"""
证据回链模块单元测试

测试文本全部为虚构数据，只模仿竣工报告的版式（参数表、「N．孔号钻孔」段落、
两行表头、合成报告的转置参数表），不含任何真实工程内容。
"""
import json
import sys
from pathlib import Path

import pytest

from core.models import DrillHoleEntity, DrillHoleDesignParams, DrillHoleActualParams
from extraction.evidence_aligner import (
    EvidenceAligner, EvidenceStatus, EvidenceReport, summarize,
)

S = EvidenceStatus

# 版式一：按孔号成行的参数表 + 正文段落（模仿真实竣工报告）
ROW_STYLE = """测试矿T巷底板超前钻探竣工报告

工程于2021年3月20日竣工，共施工3个钻孔，现将验收情况汇总如下：

一、任务来源

钻孔施工参数表

| 钻探位置 | 孔号 | 方位 | 倾角 | 开孔位置 | 终孔层位 | 终孔孔深 |
|---|---|---|---|---|---|---|
| 轨道巷12#点前20m正前方向 | T1-1 | 250° | -20° | 3煤 | 8煤底板砂岩 | 80.5m |
| 轨道巷12#点前20m左侧方向 | T1 -2 | 235° | -12° | 3煤 | 6煤顶板砂岩 | 101m |
| 轨道巷12#点前20m | T1-1-J1 | 248° | +6° | 巷道顶板下2.5m | 本溪灰岩 | 60m |

二、钻探情况

1．T1-1钻孔，设计位置：轨道巷12#点前20m；设计方位：250°；设计倾角：-20°；设计孔深：80m。

该孔2021年3月1日早班开孔，实际方位250°，倾角-20°，以φ108mm钻头钻进至20m，孔内下入φ89 mm套管19m。凝固好后用φ75mm钻头扫孔20.5m，使用φ75mm钻头钻进至80.5m位置终孔。

2．T1-2钻孔，设计位置：轨道巷12#点前20m；设计方位：235°；设计倾角：−12°；设计孔深：100m。

该孔2021年3月4日夜班开孔，实际方位235°，倾角-12°，以φ108mm钻头钻进至21m，使用φ75mm钻头钻进至101m位置终孔。

3．T1-1-J1钻孔，设计位置：轨道巷12#点前20m；设计方位：248°；设计倾角：+6°；设计孔深：60m。

该孔2021年3月9日中班开孔，实际方位248°，倾角+6°，以φ94mm钻头钻进至60m位置终孔。

三、结论

以上钻孔施工质量均达到设计要求。
"""


def hole(hid, loc=None, design=None, actual=None):
    return DrillHoleEntity(
        hole_id=hid, location_desc=loc,
        design_params=DrillHoleDesignParams(**(design or {})),
        actual_params=DrillHoleActualParams(**(actual or {})),
    )


def t11(**over):
    """T1-1 的一份完全正确的抽取结果，可用 over 覆盖个别字段"""
    design = dict(design_depth=80, design_azimuth=250, design_inclination=-20)
    actual = dict(actual_depth=80.5, actual_azimuth=250, actual_inclination=-20,
                  start_formation='3煤', end_formation='8煤底板砂岩', drilling_date='2021-03-01')
    loc = over.pop('location_desc', '轨道巷12#点前20m正前方向')
    for k, v in over.items():
        (design if k.startswith('design_') else actual)[k] = v
    return hole('T1-1', loc, design, actual)


@pytest.fixture
def aligner():
    return EvidenceAligner()


def assert_anchors_consistent(text, report: EvidenceReport):
    for f in report.fields:
        for a in f.anchors:
            assert text[a.start:a.end] == a.text, (f.hole_id, f.field, a)


# ───────────── 基本状态 ─────────────

def test_correct_extraction_is_aligned(aligner):
    rep = aligner.align(ROW_STYLE, [t11()])
    for name in ('hole_id', 'location_desc', 'design_depth', 'design_azimuth', 'design_inclination',
                 'actual_depth', 'actual_azimuth', 'actual_inclination',
                 'start_formation', 'end_formation', 'drilling_date'):
        assert rep.get('T1-1', name).status is S.ALIGNED, name
    assert_anchors_consistent(ROW_STYLE, rep)


def test_value_found_in_text_and_table_gives_two_anchors(aligner):
    rep = aligner.align(ROW_STYLE, [t11()])
    ev = rep.get('T1-1', 'actual_depth')            # 正文「钻进至80.5m位置终孔」+ 表「终孔孔深 80.5m」
    assert ev.status is S.ALIGNED
    assert sorted(a.source for a in ev.anchors) == ['table', 'text']
    assert all(a.text == '80.5' for a in ev.anchors)


def test_value_copied_from_another_holes_row_is_conflict(aligner):
    # 「正前方向」只出现在 T1-1 的行里，T1-2 的行写的是「左侧方向」
    h = hole('T1-2', '轨道巷12#点前20m正前方向', dict(design_depth=100), dict(actual_depth=101))
    ev = aligner.align(ROW_STYLE, [h]).get('T1-2', 'location_desc')
    assert ev.status is S.CONFLICT
    assert '轨道巷12#点前20m左侧方向' in ev.candidates
    # 出处只指向 T1-2 自己的行/段落，不指向 T1-1 的行
    t11_row = ROW_STYLE.index('| 轨道巷12#点前20m正前方向 | T1-1')
    assert all(not (t11_row <= a.start < t11_row + 60) for a in ev.anchors)


def test_two_drill_bits_make_diameter_ambiguous(aligner):
    ev = aligner.align(ROW_STYLE, [t11(actual_diameter=108)]).get('T1-1', 'actual_diameter')
    assert ev.status is S.AMBIGUOUS
    assert ev.candidates == [75.0, 108.0]
    assert {a.text for a in ev.anchors} == {'108', '75'}


def test_design_diameter_without_label_is_unlabeled(aligner):
    # 报告里没有「设计孔径」，108 只以钻头规格出现
    ev = aligner.align(ROW_STYLE, [t11(design_diameter=108)]).get('T1-1', 'design_diameter')
    assert ev.status is S.UNLABELED
    assert any(a.text == '108' for a in ev.anchors)


def test_value_absent_from_hole_scope_is_no_source(aligner):
    ev = aligner.align(ROW_STYLE, [t11(design_diameter=133)]).get('T1-1', 'design_diameter')
    assert ev.status is S.NO_SOURCE
    assert ev.anchors == []


def test_wrong_labelled_number_is_conflict(aligner):
    ev = aligner.align(ROW_STYLE, [t11(design_depth=85)]).get('T1-1', 'design_depth')
    assert ev.status is S.CONFLICT
    assert ev.candidates == [80.0]


def test_null_value_is_null(aligner):
    ev = aligner.align(ROW_STYLE, [t11(design_diameter=None)]).get('T1-1', 'design_diameter')
    assert ev.status is S.NULL


def test_unknown_hole_has_no_source(aligner):
    rep = aligner.align(ROW_STYLE, [hole('X9-9', '某处', dict(design_depth=80))])
    assert rep.get('X9-9', 'hole_id').status is S.NO_SOURCE
    assert rep.get('X9-9', 'design_depth').status is S.NO_SOURCE


# ───────────── 孔范围 ─────────────

def test_prefix_hole_ids_do_not_share_scope(aligner):
    # T1-1 与 T1-1-J1：J1 的设计孔深 60 不应成为 T1-1 的出处
    rep = aligner.align(ROW_STYLE, [t11(design_depth=60), hole('T1-1-J1', None, dict(design_depth=60))])
    assert rep.get('T1-1', 'design_depth').status is S.CONFLICT
    assert rep.get('T1-1-J1', 'design_depth').status is S.ALIGNED


def test_same_value_in_two_holes_anchors_only_own_scope(aligner):
    # T1-1 和 T1-2 都有 φ75 钻头；T1-2 的出处必须全在 T1-2 段落内
    rep = aligner.align(ROW_STYLE, [t11(actual_diameter=75),
                                    hole('T1-2', None, actual=dict(actual_diameter=75))])
    seg2 = ROW_STYLE.index('2．T1-2钻孔')
    seg3 = ROW_STYLE.index('3．T1-1-J1钻孔')
    ev = rep.get('T1-2', 'actual_diameter')
    assert ev.anchors and all(seg2 <= a.start < seg3 for a in ev.anchors)


def test_hole_id_with_space_in_table_cell(aligner):
    # 表格里写成「T1 -2」
    rep = aligner.align(ROW_STYLE, [hole('T1-2', '轨道巷12#点前20m左侧方向', actual=dict(actual_depth=101))])
    assert rep.get('T1-2', 'location_desc').status is S.ALIGNED
    assert any(a.source == 'table' and a.text == 'T1 -2' for a in rep.get('T1-2', 'hole_id').anchors)


# ───────────── 写法归一 ─────────────

@pytest.mark.parametrize('hid,field,value', [
    ('T1-2', 'design_inclination', -12),     # 原文「−12°」（U+2212）
    ('T1-1-J1', 'design_inclination', 6),    # 原文「+6°」
    ('T1-1-J1', 'actual_inclination', 6.0),
    ('T1-1', 'design_depth', 80.0),          # 原文「80m」
    ('T1-1', 'actual_depth', '80.5'),        # 字符串数值
])
def test_number_normalisation(aligner, hid, field, value):
    key = 'design_params' if field.startswith('design_') else 'actual_params'
    ev = aligner.align(ROW_STYLE, [{'hole_id': hid, key: {field: value}}]).get(hid, field)
    assert ev.status is S.ALIGNED


@pytest.mark.parametrize('value', ['2021-03-01', '2021-3-1', '2021.03.01'])
def test_date_formats(aligner, value):
    assert aligner.align(ROW_STYLE, [t11(drilling_date=value)]).get('T1-1', 'drilling_date').status is S.ALIGNED


def test_source_typo_shows_as_conflict(aligner):
    # 原文年份写错（2012），模型输出 2021：判为不符，并给出原文写法，交给人判断
    text = ROW_STYLE.replace('该孔2021年3月1日早班开孔', '该孔2012年3月1日早班开孔')
    ev = aligner.align(text, [t11()]).get('T1-1', 'drilling_date')
    assert ev.status is S.CONFLICT
    assert ev.candidates == ['2012-03-01']


def test_start_and_end_dates_make_date_ambiguous(aligner):
    text = ROW_STYLE.replace('使用φ75mm钻头钻进至80.5m位置终孔。',
                             '使用φ75mm钻头钻进至80.5m位置终孔，2021年3月3日施工结束。')
    ev = aligner.align(text, [t11()]).get('T1-1', 'drilling_date')
    assert ev.status is S.AMBIGUOUS
    assert ev.candidates == ['2021-03-01', '2021-03-03']


def test_zero_value_is_aligned_not_downgraded(aligner):
    # 回归：自检曾把 0 当成假值，误降级为 no_source
    text = ROW_STYLE.replace('设计倾角：+6°', '设计倾角：0°').replace('倾角+6°', '倾角0°').replace('| 248° | +6° |', '| 248° | 0° |')
    rep = aligner.align(text, [hole('T1-1-J1', None, dict(design_inclination=0), dict(actual_inclination=0))])
    assert rep.get('T1-1-J1', 'design_inclination').status is S.ALIGNED
    assert rep.get('T1-1-J1', 'actual_inclination').status is S.ALIGNED


def test_cell_with_two_locations_is_ambiguous(aligner):
    # 原文一格里同时写了「左侧方向」和「右侧方向」：交给人选，而不是判模型不符
    text = ROW_STYLE.replace('| 轨道巷12#点前20m左侧方向 | T1 -2 |', '| 轨道巷12#点前20m 左侧方向 轨道巷12#点前20m 右侧方向 | T1 -2 |')
    ev = aligner.align(text, [hole('T1-2', '轨道巷12#点前20m右侧方向')]).get('T1-2', 'location_desc')
    assert ev.status is S.AMBIGUOUS
    assert [_squash(a.text) for a in ev.anchors] == ['轨道巷12#点前20m右侧方向']
    assert_anchors_consistent(text, aligner.align(text, [hole('T1-2', '轨道巷12#点前20m右侧方向')]))
    # 两处都不是模型值时仍是不符
    assert aligner.align(text, [hole('T1-2', '轨道巷12#点前20m正前方向')]).get('T1-2', 'location_desc').status is S.CONFLICT


def _squash(s):
    return ''.join(s.split())


# ───────────── 表格版式 ─────────────

TWO_ROW_HEADER = """二、钻探情况

| 孔号 | 方位 | 方位 | 倾角 | 倾角 | 孔深 | 孔深 |
|---|---|---|---|---|---|---|
|  | 设计 | 实际 | 设计 | 实际 | 设计 | 实际 |
| K-1 | 120 | 122 | -5 | -6 | 50 | 48.5 |
"""


def test_two_row_header_maps_design_and_actual_columns(aligner):
    h = hole('K-1', None, dict(design_azimuth=120, design_inclination=-5, design_depth=50),
             dict(actual_azimuth=122, actual_inclination=-6, actual_depth=48.5))
    rep = aligner.align(TWO_ROW_HEADER, [h])
    for name in ('design_azimuth', 'design_inclination', 'design_depth',
                 'actual_azimuth', 'actual_inclination', 'actual_depth'):
        assert rep.get('K-1', name).status is S.ALIGNED, name
    # 设计/实际互换会被发现
    swapped = hole('K-1', None, dict(design_azimuth=122))
    assert aligner.align(TWO_ROW_HEADER, [swapped]).get('K-1', 'design_azimuth').status is S.CONFLICT


TRANSPOSED = """二、钻孔施工情况

1．SYN-01钻孔，设计位置：运输巷 316#点前 65m；设计方位：90.0°；设计倾角：-10.0°；设计孔深：100.0 m。

该孔实际施工参数：实际方位92.0°，实际倾角-11.0°，终孔深度98.0 m。

参数汇总表：

| 字段 | 设计 | 实际 | 单位 |
|---|---|---|---|
| 孔深 | 100.0 | 98.0 | m |
| 方位角 | 90.0 | 92.0 | ° |
| 倾角 | -10.0 | -11.0 | ° |

2．SYN-02钻孔，设计位置：轨道上山 15#点前 88m；设计方位：45.0°；设计倾角：-5.0°；设计孔深：60.0 m。

该孔实际施工参数：实际方位44.0°，实际倾角-6.0°，终孔深度58.0 m。

参数汇总表：

| 字段 | 设计 | 实际 | 单位 |
|---|---|---|---|
| 孔深 | 60.0 | 58.0 | m |
| 方位角 | 45.0 | 44.0 | ° |
| 倾角 | -5.0 | -6.0 | ° |
"""


def test_transposed_summary_table_belongs_to_enclosing_hole(aligner):
    h1 = hole('SYN-01', '运输巷 316#点前 65m', dict(design_depth=100, design_azimuth=90, design_inclination=-10),
              dict(actual_depth=98, actual_azimuth=92, actual_inclination=-11))
    rep = aligner.align(TRANSPOSED, [h1])
    for f in rep.for_hole('SYN-01'):
        if f.field not in ('start_formation', 'end_formation', 'drilling_date', 'design_diameter', 'actual_diameter'):
            assert f.status is S.ALIGNED, f.field
    # 设计孔深在正文和本孔汇总表各出现一次，且不会指到 SYN-02 的表
    ev = rep.get('SYN-01', 'design_depth')
    assert sorted(a.source for a in ev.anchors) == ['table', 'text']
    assert all(a.start < TRANSPOSED.index('2．SYN-02钻孔') for a in ev.anchors)
    # 「单位」列不会被当成数值出处
    assert all(a.label is None or '单位' not in a.label for a in ev.anchors)


def test_location_with_spaces_compares_whitespace_insensitively(aligner):
    h = hole('SYN-02', '轨道上山15#点前88m')
    assert aligner.align(TRANSPOSED, [h]).get('SYN-02', 'location_desc').status is S.ALIGNED


# ───────────── 输出与自检 ─────────────

def test_all_anchors_slice_back_to_source(aligner):
    holes = [t11(actual_diameter=108, design_diameter=108),
             hole('T1-2', '轨道巷12#点前20m正前方向', dict(design_inclination=-12), dict(actual_depth=101)),
             hole('T1-1-J1', '轨道巷12#点前20m', dict(design_depth=60), dict(start_formation='巷道顶板下2.5m'))]
    rep = aligner.align(ROW_STYLE, holes)
    assert_anchors_consistent(ROW_STYLE, rep)
    assert rep.source_length == len(ROW_STYLE)


def test_report_is_json_serialisable_and_summarises(aligner):
    rep = aligner.align(ROW_STYLE, [t11(actual_diameter=108, design_diameter=None)])
    d = json.loads(json.dumps(rep.to_dict(), ensure_ascii=False))
    assert d['summary']['ambiguous'] == 1 and d['summary']['null'] == 1
    assert sum(d['summary'].values()) == len(d['fields'])
    assert len(d['source_sha1']) == 40
    assert summarize([rep, rep])['ambiguous'] == 2


def test_verify_downgrades_inconsistent_anchor(aligner):
    from extraction.evidence_aligner import EvidenceAnchor, FieldEvidence
    bad = FieldEvidence('T1-1', 'design_depth', 80, S.ALIGNED, [EvidenceAnchor(0, 2, '80', 'text')])
    assert aligner._verify(ROW_STYLE, bad).status is S.NO_SOURCE


def test_dict_and_entity_inputs_agree(aligner):
    ent = t11(actual_diameter=108)
    as_dict = {'hole_id': 'T1-1', 'location_desc': ent.location_desc,
               'design_params': vars(ent.design_params), 'actual_params': vars(ent.actual_params)}
    a = aligner.align(ROW_STYLE, [ent]).to_dict()['fields']
    b = aligner.align(ROW_STYLE, [as_dict]).to_dict()['fields']
    assert [(x['field'], x['status']) for x in a] == [(x['field'], x['status']) for x in b]


# ───────────── 与 DocumentProcessor 的偏移一致性 ─────────────

def test_offsets_match_document_processor_output(aligner, tmp_path):
    """用合成数据生成器写一份真实 .docx，经 DocumentProcessor 转成 markdown 后再回链"""
    pytest.importorskip('docx')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.generate_synthetic_dataset import SyntheticDoc, SyntheticHole, _write_docx_zh
    from extraction.document_processor import DocumentProcessor

    h = SyntheticHole('SYN-T1', '轨道上山 15#点前 88m', 'x', 60.0, 45.0, -5.0, 58.0, 44.0, -6.0)
    path = tmp_path / 'syn.docx'
    _write_docx_zh(path, SyntheticDoc('syn.docx', '合成报告', '合成项目', 't', 'p', '2026-01-20', [h]))
    md = DocumentProcessor().process_document(str(path))

    ent = hole('SYN-T1', '轨道上山 15#点前 88m', dict(design_depth=60, design_azimuth=45, design_inclination=-5),
               dict(actual_depth=58, actual_azimuth=44, actual_inclination=-6))
    rep = aligner.align(md, [ent])
    assert_anchors_consistent(md, rep)
    for name in ('hole_id', 'location_desc', 'design_depth', 'design_azimuth', 'design_inclination',
                 'actual_depth', 'actual_azimuth', 'actual_inclination'):
        assert rep.get('SYN-T1', name).status is S.ALIGNED, name


# ───────────── 流水线开关 ─────────────

class _FakeLLM:
    model = None

    def __init__(self, entities_json):
        self._json = entities_json

    def generate(self, prompt):
        from llm.base import LLMResponse
        return LLMResponse(content=self._json, model='fake', usage=None)


class _FakeConfig:
    def __init__(self, survey):
        self._survey = survey

    def get(self, key, default=None):
        return default

    def get_data_paths(self):
        return {'survey_points_file': self._survey}


@pytest.mark.parametrize('enabled', [False, True])
def test_pipeline_flag(tmp_path, monkeypatch, enabled):
    from extraction.pipeline import ExtractionPipeline
    from extraction.document_processor import DocumentProcessor

    survey = tmp_path / 'pts.csv'
    survey.write_text('FID,X,Y,Z\n12,0,0,0\n13,10,0,0\n', encoding='utf-8')
    entities = json.dumps([{'hole_id': 'T1-1', 'location_desc': '轨道巷12#点前20m正前方向',
                            'design_params': {'design_depth': 80}, 'actual_params': {'actual_depth': 80.5}}],
                          ensure_ascii=False)
    monkeypatch.setattr(DocumentProcessor, 'process_document', lambda self, p: ROW_STYLE)
    pipe = ExtractionPipeline(llm_client=_FakeLLM(entities), config_loader=_FakeConfig(str(survey)),
                              enable_evidence_alignment=enabled)
    monkeypatch.setattr(pipe.coordinate_inferencer, 'infer_coordinates', lambda holes: ({}, {}))
    doc = tmp_path / 'r.docx'
    doc.write_bytes(b'')
    res = pipe.process_document(doc)

    assert not res.errors
    if enabled:
        ev = res.metadata['evidence']
        assert res.metadata['source_text'] == ROW_STYLE
        st = {(f['hole_id'], f['field']): f['status'] for f in ev['fields']}
        assert st[('T1-1', 'design_depth')] == 'aligned'
        assert st[('T1-1', 'actual_depth')] == 'aligned'
    else:
        assert 'evidence' not in res.metadata and 'source_text' not in res.metadata
