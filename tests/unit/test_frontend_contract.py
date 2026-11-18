"""
前后端契约：web/evidence-review/fixtures/report.json 必须与当前 EvidenceAligner 的输出一致。
失败时运行 ``python scripts/export_evidence_fixture.py`` 重新生成，再跑 ``node --test web/evidence-review/``。
"""
import json
from pathlib import Path

from extraction.evidence_aligner import EvidenceAligner

FIX = Path(__file__).resolve().parents[2] / 'web' / 'evidence-review' / 'fixtures'


def test_fixture_report_is_up_to_date():
    text = (FIX / 'source.md').read_text(encoding='utf-8')
    holes = json.loads((FIX / 'holes.json').read_text(encoding='utf-8'))
    current = json.loads(json.dumps(EvidenceAligner().align(text, holes).to_dict(), ensure_ascii=False))
    assert current == json.loads((FIX / 'report.json').read_text(encoding='utf-8'))


def test_fixture_contains_non_bmp_character():
    # 前端按 UTF-16 下标切字符串，样例必须覆盖码点/UTF-16 不一致的情况
    text = (FIX / 'source.md').read_text(encoding='utf-8')
    assert any(ord(ch) > 0xFFFF for ch in text)
