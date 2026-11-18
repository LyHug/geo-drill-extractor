"""
人工核对会话与单孔坐标推断测试（虚构数据，不调用真实模型）
"""
import json

import pytest

from core import Coordinate
from extraction.coordinate_inferencer import CoordinateInferencer
from extraction.review import (
    Action, HoleState, ReviewError, ReviewSession, FAILURE_MESSAGES,
)
from .evidence_fixtures import ROW_STYLE, hole, t11

# 导线点：12 → 13 沿 X 轴正向；没有 11 号点
SURVEY = 'FID,X,Y,Z\n12,1000,2000,-300\n13,1100,2000,-300\n'

LOCATION_JSON = {
    # 正前：12 → 13 前进 20 m
    '轨道巷12#点前20m正前方向': {'参考点号': '12', '方向参考点号': '13', '距离': 20, '方向类型': 'forward',
                          '侧向偏移': {'方向': 'none', '距离': 0}, '垂直偏移': {'方向': 'none', '距离': 0}, '置信度': 0.95},
    # 左侧：模型把方向点推成了不存在的 11 号点 → 方向参考点未找到
    '轨道巷12#点前20m左侧方向': {'参考点号': '12', '方向参考点号': '11', '距离': 20, '方向类型': 'forward',
                          '侧向偏移': {'方向': 'none', '距离': 0}, '垂直偏移': {'方向': 'none', '距离': 0}, '置信度': 0.9},
}


class FakeLLM:
    """按位置描述返回预设的位置分析 JSON"""

    def __init__(self, name, table, broken=False):
        self.model = name
        self.table = table
        self.broken = broken
        self.calls = 0

    def generate(self, prompt):
        from llm.base import LLMResponse
        self.calls += 1
        if self.broken:
            return LLMResponse(content='不是 JSON', model=self.model)
        desc = prompt.split('钻孔位置描述:')[1].split('\n')[0].strip()
        return LLMResponse(content=json.dumps(self.table.get(desc, {}), ensure_ascii=False), model=self.model)


@pytest.fixture
def survey(tmp_path):
    p = tmp_path / 'pts.csv'
    p.write_text(SURVEY, encoding='utf-8')
    return str(p)


@pytest.fixture
def inf_a(survey):
    return CoordinateInferencer(survey, FakeLLM('model-a', LOCATION_JSON))


@pytest.fixture
def inf_b(survey):
    # 「换模型」：model-b 能把左侧方向推出来
    table = dict(LOCATION_JSON)
    table['轨道巷12#点前20m左侧方向'] = dict(LOCATION_JSON['轨道巷12#点前20m正前方向'], 置信度=0.85)
    return CoordinateInferencer(survey, FakeLLM('model-b', table))


def session(holes, inferencer=None, coordinates=None):
    return ReviewSession(ROW_STYLE, holes, coordinates or {}, inferencer, model_name='model-a')


# ───────────── CoordinateInferencer.infer_hole ─────────────

def test_infer_hole_success_with_end_point(inf_a):
    coords, reason, info = inf_a.infer_hole(t11())
    assert reason is None and info['方向类型'] == 'forward'
    assert (round(coords['start'].x, 6), coords['start'].y, coords['start'].z) == (1020.0, 2000.0, -300.0)
    assert 'end' in coords                       # 有实际方位/倾角/孔深就算终点


def test_infer_hole_reports_direction_point_missing(inf_a):
    coords, reason, _ = inf_a.infer_hole(hole('T1-2', '轨道巷12#点前20m左侧方向'))
    assert coords is None and reason == 'survey_direction_point_not_found'


def test_infer_hole_protocol_failure_and_missing_desc(survey):
    inf = CoordinateInferencer(survey, FakeLLM('bad', {}, broken=True))
    assert inf.infer_hole(t11())[1] == 'location_json_decode_error'
    assert inf.infer_hole(hole('T1-2', None))[1] == 'missing_location_desc'


def test_infer_hole_malformed_offsets_do_not_raise(survey):
    # 模型把偏移写成数字（不符合提示词格式）：单孔接口返回失败代码而不是抛异常
    bad = {'轨道巷12#点前20m正前方向': dict(LOCATION_JSON['轨道巷12#点前20m正前方向'], 侧向偏移=5)}
    inf = CoordinateInferencer(survey, FakeLLM('m', bad))
    coords, reason, _ = inf.infer_hole(t11())
    assert coords is None and reason == 'location_field_invalid'
    assert FAILURE_MESSAGES[reason][1] == 'protocol_parsing'


def test_batch_failure_counts_unchanged(inf_a):
    # 批量接口的失败统计口径不因重构改变
    holes = [t11(), hole('T1-2', '轨道巷12#点前20m左侧方向')]
    coords, stats = inf_a.infer_coordinates(holes)
    assert set(coords) == {'T1-1'}
    assert stats['start_coordinate_failure_counts'] == {'survey_direction_point_not_found': 1}


def test_every_failure_code_has_message():
    codes = {'missing_reference_point', 'location_json_not_object', 'location_json_decode_error', 'llm_call_failed',
             'location_field_invalid', 'location_analysis_exception', 'start_coordinate_exception',
             'survey_ref_point_not_found', 'survey_direction_point_not_found', 'start_coordinate_failed',
             'no_survey_points', 'missing_location_desc'}
    assert codes <= set(FAILURE_MESSAGES)


# ───────────── 字段决定 ─────────────

def test_pending_fields_and_blockers():
    s = session([t11(actual_diameter=108, design_diameter=108)])
    assert set(s.pending('T1-1')) == {'actual_diameter', 'design_diameter'}
    assert 'coordinate:not_inferred' in s.blockers('T1-1')


def test_use_source_value_fixes_conflict_and_records_anchor():
    h = hole('T1-2', '轨道巷12#点前20m正前方向')
    s = session([h])
    assert 'location_desc' in s.pending('T1-2')
    d = s.decide('T1-2', 'location_desc', Action.USE_SOURCE, value='轨道巷12#点前20m左侧方向')
    assert h.location_desc == '轨道巷12#点前20m左侧方向'
    assert d.model_value == '轨道巷12#点前20m正前方向'
    assert ROW_STYLE[d.anchor.start:d.anchor.end] == d.anchor.text and d.anchor.source == 'table'
    assert 'location_desc' not in s.pending('T1-2')


def test_use_source_rejects_value_not_in_source():
    s = session([hole('T1-2', '轨道巷12#点前20m正前方向')])
    with pytest.raises(ReviewError):
        s.decide('T1-2', 'location_desc', Action.USE_SOURCE, value='某处')


def test_pick_ambiguous_candidate_by_index():
    h = t11(actual_diameter=108)
    s = session([h])
    ev = s.report.get('T1-1', 'actual_diameter')
    d = s.decide('T1-1', 'actual_diameter', 'use_source', candidate_index=ev.candidates.index(75.0))
    assert h.actual_params.actual_diameter == 75.0 and d.anchor.text == '75'


def test_set_null_and_set_value():
    h = t11(design_diameter=108)
    s = session([h])
    s.decide('T1-1', 'design_diameter', Action.SET_NULL)
    assert h.design_params.design_diameter is None
    s.decide('T1-1', 'end_formation', Action.SET_VALUE, value=' 8煤底板砂岩 ')
    assert h.actual_params.end_formation == '8煤底板砂岩'
    with pytest.raises(ReviewError):
        s.decide('T1-1', 'design_depth', Action.SET_VALUE, value='八十米')


def test_unknown_hole_and_field_are_rejected():
    s = session([t11()])
    with pytest.raises(ReviewError):
        s.decide('X', 'design_depth', Action.ACCEPT_MODEL)
    with pytest.raises(ReviewError):
        s.decide('T1-1', 'hole_id', Action.ACCEPT_MODEL)


def test_duplicate_hole_ids_rejected():
    with pytest.raises(ReviewError):
        session([t11(), t11()])


# ───────────── 坐标 ─────────────

def test_changing_location_invalidates_coordinate(inf_a):
    h = hole('T1-2', '轨道巷12#点前20m正前方向', actual=dict(actual_depth=101))
    start = Coordinate(1020, 2000, -300, 0.95, 'high_confidence_forward')
    s = session([h], inf_a, {'T1-2': {'start': start}})
    assert s.coords['T1-2'].ok
    s.decide('T1-2', 'location_desc', Action.USE_SOURCE, value='轨道巷12#点前20m左侧方向')
    assert not s.coords['T1-2'].ok and s.coords['T1-2'].failure == 'location_changed'
    # 保留模型值（不变）不会作废坐标
    s2 = session([hole('T1-1', '轨道巷12#点前20m正前方向')], inf_a, {'T1-1': {'start': start}})
    s2.decide('T1-1', 'location_desc', Action.ACCEPT_MODEL)
    assert s2.coords['T1-1'].ok


def test_reinfer_fails_then_succeeds_with_other_model(inf_a, inf_b):
    # 对应界面第 6、7 步：采用原文值 → 本模型重算失败 → 换模型重算成功
    h = hole('T1-2', '轨道巷12#点前20m正前方向',
             dict(design_depth=100, design_azimuth=235, design_inclination=-12),
             dict(actual_depth=101, actual_azimuth=235, actual_inclination=-12, drilling_date='2021-03-04'))
    s = session([h], inf_a)
    s.decide('T1-2', 'location_desc', Action.USE_SOURCE, value='轨道巷12#点前20m左侧方向')

    r1 = s.reinfer('T1-2')
    assert not r1.ok and r1.failure == 'survey_direction_point_not_found'
    assert r1.to_dict()['failure_message'] == '方向参考点未找到'
    assert r1.to_dict()['failure_category'] == 'semantic_geometric'

    r2 = s.reinfer('T1-2', inferencer=inf_b)
    assert r2.ok and r2.model == 'model-b' and r2.source == 'inferred'
    assert [a['model'] for a in r2.attempts] == ['model-a', 'model-b']
    assert r2.end is not None


def test_manual_pick_computes_end_from_actual_params():
    h = t11()
    s = session([h])
    rec = s.set_manual_coordinate('T1-1', 1000, 2000, -300)
    assert rec.source == 'manual_pick' and rec.start.method == 'manual_pick'
    assert rec.end is not None and rec.end.z < -300        # 倾角 -20° 向下


def test_editing_geometry_recomputes_end():
    h = t11()
    s = session([h])
    s.set_manual_coordinate('T1-1', 1000, 2000, -300)
    z_before = s.coords['T1-1'].end.z
    s.decide('T1-1', 'actual_inclination', Action.SET_VALUE, value=-40)
    assert s.coords['T1-1'].end.z < z_before


# ───────────── 确认 / 跳过 / 入库清单 ─────────────

def test_confirm_requires_all_fields_and_coordinate(inf_a):
    h = t11(actual_diameter=108, design_diameter=108)
    s = session([h], inf_a)
    with pytest.raises(ReviewError) as e:
        s.confirm('T1-1')
    assert set(e.value.reasons) == {'field:actual_diameter', 'field:design_diameter', 'coordinate:not_inferred'}
    s.decide('T1-1', 'actual_diameter', Action.USE_SOURCE, value=75)
    s.decide('T1-1', 'design_diameter', Action.SET_NULL)
    s.reinfer('T1-1')
    s.confirm('T1-1')
    assert s.state['T1-1'] is HoleState.CONFIRMED
    with pytest.raises(ReviewError):                       # 确认后不能直接改
        s.decide('T1-1', 'design_depth', Action.SET_VALUE, value=81)
    s.reopen('T1-1')
    s.decide('T1-1', 'design_depth', Action.ACCEPT_MODEL)


def test_commit_plan_lists_confirmed_skipped_and_unreviewed(inf_a):
    holes = [t11(), hole('T1-2', '轨道巷12#点前20m左侧方向', actual=dict(actual_depth=101)),
             hole('T1-1-J1', '轨道巷12#点前20m', dict(design_depth=60))]
    s = session(holes, inf_a)
    s.reinfer('T1-1')
    s.confirm('T1-1')
    s.reinfer('T1-2')                                      # 方向参考点未找到
    s.skip('T1-2')
    plan = json.loads(json.dumps(s.commit_plan(), ensure_ascii=False))

    assert [c['hole_id'] for c in plan['commit']] == ['T1-1']
    assert plan['skipped'] == [{'hole_id': 'T1-2', 'reason': 'survey_direction_point_not_found'}]
    assert plan['unreviewed'] == ['T1-1-J1']
    c = plan['commit'][0]
    assert c['coordinate']['source'] == 'inferred' and c['coordinate']['model'] == 'model-a'
    assert c['provenance']['design_depth']['status'] == 'aligned'
    assert c['provenance']['design_depth']['anchors'][0]['text'] == '80'
    assert plan['source_sha1'] == s.report.source_sha1


def test_commit_plan_keeps_manual_decisions_in_provenance():
    h = t11(actual_diameter=108)
    s = session([h])
    s.decide('T1-1', 'actual_diameter', Action.USE_SOURCE, value='75')
    s.set_manual_coordinate('T1-1', 1, 2, 3)
    s.confirm('T1-1')
    c = s.commit_plan()['commit'][0]
    p = c['provenance']['actual_diameter']
    assert p['status'] == 'ambiguous' and p['model_value'] == 108
    assert p['decision']['action'] == 'use_source' and p['decision']['value'] == 75.0
    assert c['fields']['actual_diameter'] == 75.0
    assert c['coordinate']['source'] == 'manual_pick'


def test_hole_summary_for_list_row(inf_a):
    s = session([hole('T1-2', '轨道巷12#点前20m正前方向', actual=dict(actual_diameter=108))], inf_a)
    row = s.hole_summary('T1-2')
    assert row['pending']['conflict'] == 1 and row['pending']['ambiguous'] == 1
    assert row['can_confirm'] is False and row['state'] == 'reviewing'
    json.dumps(s.to_dict(), ensure_ascii=False)


def test_from_process_result_requires_source_text():
    from core import ProcessResult
    r = ProcessResult('a.docx', [t11()], {}, 0.0, metadata={'model': 'model-a'})
    with pytest.raises(ReviewError):
        ReviewSession.from_process_result(r)
    r.metadata['source_text'] = ROW_STYLE
    s = ReviewSession.from_process_result(r)
    assert s.model_name == 'model-a' and s.order == ['T1-1']
