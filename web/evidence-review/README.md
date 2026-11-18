# evidence-review · 原文对照前端渲染

无依赖 ES 模块，供 webThree（Vue）里的「原文对照」卡片使用。数据来自后端
`ExtractionPipeline(enable_evidence_alignment=True)` 的 `metadata.evidence` 与 `metadata.source_text`。

```js
import { verifyReport, buildSegments, renderHtml, fieldRows } from './evidence.js';

const check = await verifyReport(sourceText, evidence);   // 渲染前自检：长度、sha1、逐锚点比对
if (!check.ok) showWarning(check.problems);                // 不一致时整份不高亮
const rows = fieldRows(evidence.fields, 'T1-2');          // 右栏字段列表（编号、状态、是否待处理）
const html = renderHtml(buildSegments(sourceText, evidence.fields, 'T1-2'));  // 原文高亮（已转义）
```

- 后端偏移按 Unicode 码点计，模块内部换算成 JS 的 UTF-16 下标。
- 同一处文字是多个字段的出处时合成一个 `<mark>`，`data-fields` / `data-no` 列出全部字段与编号，颜色取最需要注意的状态。
- 字段编号由 `numberFields` 统一分配，原文高亮和字段列表共用，保证两边编号一致。
- 样式类：`.ev-aligned` `.ev-ambiguous` `.ev-unlabeled` `.ev-conflict` `.ev-no_source`，由页面 CSS 定义。

测试：`node --test web/evidence-review/`（Node ≥ 18）。样例 `fixtures/report.json` 由
`python scripts/export_evidence_fixture.py` 从后端生成，`tests/unit/test_frontend_contract.py` 检查它是否过期。
