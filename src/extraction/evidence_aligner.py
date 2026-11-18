"""
证据回链模块 - 把抽取出的每个字段锚回原文

在实体抽取之后运行，不调用 LLM、不改提示词。输入是送给模型的同一份 markdown
（``DocumentProcessor`` 的输出）和抽取出的钻孔实体；输出每个字段在原文中的出处
（字符区间）和核验状态，供前端高亮与人工核对。

判定规则（"孔范围 + 标签"）：

* 孔范围 = 正文中 ``N．<孔号>钻孔`` 段落到下一个孔号段落/章节标题，
  ∪ 参数表中孔号列等于该孔的行，∪ 落在该孔段落内的「字段 | 设计 | 实际」转置表。
* 只在孔范围内找出处；带标签（如「设计方位：」、表头「终孔孔深」）的出处才算有效出处。

状态：

``aligned``    带标签出处的值与模型值一致（数值型字段且只有一个不同值）
``ambiguous``  带标签出处有多个不同值，模型值是其中之一
``unlabeled``  没有该字段的标签，只在孔范围里找到同一个数/串
``conflict``   带标签出处存在，但值与模型值不同
``no_source``  孔范围内完全找不到
``null``       模型返回空值，不评

偏移单位：``start`` / ``end`` 是 Unicode 码点下标（即 Python ``str`` 下标），不是 UTF-16 下标。
前端（JS 字符串按 UTF-16 计）须换算，见 ``web/evidence-review/evidence.js`` 的 ``codePointIndexer``。

局限：标签规则针对现有钻孔竣工报告的写法；字符串字段（位置描述、地层）只做
去空白后的严格相等比较，同义缩写（如「本灰」/「本溪灰岩」）会被判为不符。
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


class EvidenceStatus(str, Enum):
    """字段核验状态"""
    ALIGNED = "aligned"
    AMBIGUOUS = "ambiguous"
    UNLABELED = "unlabeled"
    CONFLICT = "conflict"
    NO_SOURCE = "no_source"
    NULL = "null"


@dataclass(frozen=True)
class EvidenceAnchor:
    """原文中的一处出处：``text == source_text[start:end]``"""
    start: int
    end: int
    text: str
    source: str                 # 'text' 正文 | 'table' 表格
    label: Optional[str] = None  # 命中的标签或列名

    def to_dict(self) -> Dict[str, Any]:
        return {'start': self.start, 'end': self.end, 'text': self.text,
                'source': self.source, 'label': self.label}


@dataclass
class FieldEvidence:
    """单个字段的核验结果"""
    hole_id: str
    field: str
    value: Any
    status: EvidenceStatus
    anchors: List[EvidenceAnchor] = field(default_factory=list)
    candidates: List[Any] = field(default_factory=list)   # 原文中带标签出处的不同取值

    def to_dict(self) -> Dict[str, Any]:
        return {'hole_id': self.hole_id, 'field': self.field, 'value': self.value,
                'status': self.status.value, 'anchors': [a.to_dict() for a in self.anchors],
                'candidates': list(self.candidates)}


@dataclass
class EvidenceReport:
    """一份文档的核验结果"""
    fields: List[FieldEvidence]
    source_length: int
    source_sha1: str   # 前端据此确认自己渲染的是同一份文本

    def summary(self) -> Dict[str, int]:
        c = Counter(f.status.value for f in self.fields)
        return {s.value: c.get(s.value, 0) for s in EvidenceStatus}

    def for_hole(self, hole_id: str) -> List[FieldEvidence]:
        return [f for f in self.fields if f.hole_id == hole_id]

    def get(self, hole_id: str, field_name: str) -> Optional[FieldEvidence]:
        for f in self.fields:
            if f.hole_id == hole_id and f.field == field_name:
                return f
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {'source_length': self.source_length, 'source_sha1': self.source_sha1,
                'summary': self.summary(), 'fields': [f.to_dict() for f in self.fields]}


# ───────────────────────── 规则 ─────────────────────────

NUM = r'[+\-−－]?\d+(?:\.\d+)?'

NUMERIC_FIELDS = (
    'design_depth', 'design_azimuth', 'design_inclination', 'design_diameter',
    'actual_depth', 'actual_azimuth', 'actual_inclination', 'actual_diameter',
)
STRING_FIELDS = ('location_desc', 'start_formation', 'end_formation')
DATE_FIELDS = ('drilling_date',)
CHECKED_FIELDS = ('hole_id', 'location_desc') + NUMERIC_FIELDS + ('start_formation', 'end_formation', 'drilling_date')

_DATE_ZH = r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'

# 正文标签：字段 -> [(正则, 标签名)]；正则的第 1 组是值
TEXT_LABELS: Dict[str, List[Tuple[str, str]]] = {
    'location_desc':      [(r'设计位置[：:]\s*([^；;。，,\n|]+?)\s*(?=[；;。，,\n|]|$)', '设计位置')],
    'design_depth':       [(r'设计孔深[：:]\s*(' + NUM + ')', '设计孔深')],
    'design_azimuth':     [(r'设计方位角?[：:]\s*(' + NUM + ')', '设计方位')],
    'design_inclination': [(r'设计倾角[：:]\s*(' + NUM + ')', '设计倾角')],
    'design_diameter':    [(r'设计孔径[：:]?\s*(' + NUM + ')', '设计孔径')],
    'actual_depth':       [(r'(?:钻进|钻)至\s*(' + NUM + r')\s*m\s*位置终孔', '终孔'),
                           (r'终孔(?:孔深|深度)[：:]?\s*(' + NUM + ')', '终孔深度')],
    'actual_azimuth':     [(r'实际方位角?[：:]?\s*(' + NUM + ')', '实际方位')],
    'actual_inclination': [(r'(?<!设计)倾角[：:]?\s*(' + NUM + r')\s*°', '实际倾角')],
    'actual_diameter':    [(r'[φΦ]\s*(' + NUM + r')\s*mm\s*钻头', '钻头直径')],
    'drilling_date':      [('(' + _DATE_ZH + r')\s*[早中晚夜]?班?\s*(?:开孔|施工结束|终孔|完成)', '日期')],
}

# 表头（多行表头会先合并）-> 字段；按顺序取第一个命中
COL_MAP: List[Tuple[str, str]] = [
    (r'孔号|钻孔编号|孔编号', 'hole_id'),
    (r'设计.*孔深|孔深.*设计|设计.*深度', 'design_depth'),
    (r'设计.*方位|方位.*设计', 'design_azimuth'),
    (r'设计.*倾角|倾角.*设计', 'design_inclination'),
    (r'设计.*孔径|孔径.*设计', 'design_diameter'),
    (r'终孔.*深|累计孔深|实际.*孔深|孔深.*实际|^孔深|^深度', 'actual_depth'),
    (r'方位', 'actual_azimuth'),
    (r'倾角', 'actual_inclination'),
    (r'孔径', 'actual_diameter'),
    (r'开孔(?:位置|层位)', 'start_formation'),
    (r'终孔(?:层位|位置)', 'end_formation'),
    (r'钻探位置|施工地点|设计位置', 'location_desc'),
]
_SKIP_COLS = re.compile(r'单位|备注|说明')
_SECTION = re.compile(r'^\s*(?:#+\s*)?[一二三四五六七八九十]+、')
# 通用孔段落标题：「1．T1-1钻孔」「2.补1号钻孔」「SYN-303C-01钻孔」
_HOLE_HEAD = re.compile(r'^\s*(?:\d+\s*[．.、]\s*)?[一-龥]{0,2}[A-Za-z0-9][A-Za-z0-9\-－_#/ ]*?\s*号?\s*钻孔')


def _map_col(header: str) -> Optional[str]:
    h = re.sub(r'\s+', '', header)
    if not h or _SKIP_COLS.search(h):
        return None
    for pat, f in COL_MAP:
        if re.search(pat, h):
            return f
    return None


def _squash(s: str) -> str:
    return re.sub(r'\s+', '', s)


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s.replace('−', '-').replace('－', '-').replace('+', ''))
    except (ValueError, AttributeError):
        return None


def _norm_date(v: Any) -> Optional[str]:
    """'2020-6-1' / '2020.06.01' / '2020年6月1日' -> '2020-06-01'"""
    if v is None:
        return None
    m = re.search(r'(\d{4})\s*[-./年]\s*(\d{1,2})\s*[-./月]\s*(\d{1,2})', str(v))
    return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else None


# ───────────────────────── 文本结构 ─────────────────────────

@dataclass
class _Cell:
    start: int
    end: int
    text: str


@dataclass
class _Table:
    line_from: int            # 首行行号
    line_to: int              # 末行行号（含）
    headers: List[str]        # 合并后的表头
    rows: List[List[_Cell]]   # 数据行


class _Doc:
    """按行切分并记录每行起始偏移，解析表格"""

    def __init__(self, text: str):
        self.text = text
        self.lines = text.split('\n')
        self.offsets, pos = [], 0
        for ln in self.lines:
            self.offsets.append(pos)
            pos += len(ln) + 1
        self.tables = self._parse_tables()
        self.table_lines = {i for t in self.tables for i in range(t.line_from, t.line_to + 1)}

    def _cells(self, i: int) -> List[_Cell]:
        ln, base = self.lines[i], self.offsets[i]
        pipes = [k for k, ch in enumerate(ln) if ch == '|']
        cells = []
        for a, b in zip(pipes, pipes[1:]):
            raw = ln[a + 1:b]
            lead = len(raw) - len(raw.lstrip())
            txt = raw.strip()
            s = base + a + 1 + lead
            cells.append(_Cell(s, s + len(txt), txt))
        return cells

    def _parse_tables(self) -> List[_Table]:
        tables, i, n = [], 0, len(self.lines)
        while i < n:
            if not self.lines[i].lstrip().startswith('|'):
                i += 1
                continue
            j = i
            rows: List[List[_Cell]] = []
            while j < n and self.lines[j].lstrip().startswith('|'):
                if not re.fullmatch(r'[\s|:\-]*', self.lines[j]):
                    rows.append(self._cells(j))
                j += 1
            if rows:
                headers = [c.text for c in rows[0]]
                data = rows[1:]
                # 多行表头：第二行只有「设计/实际」之类、没有数字 → 合并进表头
                if data and any(re.search(r'设计|实际', c.text) for c in data[0]) \
                        and not any(re.search(r'\d', c.text) for c in data[0]):
                    sub = data[0]
                    headers = [h + (sub[k].text if k < len(sub) else '') for k, h in enumerate(headers)]
                    data = data[1:]
                tables.append(_Table(i, j - 1, headers, data))
            i = j
        return tables


@dataclass
class _Scope:
    """一个孔的出处范围"""
    text_ranges: List[Tuple[int, int]] = field(default_factory=list)   # 正文段落（字符区间，不含表格行）
    id_anchors: List[EvidenceAnchor] = field(default_factory=list)
    labelled_cells: List[Tuple[str, str, _Cell]] = field(default_factory=list)  # (字段, 列名, 单元格)
    pool_cells: List[_Cell] = field(default_factory=list)              # 孔范围内全部单元格

    @property
    def empty(self) -> bool:
        return not self.text_ranges and not self.pool_cells


# ───────────────────────── 主类 ─────────────────────────

class EvidenceAligner:
    """
    证据回链

    用法::

        report = EvidenceAligner().align(markdown_text, drill_holes)
        report.get('T1-2', 'location_desc').status   # EvidenceStatus.CONFLICT
    """

    def align(self, text: str, holes: Sequence[Any]) -> EvidenceReport:
        """
        Args:
            text: ``DocumentProcessor`` 输出的 markdown（必须是送给模型的同一份文本）
            holes: ``DrillHoleEntity`` 列表，或同结构的 dict 列表
        """
        doc = _Doc(text)
        hole_dicts = [self._as_dict(h) for h in holes]
        ids = [h['hole_id'] for h in hole_dicts if h.get('hole_id')]
        scopes = self._build_scopes(doc, ids)

        results: List[FieldEvidence] = []
        for h in hole_dicts:
            hid = h.get('hole_id')
            if not hid:
                continue
            scope = scopes.get(hid, _Scope())
            for f in CHECKED_FIELDS:
                results.append(self._check(doc, scope, hid, f, h.get(f)))

        results = [self._verify(text, r) for r in results]
        return EvidenceReport(results, len(text), hashlib.sha1(text.encode('utf-8')).hexdigest())

    # ── 输入归一 ──
    @staticmethod
    def _as_dict(h: Any) -> Dict[str, Any]:
        if isinstance(h, dict):
            d = {'hole_id': h.get('hole_id'), 'location_desc': h.get('location_desc')}
            d.update(h.get('design_params') or {})
            d.update(h.get('actual_params') or {})
            return d
        d = {'hole_id': getattr(h, 'hole_id', None), 'location_desc': getattr(h, 'location_desc', None)}
        for part in ('design_params', 'actual_params'):
            p = getattr(h, part, None)
            if p is not None:
                d.update({k: v for k, v in vars(p).items()})
        return d

    # ── 孔范围 ──
    def _build_scopes(self, doc: _Doc, ids: List[str]) -> Dict[str, _Scope]:
        scopes = {hid: _Scope() for hid in ids}
        key = {_squash(hid).upper(): hid for hid in ids}

        # 正文段落起点：「N．<孔号>钻孔」
        starts: List[Tuple[int, str, int, int]] = []   # (行号, 孔号, id 起, id 止)
        for i, ln in enumerate(doc.lines):
            if i in doc.table_lines:
                continue
            for hid in ids:
                m = re.match(r'^\s*(?:\d+\s*[．.、]\s*)?(' + re.escape(hid) + r')\s*号?\s*钻孔', ln)
                if m:
                    base = doc.offsets[i]
                    starts.append((i, hid, base + m.start(1), base + m.end(1)))
        starts.sort()
        # 段落边界：任何「N．<孔号>钻孔」开头的行（含模型漏抽的孔），避免漏抽的孔被前一个孔的段落吞掉
        bounds = sorted({i for i, ln in enumerate(doc.lines)
                         if i not in doc.table_lines and _HOLE_HEAD.match(ln)} | {s[0] for s in starts})
        seg_lines: Dict[str, List[Tuple[int, int]]] = {}
        for i, hid, s, e in starts:
            end = next((b for b in bounds if b > i), len(doc.lines))
            for j in range(i + 1, end):
                if _SECTION.match(doc.lines[j]):
                    end = j
                    break
            seg_lines.setdefault(hid, []).append((i, end))
            scopes[hid].id_anchors.append(EvidenceAnchor(s, e, doc.text[s:e], 'text', '段落标题'))
            # 段落内的非表格行 → 正文区间
            for j in range(i, end):
                if j not in doc.table_lines:
                    a = doc.offsets[j]
                    scopes[hid].text_ranges.append((a, a + len(doc.lines[j])))

        for t in doc.tables:
            cols = [_map_col(h) for h in t.headers]
            id_col = cols.index('hole_id') if 'hole_id' in cols else None
            transposed = id_col is None and len(t.headers) >= 3 and \
                any('设计' in h for h in t.headers) and any('实际' in h for h in t.headers)
            if transposed:
                # 「字段 | 设计 | 实际 | 单位」：归属于包含它的孔段落
                owner = next((hid for hid, segs in seg_lines.items()
                              for a, b in segs if a <= t.line_from < b), None)
                if owner is None:
                    continue
                for row in t.rows:
                    if not row:
                        continue
                    for k in range(1, len(row)):
                        hdr = t.headers[k] if k < len(t.headers) else ''
                        f = _map_col(row[0].text + hdr)
                        scopes[owner].pool_cells.append(row[k])
                        if f and f != 'hole_id':
                            scopes[owner].labelled_cells.append((f, row[0].text + '/' + hdr, row[k]))
                continue
            for row in t.rows:
                # 找出这一行属于哪个孔：孔号列，或任一单元格等于孔号
                cand = [row[id_col]] if id_col is not None and id_col < len(row) else row
                owner = None
                for c in cand:
                    owner = key.get(_squash(c.text).upper())
                    if owner:
                        id_cell = c
                        break
                if not owner:
                    continue
                sc = scopes[owner]
                sc.id_anchors.append(EvidenceAnchor(id_cell.start, id_cell.end, id_cell.text, 'table', '孔号'))
                for k, c in enumerate(row):
                    sc.pool_cells.append(c)
                    f = cols[k] if k < len(cols) else None
                    if f and f != 'hole_id':
                        sc.labelled_cells.append((f, t.headers[k], c))
        return scopes

    # ── 单字段判定 ──
    def _check(self, doc: _Doc, scope: _Scope, hid: str, f: str, value: Any) -> FieldEvidence:
        if f == 'hole_id':
            if scope.id_anchors:
                return FieldEvidence(hid, f, value, EvidenceStatus.ALIGNED, list(scope.id_anchors))
            return FieldEvidence(hid, f, value, EvidenceStatus.NO_SOURCE)
        if value is None or (isinstance(value, str) and not value.strip()):
            return FieldEvidence(hid, f, value, EvidenceStatus.NULL)

        if f in NUMERIC_FIELDS:
            v = _to_float(str(value)) if not isinstance(value, (int, float)) else float(value)
            if v is None:
                return FieldEvidence(hid, f, value, EvidenceStatus.NO_SOURCE)
            norm: Callable[[str], Any] = lambda s: (None if _to_float(s) is None else round(_to_float(s), 6))
            target = round(v, 6)
        elif f in DATE_FIELDS:
            norm, target = _norm_date, _norm_date(value)
            if target is None:
                return FieldEvidence(hid, f, value, EvidenceStatus.NO_SOURCE)
        else:
            norm, target = _squash, _squash(str(value))

        labelled = self._labelled(doc, scope, f)          # [(anchor, 归一值)]
        labelled = [(a, nv) for a, nv in labelled if nv is not None]
        if labelled:
            hits = [a for a, nv in labelled if nv == target]
            uniq = {nv for _, nv in labelled}
            distinct = sorted(uniq) if all(isinstance(x, float) for x in uniq) else sorted(uniq, key=str)
            if hits:
                typed = f in NUMERIC_FIELDS or f in DATE_FIELDS
                st = EvidenceStatus.AMBIGUOUS if typed and len(distinct) > 1 else EvidenceStatus.ALIGNED
                anchors = [a for a, _ in labelled] if st is EvidenceStatus.AMBIGUOUS else hits
                return FieldEvidence(hid, f, value, st, anchors, distinct if st is EvidenceStatus.AMBIGUOUS else [])
            multi = self._multi_valued_location(doc, f, target, labelled)
            if multi:
                return FieldEvidence(hid, f, value, EvidenceStatus.AMBIGUOUS, multi, distinct)
            return FieldEvidence(hid, f, value, EvidenceStatus.CONFLICT, [a for a, _ in labelled], distinct)

        loose = self._loose(doc, scope, f, target, norm)
        if loose:
            return FieldEvidence(hid, f, value, EvidenceStatus.UNLABELED, loose)
        return FieldEvidence(hid, f, value, EvidenceStatus.NO_SOURCE)

    def _labelled(self, doc: _Doc, scope: _Scope, f: str) -> List[Tuple[EvidenceAnchor, Any]]:
        out: List[Tuple[EvidenceAnchor, Any]] = []
        for pat, label in TEXT_LABELS.get(f, []):
            for a, b in scope.text_ranges:
                for m in re.finditer(pat, doc.text[a:b]):
                    s, e = a + m.start(1), a + m.end(1)
                    raw = doc.text[s:e]
                    out.append((EvidenceAnchor(s, e, raw, 'text', label), self._norm(f, raw)))
        for ff, hdr, c in scope.labelled_cells:
            if ff != f or not c.text:
                continue
            if f in NUMERIC_FIELDS:
                m = re.search(NUM, c.text)
                if not m:
                    continue
                s, e = c.start + m.start(), c.start + m.end()
            else:
                s, e = c.start, c.end
            out.append((EvidenceAnchor(s, e, doc.text[s:e], 'table', hdr), self._norm(f, doc.text[s:e])))
        return out

    @staticmethod
    def _multi_valued_location(doc: _Doc, f: str, target: str,
                               labelled: List[Tuple[EvidenceAnchor, Any]]) -> List[EvidenceAnchor]:
        """一格里写了多个位置（如「…左侧方向 …右侧方向」），模型值是其中之一 → 返回它在格内的子区间"""
        if f != 'location_desc' or not target:
            return []
        out = []
        for a, nv in labelled:
            if a.source != 'table' or len(re.findall(r'\d+\s*#?\s*点', nv)) < 2 or target not in nv:
                continue
            idx = [k for k, ch in enumerate(a.text) if not ch.isspace()]
            p = ''.join(a.text[k] for k in idx).find(target)
            s, e = a.start + idx[p], a.start + idx[p + len(target) - 1] + 1
            out.append(EvidenceAnchor(s, e, doc.text[s:e], 'table', a.label))
        return out

    @staticmethod
    def _norm(f: str, raw: str) -> Any:
        if f in NUMERIC_FIELDS:
            v = _to_float(raw)
            return None if v is None else round(v, 6)
        if f in DATE_FIELDS:
            return _norm_date(raw)
        return _squash(raw)

    def _loose(self, doc: _Doc, scope: _Scope, f: str, target: Any, norm: Callable) -> List[EvidenceAnchor]:
        """无标签时：在孔范围内找同一个数/串"""
        spans: List[Tuple[int, int, str]] = [(a, b, 'text') for a, b in scope.text_ranges]
        spans += [(c.start, c.end, 'table') for c in scope.pool_cells]
        found: List[EvidenceAnchor] = []
        for a, b, src in spans:
            seg = doc.text[a:b]
            if f in NUMERIC_FIELDS:
                for m in re.finditer(NUM, seg):
                    # 跳过嵌在更长数字/编号里的片段（如 '12#' 中的数字照样算，'T1-2' 中的 '-2' 不算）
                    if m.start() > 0 and re.match(r'[A-Za-z0-9.]', seg[m.start() - 1]):
                        continue
                    if norm(m.group(0)) == target:
                        found.append(EvidenceAnchor(a + m.start(), a + m.end(), m.group(0), src))
            elif f in DATE_FIELDS:
                for m in re.finditer(_DATE_ZH, seg):
                    if _norm_date(m.group(0)) == target:
                        found.append(EvidenceAnchor(a + m.start(), a + m.end(), m.group(0), src))
            else:
                if not target:
                    continue
                # 去空白后比较：在去空白的段落里找，再映射回原偏移
                idx = [k for k, ch in enumerate(seg) if not ch.isspace()]
                flat = ''.join(seg[k] for k in idx)
                p = flat.find(target)
                while p != -1:
                    s, e = a + idx[p], a + idx[p + len(target) - 1] + 1
                    found.append(EvidenceAnchor(s, e, doc.text[s:e], src))
                    p = flat.find(target, p + 1)
        return found

    # ── 自检：出处必须与原文逐字一致，带标签的一致项必须真的相等 ──
    def _verify(self, text: str, r: FieldEvidence) -> FieldEvidence:
        bad = [a for a in r.anchors if not (0 <= a.start <= a.end <= len(text)) or text[a.start:a.end] != a.text]
        if bad:
            logger.error(f"证据锚点与原文不一致，降级为 no_source: {r.hole_id}.{r.field} {bad[:1]}")
            return FieldEvidence(r.hole_id, r.field, r.value, EvidenceStatus.NO_SOURCE)
        if r.status is EvidenceStatus.ALIGNED and r.field in NUMERIC_FIELDS:
            v = float(r.value)
            vals = [_to_float(a.text) for a in r.anchors]
            if not all(x is not None and abs(x - v) < 1e-6 for x in vals):
                logger.error(f"对齐值校验失败，降级为 no_source: {r.hole_id}.{r.field}")
                return FieldEvidence(r.hole_id, r.field, r.value, EvidenceStatus.NO_SOURCE)
        return r


def summarize(reports: Iterable[EvidenceReport]) -> Dict[str, int]:
    """多份文档的状态合计"""
    total: Counter = Counter()
    for rep in reports:
        total.update(rep.summary())
    return {s.value: total.get(s.value, 0) for s in EvidenceStatus}
