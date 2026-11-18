// node --test web/evidence-review/
// 样例由 scripts/export_evidence_fixture.py 用后端 EvidenceAligner 生成；原文标题含扩展区汉字「𠀋」（U+2000B）
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  verifyReport, buildSegments, renderHtml, fieldRows, numberFields,
  codePointIndexer, codePointLength, sha1Hex,
} from './evidence.js';

const dir = new URL('./fixtures/', import.meta.url);
const source = readFileSync(new URL('source.md', dir), 'utf8');
const report = JSON.parse(readFileSync(new URL('report.json', dir), 'utf8'));
const field = (h, f) => report.fields.find((x) => x.hole_id === h && x.field === f);

test('样例原文含代理对，码点长度与 UTF-16 长度不同', () => {
  assert.ok(source.includes('𠀋'));
  assert.equal(codePointLength(source), report.source_length);
  assert.equal(source.length, report.source_length + 1);
});

test('码点下标换算', () => {
  const toU = codePointIndexer('a𠀋b');
  assert.deepEqual([0, 1, 2, 3].map(toU), [0, 1, 3, 4]);
  assert.equal(codePointIndexer('abc')(2), 2);
});

test('后端报告在前端自检通过', async () => {
  const r = await verifyReport(source, report);
  assert.deepEqual(r.problems, []);
  assert.equal(r.ok, true);
});

test('sha1 与 Python hashlib 一致（UTF-8）', async () => {
  assert.equal(await sha1Hex(source), report.source_sha1);
});

test('原文被改动时自检失败并指出锚点', async () => {
  const tampered = source.replace('设计孔深：80m', '设计孔深：86m');
  const r = await verifyReport(tampered, report);
  assert.equal(r.ok, false);
  assert.ok(r.problems.some((p) => p.includes('sha1')));
  assert.ok(r.badAnchors.some((b) => b.field === 'design_depth' && b.got === '86'));
});

test('不按码点换算会切错（证明换算是必要的）', () => {
  const a = field('T1-1', 'design_depth').anchors[0];
  assert.notEqual(source.slice(a.start, a.end), a.text);
});

test('片段覆盖全文、按序、互不重叠', () => {
  const segs = buildSegments(source, report.fields, 'T1-1');
  assert.equal(segs.map((s) => s.text).join(''), source);
  for (let i = 1; i < segs.length; i++) assert.equal(segs[i].start, segs[i - 1].end);
});

test('同一处是多个字段的出处时合并为一个片段（φ108：设计孔径无标签 + 实际孔径多候选）', () => {
  const segs = buildSegments(source, report.fields, 'T1-1');
  const s108 = segs.filter((s) => s.text === '108' && s.marks.length);
  assert.ok(s108.some((s) => new Set(s.marks.map((m) => m.field)).size === 2));
});

test('只画本孔的锚点', () => {
  const segs = buildSegments(source, report.fields, 'T1-2');
  const marked = segs.filter((s) => s.marks.length);
  assert.ok(marked.length > 0);
  for (const s of marked) for (const m of s.marks) assert.ok(field('T1-2', m.field));
  // T1-2 的位置描述与原文不符
  assert.ok(marked.some((s) => s.marks.some((m) => m.field === 'location_desc' && m.status === 'conflict')));
});

test('与原文不一致的锚点不画', () => {
  const broken = structuredClone(report);
  const f = broken.fields.find((x) => x.hole_id === 'T1-1' && x.field === 'design_depth');
  f.anchors = f.anchors.map((a) => ({ ...a, text: '999' }));
  const segs = buildSegments(source, broken.fields, 'T1-1');
  assert.ok(!segs.some((s) => s.marks.some((m) => m.field === 'design_depth')));
});

test('原文高亮与字段列表编号一致', () => {
  const numbering = numberFields(report.fields, 'T1-1');
  const rows = fieldRows(report.fields, 'T1-1');
  const segs = buildSegments(source, report.fields, 'T1-1');
  for (const r of rows) {
    if (r.no == null) continue;
    assert.equal(r.no, numbering[r.field]);
    for (const s of segs) for (const m of s.marks) if (m.field === r.field) assert.equal(m.no, r.no);
  }
  assert.equal(rows.find((r) => r.field === 'actual_diameter').pending, true);
});

test('固定编号优先', () => {
  const segs = buildSegments(source, report.fields, 'T1-1', { numbering: { location_desc: 2, design_depth: 3 } });
  const m = segs.flatMap((s) => s.marks).find((x) => x.field === 'design_depth');
  assert.equal(m.no, 3);
});

test('HTML 转义并按最需要注意的状态上色', () => {
  const segs = [
    { start: 0, end: 3, text: '<b>', marks: [] },
    { start: 3, end: 6, text: '108', marks: [
      { field: 'design_diameter', no: 6, status: 'unlabeled', source: 'text' },
      { field: 'actual_diameter', no: 10, status: 'ambiguous', source: 'text' }] },
  ];
  const html = renderHtml(segs);
  assert.ok(html.startsWith('&lt;b&gt;'));
  assert.match(html, /class="ev ev-ambiguous"/);
  assert.match(html, /data-no="6 10"/);
});
