"""
人工核对会话 - 原文对照界面背后的后端操作

一份报告抽取完成后，用户在界面上逐孔核对。本模块提供这些操作并记录来源：

* ``decide``      对一个字段做决定：保留模型值 / 采用原文中的值 / 人工输入 / 置空
* ``reinfer``     （改了位置描述后）重新推断坐标，可传入另一个模型的推断器
* ``set_manual_coordinate``  在三维中点选开孔位置
* ``confirm`` / ``skip`` / ``reopen``  确认此孔 / 本次不入库 / 撤回
* ``commit_plan`` 生成入库清单：已确认的孔、每个字段的出处与人工决定、坐标来源

不直接写数据库或图层，入库由调用方（如 webThree 后端）按清单执行。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields as dc_fields
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core import Coordinate, DrillHoleEntity, DrillHoleDesignParams, DrillHoleActualParams, calculate_drill_hole_endpoint
from .evidence_aligner import (
    CHECKED_FIELDS, DATE_FIELDS, NUMERIC_FIELDS,
    EvidenceAligner, EvidenceAnchor, EvidenceReport, EvidenceStatus, FieldEvidence,
    _norm_date, _squash, _to_float,
)

REVIEW_FIELDS = tuple(f for f in CHECKED_FIELDS if f != 'hole_id')
PENDING_STATUSES = {EvidenceStatus.AMBIGUOUS, EvidenceStatus.UNLABELED,
                    EvidenceStatus.CONFLICT, EvidenceStatus.NO_SOURCE}
_DESIGN_FIELDS = {f.name for f in dc_fields(DrillHoleDesignParams)}
_ACTUAL_FIELDS = {f.name for f in dc_fields(DrillHoleActualParams)}
_GEOMETRY_FIELDS = {'design_depth', 'design_azimuth', 'design_inclination',
                    'actual_depth', 'actual_azimuth', 'actual_inclination'}

# 坐标失败原因：代码 -> (界面文案, 失败类别)
FAILURE_MESSAGES: Dict[str, Tuple[str, str]] = {
    'missing_reference_point':          ('位置描述中没有识别出导线点号', 'semantic_geometric'),
    'survey_ref_point_not_found':       ('参考导线点不在导线点文件中', 'semantic_geometric'),
    'survey_direction_point_not_found': ('方向参考点未找到', 'semantic_geometric'),
    'start_coordinate_failed':          ('起点坐标计算失败', 'semantic_geometric'),
    'location_json_not_object':         ('位置分析结果格式错误', 'protocol_parsing'),
    'location_json_decode_error':       ('位置分析结果无法解析', 'protocol_parsing'),
    'llm_call_failed':                  ('模型调用失败', 'protocol_parsing'),
    'location_field_invalid':           ('位置分析结果字段格式不合要求', 'protocol_parsing'),
    'location_analysis_exception':      ('位置分析过程异常', 'internal'),
    'start_coordinate_exception':       ('起点坐标计算异常', 'internal'),
    'no_survey_points':                 ('未加载导线点', 'environment'),
    'missing_location_desc':            ('缺少位置描述', 'semantic_geometric'),
    'location_changed':                 ('位置描述已修改，需重新推断坐标', 'pending'),
    'not_inferred':                     ('尚未推断坐标', 'pending'),
}


class ReviewError(ValueError):
    """核对操作不合法（如待处理字段未处理就确认）"""

    def __init__(self, message: str, reasons: Optional[List[str]] = None):
        super().__init__(message)
        self.reasons = reasons or []


class HoleState(str, Enum):
    REVIEWING = 'reviewing'
    CONFIRMED = 'confirmed'
    SKIPPED = 'skipped'


class Action(str, Enum):
    ACCEPT_MODEL = 'accept_model'   # 保留模型值
    USE_SOURCE = 'use_source'       # 采用原文中的某个值
    SET_VALUE = 'set_value'         # 人工输入
    SET_NULL = 'set_null'           # 置空


@dataclass
class FieldDecision:
    field: str
    action: Action
    value: Any
    model_value: Any
    anchor: Optional[EvidenceAnchor] = None
    decided_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))

    def to_dict(self) -> Dict[str, Any]:
        return {'field': self.field, 'action': self.action.value, 'value': self.value,
                'model_value': self.model_value, 'anchor': self.anchor.to_dict() if self.anchor else None,
                'decided_at': self.decided_at}


@dataclass
class CoordinateRecord:
    start: Optional[Coordinate] = None
    end: Optional[Coordinate] = None
    source: Optional[str] = None          # 'inferred' | 'manual_pick'
    model: Optional[str] = None
    failure: Optional[str] = None         # FAILURE_MESSAGES 中的代码
    attempts: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.start is not None

    def to_dict(self) -> Dict[str, Any]:
        c = lambda p: None if p is None else {'x': p.x, 'y': p.y, 'z': p.z, 'confidence': p.confidence, 'method': p.method}
        msg, cat = FAILURE_MESSAGES.get(self.failure, (self.failure, 'unknown')) if self.failure else (None, None)
        return {'start': c(self.start), 'end': c(self.end), 'source': self.source, 'model': self.model,
                'failure': self.failure, 'failure_message': msg, 'failure_category': cat,
                'attempts': list(self.attempts)}


def _model_name(inferencer: Any) -> Optional[str]:
    client = getattr(inferencer, 'llm_client', None)
    m = getattr(client, 'model', None)
    return getattr(m, 'value', m) if m is not None else getattr(inferencer, 'model_name', None)


def _get_field(hole: DrillHoleEntity, f: str) -> Any:
    if f == 'location_desc':
        return hole.location_desc
    part = hole.design_params if f in _DESIGN_FIELDS else hole.actual_params
    return getattr(part, f, None) if part is not None else None


def _set_field(hole: DrillHoleEntity, f: str, v: Any) -> None:
    if f == 'location_desc':
        hole.location_desc = v
        return
    if f in _DESIGN_FIELDS:
        if hole.design_params is None:
            hole.design_params = DrillHoleDesignParams()
        setattr(hole.design_params, f, v)
    else:
        if hole.actual_params is None:
            hole.actual_params = DrillHoleActualParams()
        setattr(hole.actual_params, f, v)


def _coerce(f: str, v: Any) -> Any:
    """人工输入/原文取值统一成字段类型"""
    if v is None:
        return None
    if f in NUMERIC_FIELDS:
        x = v if isinstance(v, (int, float)) else _to_float(str(v).strip().rstrip('m°mm米度毫'))
        if x is None:
            raise ReviewError(f'{f} 需要数值，收到 {v!r}')
        return float(x)
    if f in DATE_FIELDS:
        d = _norm_date(v)
        if d is None:
            raise ReviewError(f'{f} 需要日期，收到 {v!r}')
        return d
    s = str(v).strip()
    return s or None


class ReviewSession:
    """
    一份报告的核对会话

    用法::

        s = ReviewSession.from_process_result(result, inferencer)
        s.decide('T1-2', 'location_desc', Action.USE_SOURCE, value='轨道巷12#点前20m左侧方向')
        s.reinfer('T1-2', inferencer=other_model_inferencer)
        s.confirm('T1-2')
        plan = s.commit_plan()
    """

    def __init__(self, source_text: str, holes: Sequence[DrillHoleEntity],
                 coordinates: Optional[Dict[str, Dict[str, Coordinate]]] = None,
                 inferencer: Any = None, aligner: Optional[EvidenceAligner] = None,
                 model_name: Optional[str] = None,
                 evidence: Optional[EvidenceReport] = None):
        self.source_text = source_text
        self.order = [h.hole_id for h in holes]
        if len(set(self.order)) != len(self.order):
            raise ReviewError('同一份报告中孔号重复，无法建立核对会话')
        self.holes: Dict[str, DrillHoleEntity] = {h.hole_id: h for h in holes}
        self.model_values = {hid: {f: _get_field(h, f) for f in REVIEW_FIELDS} for hid, h in self.holes.items()}
        self.inferencer = inferencer
        self.model_name = model_name or _model_name(inferencer)
        self.report = evidence or (aligner or EvidenceAligner()).align(source_text, holes)
        self.decisions: Dict[str, Dict[str, FieldDecision]] = {hid: {} for hid in self.order}
        self.state: Dict[str, HoleState] = {hid: HoleState.REVIEWING for hid in self.order}
        self.skip_reason: Dict[str, str] = {}
        coordinates = coordinates or {}
        self.coords: Dict[str, CoordinateRecord] = {}
        for hid in self.order:
            c = coordinates.get(hid) or {}
            if c.get('start') is not None:
                self.coords[hid] = CoordinateRecord(c['start'], c.get('end'), 'inferred', self.model_name)
            else:
                self.coords[hid] = CoordinateRecord(failure='not_inferred')

    @classmethod
    def from_process_result(cls, result: Any, inferencer: Any = None,
                            aligner: Optional[EvidenceAligner] = None) -> 'ReviewSession':
        """从 ``ExtractionPipeline.process_document`` 的结果建立会话（需开启 enable_evidence_alignment）"""
        text = result.metadata.get('source_text')
        if text is None:
            raise ReviewError('结果中没有 source_text，请以 enable_evidence_alignment=True 运行流水线')
        return cls(text, result.drill_holes, result.coordinates, inferencer, aligner, result.metadata.get('model'))

    # ── 查询 ──
    def _hole(self, hid: str) -> DrillHoleEntity:
        if hid not in self.holes:
            raise ReviewError(f'未知孔号 {hid}')
        return self.holes[hid]

    def evidence(self, hid: str) -> List[FieldEvidence]:
        self._hole(hid)
        return self.report.for_hole(hid)

    def pending(self, hid: str) -> List[str]:
        """需要人处理、且还没有决定的字段"""
        done = self.decisions[hid]
        return [e.field for e in self.evidence(hid)
                if e.field in REVIEW_FIELDS and e.status in PENDING_STATUSES and e.field not in done]

    def blockers(self, hid: str) -> List[str]:
        """确认此孔前还差什么"""
        reasons = [f'field:{f}' for f in self.pending(hid)]
        if not self.coords[hid].ok:
            reasons.append(f'coordinate:{self.coords[hid].failure or "not_inferred"}')
        return reasons

    # ── 字段决定 ──
    def _ensure_open(self, hid: str) -> None:
        if self.state[hid] is not HoleState.REVIEWING:
            raise ReviewError(f'{hid} 已{ "确认" if self.state[hid] is HoleState.CONFIRMED else "跳过"}，先 reopen 再修改')

    def decide(self, hid: str, field_name: str, action: Action | str, value: Any = None,
               candidate_index: Optional[int] = None) -> FieldDecision:
        hole = self._hole(hid)
        self._ensure_open(hid)
        if field_name not in REVIEW_FIELDS:
            raise ReviewError(f'不可核对的字段 {field_name}')
        action = Action(action)
        ev = self.report.get(hid, field_name)
        model_value = self.model_values[hid][field_name]
        anchor = None

        if action is Action.ACCEPT_MODEL:
            new = model_value
        elif action is Action.SET_NULL:
            new = None
        elif action is Action.SET_VALUE:
            if value is None:
                raise ReviewError('人工输入需要提供 value')
            new = _coerce(field_name, value)
        else:  # USE_SOURCE
            new, anchor = self._pick_source(ev, field_name, value, candidate_index)

        before = _get_field(hole, field_name)
        _set_field(hole, field_name, new)
        d = FieldDecision(field_name, action, new, model_value, anchor)
        self.decisions[hid][field_name] = d

        rec = self.coords[hid]
        if field_name == 'location_desc' and _squash(str(before or '')) != _squash(str(new or '')):
            # 位置描述变了，旧坐标作废，需要重新推断或点选
            self.coords[hid] = CoordinateRecord(failure='location_changed', attempts=rec.attempts)
        elif field_name in _GEOMETRY_FIELDS and rec.ok:
            rec.end = self._end_for(hole, rec.start)
        return d

    def _pick_source(self, ev: Optional[FieldEvidence], f: str, value: Any,
                     candidate_index: Optional[int]) -> Tuple[Any, Optional[EvidenceAnchor]]:
        if ev is None or (not ev.anchors and not ev.candidates):
            raise ReviewError(f'{f} 在原文中没有可采用的出处')
        norm = EvidenceAligner._norm
        if candidate_index is not None:
            if not 0 <= candidate_index < len(ev.candidates):
                raise ReviewError(f'候选序号越界：{candidate_index}')
            target = ev.candidates[candidate_index]
        elif value is not None:
            target = norm(f, str(value))
        else:
            raise ReviewError('采用原文值需要提供 value 或 candidate_index')
        for a in ev.anchors:
            if norm(f, a.text) == target:
                return _coerce(f, a.text), a
        if target in ev.candidates:
            return _coerce(f, target), None
        raise ReviewError(f'{value!r} 不是 {f} 在原文中的出处之一')

    # ── 坐标 ──
    def _end_for(self, hole: DrillHoleEntity, start: Coordinate) -> Optional[Coordinate]:
        inf = self.inferencer
        if inf is not None and hasattr(inf, 'end_coordinate_for'):
            return inf.end_coordinate_for(hole, start)
        p, d = hole.actual_params, hole.design_params
        for az, inc, dep in ((getattr(p, 'actual_azimuth', None), getattr(p, 'actual_inclination', None), getattr(p, 'actual_depth', None)),
                             (getattr(d, 'design_azimuth', None), getattr(d, 'design_inclination', None), getattr(d, 'design_depth', None))):
            if None not in (az, inc, dep):
                x, y, z = calculate_drill_hole_endpoint(start.x, start.y, start.z, az, inc, dep)
                return Coordinate(x, y, z, start.confidence * 0.9, f'{start.method}_calculated')
        return None

    def reinfer(self, hid: str, inferencer: Any = None) -> CoordinateRecord:
        """按当前位置描述重新推断坐标；传入另一个推断器即「换模型重算」"""
        hole = self._hole(hid)
        self._ensure_open(hid)
        inf = inferencer or self.inferencer
        if inf is None:
            raise ReviewError('没有可用的坐标推断器')
        coords, reason, _info = inf.infer_hole(hole)
        model = _model_name(inf)
        attempts = self.coords[hid].attempts + [{'model': model, 'ok': bool(coords), 'failure': reason,
                                                  'location_desc': hole.location_desc}]
        if coords and coords.get('start') is not None:
            rec = CoordinateRecord(coords['start'], coords.get('end'), 'inferred', model, None, attempts)
        else:
            rec = CoordinateRecord(failure=reason or 'start_coordinate_failed', attempts=attempts)
        self.coords[hid] = rec
        return rec

    def set_manual_coordinate(self, hid: str, x: float, y: float, z: float) -> CoordinateRecord:
        """三维中点选开孔位置"""
        hole = self._hole(hid)
        self._ensure_open(hid)
        start = Coordinate(float(x), float(y), float(z), confidence=1.0, method='manual_pick')
        rec = CoordinateRecord(start, self._end_for(hole, start), 'manual_pick', None, None,
                               self.coords[hid].attempts + [{'model': None, 'ok': True, 'failure': None, 'manual': True}])
        self.coords[hid] = rec
        return rec

    # ── 孔状态 ──
    def confirm(self, hid: str) -> None:
        self._hole(hid)
        self._ensure_open(hid)
        reasons = self.blockers(hid)
        if reasons:
            raise ReviewError(f'{hid} 还有未处理项，不能确认', reasons)
        self.state[hid] = HoleState.CONFIRMED

    def skip(self, hid: str, reason: str = '') -> None:
        self._hole(hid)
        self.state[hid] = HoleState.SKIPPED
        self.skip_reason[hid] = reason or (self.coords[hid].failure or '')

    def reopen(self, hid: str) -> None:
        self._hole(hid)
        self.state[hid] = HoleState.REVIEWING
        self.skip_reason.pop(hid, None)

    # ── 输出 ──
    def hole_summary(self, hid: str) -> Dict[str, Any]:
        """孔列表一行需要的信息"""
        pend = self.pending(hid)
        by = {s.value: 0 for s in (EvidenceStatus.CONFLICT, EvidenceStatus.AMBIGUOUS,
                                   EvidenceStatus.UNLABELED, EvidenceStatus.NO_SOURCE)}
        for e in self.evidence(hid):
            if e.field in pend:
                by[e.status.value] += 1
        return {'hole_id': hid, 'state': self.state[hid].value, 'pending': by,
                'coordinate': self.coords[hid].to_dict(), 'can_confirm': not self.blockers(hid),
                'skip_reason': self.skip_reason.get(hid)}

    def _provenance(self, hid: str) -> Dict[str, Any]:
        out = {}
        for e in self.evidence(hid):
            if e.field == 'hole_id':
                continue
            d = self.decisions[hid].get(e.field)
            out[e.field] = {'status': e.status.value, 'model_value': self.model_values[hid][e.field],
                            'anchors': [a.to_dict() for a in e.anchors],
                            'decision': d.to_dict() if d else None}
        return out

    def commit_plan(self) -> Dict[str, Any]:
        """入库清单；只有已确认的孔进入 commit"""
        commit, skipped, unreviewed = [], [], []
        for hid in self.order:
            st = self.state[hid]
            if st is HoleState.CONFIRMED:
                h = self.holes[hid]
                commit.append({'hole_id': hid,
                               'fields': {f: _get_field(h, f) for f in REVIEW_FIELDS},
                               'design_purpose': getattr(h.design_params, 'design_purpose', None) if h.design_params else None,
                               'coordinate': self.coords[hid].to_dict(),
                               'provenance': self._provenance(hid)})
            elif st is HoleState.SKIPPED:
                skipped.append({'hole_id': hid, 'reason': self.skip_reason.get(hid, '')})
            else:
                unreviewed.append(hid)
        return {'source_sha1': self.report.source_sha1, 'model': self.model_name,
                'commit': commit, 'skipped': skipped, 'unreviewed': unreviewed}

    def to_dict(self) -> Dict[str, Any]:
        return {'source_sha1': self.report.source_sha1, 'model': self.model_name,
                'holes': [self.hole_summary(h) for h in self.order],
                'evidence': self.report.to_dict()}
