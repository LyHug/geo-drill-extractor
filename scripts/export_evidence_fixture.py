#!/usr/bin/env python3
"""
重新生成前端契约样例：web/evidence-review/fixtures/report.json

后端 EvidenceAligner 的输出格式变了时运行本脚本，再跑
``node --test web/evidence-review/`` 确认前端仍能正确读取。
tests/unit/test_frontend_contract.py 会检查样例是否过期。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'web' / 'evidence-review' / 'fixtures'


def build() -> dict:
    sys.path.insert(0, str(ROOT / 'src'))
    from extraction.evidence_aligner import EvidenceAligner
    text = (FIX / 'source.md').read_text(encoding='utf-8')
    holes = json.loads((FIX / 'holes.json').read_text(encoding='utf-8'))
    return EvidenceAligner().align(text, holes).to_dict()


def main() -> int:
    (FIX / 'report.json').write_text(json.dumps(build(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'written {FIX / "report.json"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
