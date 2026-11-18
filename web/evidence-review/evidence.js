/**
 * 原文对照 · 前端证据渲染（无依赖 ES 模块）
 *
 * 输入是后端 EvidenceAligner 的输出（ProcessResult.metadata.evidence）和原文
 * （metadata.source_text）。本模块只做三件事：
 *   1. verifyReport   渲染前自检：原文长度、sha1、每个锚点切出来的文字都要和后端一致
 *   2. buildSegments  把一个孔的锚点切成互不重叠的片段（同一处可能同时是多个字段的出处）
 *   3. renderHtml     生成带 <mark> 的 HTML（已转义），交给 Vue 的 v-html 或自行渲染
 *
 * 偏移单位：后端按 Unicode 码点计（Python str 下标），JS 字符串按 UTF-16 计。
 * 原文含基本多文种平面以外的字（如「𠀋」）时两者不同，这里统一换算。
 */

export const STATUS_LABELS = {
  aligned: '有出处',
  ambiguous: '多个候选',
  unlabeled: '无标签',
  conflict: '与原文不符',
  no_source: '原文无出处',
  null: '模型返回空值',
};

/** 需要人处理的状态 */
export const PENDING_STATUSES = new Set(['ambiguous', 'unlabeled', 'conflict', 'no_source']);

/** 码点下标 → UTF-16 下标 的换算函数；原文没有代理对时直接返回原值 */
export function codePointIndexer(text) {
  if (!/[\uD800-\uDBFF]/.test(text)) return (i) => i;
  const map = [];
  let u = 0;
  for (const ch of text) {
    map.push(u);
    u += ch.length;
  }
  map.push(u);
  return (i) => (i >= 0 && i < map.length ? map[i] : -1);
}

export function codePointLength(text) {
  let n = 0;
  for (const _ of text) n++;
  return n;
}

export async function sha1Hex(text) {
  const buf = await globalThis.crypto.subtle.digest('SHA-1', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * 渲染前自检。返回 { ok, problems, badAnchors }；ok 为 false 时整份报告都不应高亮。
 * badAnchors 列出切出来的文字与后端不一致的锚点（{hole_id, field, anchor, got}）。
 */
export async function verifyReport(sourceText, report) {
  const problems = [];
  if (codePointLength(sourceText) !== report.source_length) {
    problems.push(`原文长度不一致：前端 ${codePointLength(sourceText)}，后端 ${report.source_length}`);
  }
  if ((await sha1Hex(sourceText)) !== report.source_sha1) {
    problems.push('原文 sha1 不一致：前端显示的不是送给模型的那份文本');
  }
  const toU = codePointIndexer(sourceText);
  const badAnchors = [];
  for (const f of report.fields) {
    for (const a of f.anchors) {
      const got = sourceText.slice(toU(a.start), toU(a.end));
      if (got !== a.text) badAnchors.push({ hole_id: f.hole_id, field: f.field, anchor: a, got });
    }
  }
  if (badAnchors.length) problems.push(`${badAnchors.length} 处锚点与原文不一致`);
  return { ok: problems.length === 0, problems, badAnchors };
}

/**
 * 给一个孔的字段编号：有出处的字段按出现顺序编号，原文高亮与字段列表共用这一份。
 * @param {Object<string, number>} [base] 已有编号（如界面固定的字段顺序），优先使用
 */
export function numberFields(fields, holeId, base = {}) {
  const numbering = { ...base };
  let next = Math.max(0, ...Object.values(numbering)) + 1;
  for (const f of fields) {
    if (f.hole_id === holeId && f.anchors.length && !(f.field in numbering)) numbering[f.field] = next++;
  }
  return numbering;
}

/**
 * 一个孔的高亮片段。
 * @param {string} sourceText
 * @param {object[]} fields      report.fields
 * @param {string} holeId
 * @param {object} [opts]
 * @param {Object<string, number>} [opts.numbering]  字段 → 编号（与字段列表一致）；缺省按出现顺序编号
 * @returns {{start:number,end:number,text:string,marks:{field:string,no:number,status:string,source:string}[]}[]}
 *          start/end 为 UTF-16 下标，覆盖全文、按顺序、互不重叠；marks 为空表示普通文字
 */
export function buildSegments(sourceText, fields, holeId, opts = {}) {
  const toU = codePointIndexer(sourceText);
  const numbering = numberFields(fields, holeId, opts.numbering);
  const spans = [];
  for (const f of fields) {
    if (f.hole_id !== holeId || !f.anchors.length) continue;
    for (const a of f.anchors) {
      const s = toU(a.start), e = toU(a.end);
      if (s < 0 || e < s || sourceText.slice(s, e) !== a.text) continue;   // 自检不过的锚点不画
      spans.push({ s, e, mark: { field: f.field, no: numbering[f.field], status: f.status, source: a.source } });
    }
  }
  // 扫描线切分：所有端点排序，相邻端点之间的区间带上覆盖它的全部 mark
  const cuts = new Set([0, sourceText.length]);
  spans.forEach((x) => { cuts.add(x.s); cuts.add(x.e); });
  const pts = [...cuts].sort((a, b) => a - b);
  const segs = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    if (a === b) continue;
    const marks = spans.filter((x) => x.s <= a && x.e >= b).map((x) => x.mark);
    const uniq = [...new Map(marks.map((m) => [`${m.field}|${m.source}`, m])).values()];
    const last = segs[segs.length - 1];
    if (last && !uniq.length && !last.marks.length) {
      last.end = b;
      last.text += sourceText.slice(a, b);
    } else {
      segs.push({ start: a, end: b, text: sourceText.slice(a, b), marks: uniq });
    }
  }
  return segs;
}

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

/** 状态优先级：同一处有多个字段时，按最需要注意的状态上色 */
const PRIORITY = ['conflict', 'no_source', 'ambiguous', 'unlabeled', 'aligned', 'null'];

/**
 * 生成 HTML。普通文字只转义；带 mark 的片段包成
 * <mark class="ev ev-{status}" data-fields="a b" data-no="3 6">…</mark>
 * 编号徽标、颜色由页面 CSS 决定（如 .ev-conflict { outline: 2px solid #e74c3c }）。
 */
export function renderHtml(segments) {
  return segments.map((seg) => {
    const text = esc(seg.text);
    if (!seg.marks.length) return text;
    const status = PRIORITY.find((p) => seg.marks.some((m) => m.status === p)) || seg.marks[0].status;
    const fields = [...new Set(seg.marks.map((m) => m.field))];
    const nos = [...new Set(seg.marks.map((m) => m.no))];
    return `<mark class="ev ev-${esc(status)}" data-fields="${esc(fields.join(' '))}" data-no="${esc(nos.join(' '))}" title="${esc(STATUS_LABELS[status] || status)}">${text}</mark>`;
  }).join('').replace(/\n/g, '<br>');
}

/** 字段列表一行：编号、状态文案、是否待处理 */
export function fieldRows(fields, holeId, base = {}) {
  const numbering = numberFields(fields, holeId, base);
  return fields.filter((f) => f.hole_id === holeId).map((f) => ({
    field: f.field,
    no: numbering[f.field] ?? null,
    status: f.status,
    label: STATUS_LABELS[f.status] || f.status,
    pending: PENDING_STATUSES.has(f.status),
    value: f.value,
    candidates: f.candidates,
  }));
}
