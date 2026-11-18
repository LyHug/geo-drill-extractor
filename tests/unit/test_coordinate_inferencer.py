"""
批量坐标推断：模型输出字段类型不合预期时不再悄悄丢孔（虚构数据，不调用真实模型）
"""
import pytest

from extraction.coordinate_inferencer import CoordinateInferencer
from .evidence_fixtures import hole
from .test_review import FakeLLM, SURVEY

OK = {'参考点号': '12', '方向参考点号': '13', '距离': 20, '方向类型': 'forward',
      '侧向偏移': {'方向': 'none', '距离': 0}, '垂直偏移': {'方向': 'none', '距离': 0}, '置信度': 0.95}


@pytest.fixture
def survey(tmp_path):
    p = tmp_path / 'pts.csv'
    p.write_text(SURVEY, encoding='utf-8')
    return str(p)


def run(survey, table):
    """每条位置描述一个孔；返回 (坐标, 统计)"""
    inf = CoordinateInferencer(survey, FakeLLM('m', table))
    holes = [hole(f'K{i}', desc, actual=dict(actual_depth=50, actual_azimuth=90, actual_inclination=-10))
             for i, desc in enumerate(table)]
    return inf.infer_coordinates(holes)


def assert_no_silent_drop(coords, stats, n_groups):
    """每个位置组要么有坐标，要么被计入某一类失败"""
    with_coords = len(coords)
    start_fail = sum(stats['start_coordinate_failure_counts'].values())
    loc_fail = sum(stats['location_analysis_failure_counts'].values())
    assert stats['location_analysis_success_count'] == with_coords + start_fail
    assert stats['location_analysis_success_count'] + loc_fail == n_groups


@pytest.mark.parametrize('variant', [
    {'距离': '20m'},                                   # 距离写成带单位的字符串
    {'距离': '20'},
    {'侧向偏移': 0, '垂直偏移': None},                    # 偏移写成 0 / null
    {'侧向偏移': 'none', '垂直偏移': ''},
    {'侧向偏移': {'方向': 'none', '距离': '0'}},          # 偏移距离是字符串
    {'置信度': '0.95'},                                 # 置信度是字符串（曾在判定 method 时抛异常）
])
def test_tolerated_variants_now_get_coordinates(survey, variant):
    coords, stats = run(survey, {'A处': {**OK, **variant}})
    assert set(coords) == {'K0'}
    c = coords['K0']['start']
    assert (round(c.x, 6), c.y, c.z) == (1020.0, 2000.0, -300.0)
    assert c.method == 'high_confidence_forward'
    assert 'end' in coords['K0']
    assert_no_silent_drop(coords, stats, 1)


@pytest.mark.parametrize('variant', [
    {'侧向偏移': 5},                                    # 只有数字没有方向，无法解释
    {'距离': '约二十米'},
    {'垂直偏移': {'方向': 'down', '距离': '若干'}},
])
def test_unexplainable_fields_are_counted_as_protocol_failure(survey, variant):
    coords, stats = run(survey, {'A处': {**OK, **variant}})
    assert coords == {}
    assert stats['location_analysis_failure_counts'] == {'location_field_invalid': 1}
    assert_no_silent_drop(coords, stats, 1)


def test_unexpected_exception_is_counted_not_dropped(survey, monkeypatch):
    inf = CoordinateInferencer(survey, FakeLLM('m', {'A处': OK, 'B处': OK}))

    def boom(*a, **k):
        raise RuntimeError('boom')
    monkeypatch.setattr(inf, '_calculate_start_coordinate', boom)
    holes = [hole('K0', 'A处'), hole('K1', 'B处')]
    coords, stats = inf.infer_coordinates(holes)
    assert coords == {}
    assert stats['start_coordinate_failure_counts'] == {'start_coordinate_exception': 2}
    assert_no_silent_drop(coords, stats, 2)


def test_mixed_batch_invariant(survey):
    table = {
        'A处': OK,                                         # 成功
        'B处': {**OK, '距离': '30 m'},                      # 规范化后成功
        'C处': {**OK, '方向参考点号': '11'},                 # 方向参考点未找到
        'D处': {**OK, '侧向偏移': 3},                        # 字段无法解释
        'E处': {},                                         # 缺参考点号
    }
    coords, stats = run(survey, table)
    assert set(coords) == {'K0', 'K1'}
    assert stats['start_coordinate_failure_counts'] == {'survey_direction_point_not_found': 1}
    assert stats['location_analysis_failure_counts'] == {'location_field_invalid': 1, 'missing_reference_point': 1}
    assert_no_silent_drop(coords, stats, 5)


def test_well_formed_output_unchanged(survey):
    # 规范化对符合提示词格式的输出没有影响
    coords, _ = run(survey, {'A处': {**OK, '侧向偏移': {'方向': 'left', '距离': 5}}})
    c = coords['K0']['start']
    assert (round(c.x, 6), round(c.y, 6)) == (1020.0, 1995.0)
