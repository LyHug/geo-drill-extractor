#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a small synthetic dataset for reproducibility (no confidential data).

Outputs (project-relative):
- documents_synthetic/*.docx
- data_synthetic/survey_points_synthetic.csv
- data_synthetic/ground_truth_annotations_synthetic.csv
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True)
class SyntheticHole:
    hole_id: str
    location_desc: str
    design_depth_m: float | None
    design_azimuth_deg: float | None
    design_inclination_deg: float | None
    actual_depth_m: float | None
    actual_azimuth_deg: float | None
    actual_inclination_deg: float | None


@dataclass(frozen=True)
class SyntheticDoc:
    filename: str
    title: str
    holes: list[SyntheticHole]


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_docx(path: Path, doc: SyntheticDoc) -> None:
    try:
        from docx import Document
    except Exception as e:
        raise RuntimeError(
            "python-docx is required to generate .docx files. "
            "Install with: pip install python-docx"
        ) from e

    path.parent.mkdir(parents=True, exist_ok=True)

    d = Document()
    d.add_heading(doc.title, level=1)
    d.add_paragraph("NOTE: This is synthetic (dummy) data for reproducibility.")
    d.add_paragraph("")

    for idx, hole in enumerate(doc.holes, start=1):
        d.add_heading(f"Drill hole {idx}", level=2)
        d.add_paragraph(f"钻孔编号：{hole.hole_id}")
        d.add_paragraph(f"位置描述：{hole.location_desc}")
        d.add_paragraph("设计参数：")
        d.add_paragraph(f"  设计深度(m)：{hole.design_depth_m}", style=None)
        d.add_paragraph(f"  设计方位角(°)：{hole.design_azimuth_deg}", style=None)
        d.add_paragraph(f"  设计倾角(°)：{hole.design_inclination_deg}", style=None)
        d.add_paragraph("实际参数：")
        d.add_paragraph(f"  实际深度(m)：{hole.actual_depth_m}", style=None)
        d.add_paragraph(f"  实际方位角(°)：{hole.actual_azimuth_deg}", style=None)
        d.add_paragraph(f"  实际倾角(°)：{hole.actual_inclination_deg}", style=None)
        d.add_paragraph("")

    d.save(path)


def generate(root: Path) -> dict[str, Path]:
    docs_dir = root / "documents_synthetic"
    data_dir = root / "data_synthetic"

    docs: list[SyntheticDoc] = [
        SyntheticDoc(
            filename="synthetic_doc_001.docx",
            title="Synthetic Borehole Report 001",
            holes=[
                SyntheticHole(
                    hole_id="ZK-SYN-001",
                    location_desc="轨道上山15#点前50m钻窝内",
                    design_depth_m=100.0,
                    design_azimuth_deg=90.0,
                    design_inclination_deg=-10.0,
                    actual_depth_m=98.0,
                    actual_azimuth_deg=92.0,
                    actual_inclination_deg=-11.0,
                ),
                SyntheticHole(
                    hole_id="ZK-SYN-002",
                    location_desc="CP12与CP13之间偏左5m处",
                    design_depth_m=60.0,
                    design_azimuth_deg=45.0,
                    design_inclination_deg=-5.0,
                    actual_depth_m=58.0,
                    actual_azimuth_deg=44.0,
                    actual_inclination_deg=-6.0,
                ),
            ],
        ),
        SyntheticDoc(
            filename="synthetic_doc_002.docx",
            title="Synthetic Borehole Report 002",
            holes=[
                SyntheticHole(
                    hole_id="ZK-SYN-003",
                    location_desc="15#点后30m处",
                    design_depth_m=80.0,
                    design_azimuth_deg=270.0,
                    design_inclination_deg=-12.0,
                    actual_depth_m=79.0,
                    actual_azimuth_deg=268.0,
                    actual_inclination_deg=-12.0,
                ),
                SyntheticHole(
                    hole_id="ZK-SYN-004",
                    location_desc="CP12与CP13之间",
                    design_depth_m=40.0,
                    design_azimuth_deg=0.0,
                    design_inclination_deg=-3.0,
                    actual_depth_m=39.0,
                    actual_azimuth_deg=2.0,
                    actual_inclination_deg=-4.0,
                ),
            ],
        ),
    ]

    # Survey points (minimal)
    survey_points_file = data_dir / "survey_points_synthetic.csv"
    _write_csv(
        survey_points_file,
        rows=[
            {"FID": "15", "X": 4097000.0, "Y": 40000.0, "Z": -320.0, "name": "synthetic"},
            {"FID": "16", "X": 4097100.0, "Y": 40000.0, "Z": -320.0, "name": "synthetic"},
            {"FID": "CP12", "X": 4097000.0, "Y": 40100.0, "Z": -320.0, "name": "synthetic"},
            {"FID": "CP13", "X": 4097000.0, "Y": 40200.0, "Z": -320.0, "name": "synthetic"},
        ],
        fieldnames=["FID", "X", "Y", "Z", "name"],
    )

    # Ground truth (document-level counts only)
    gt_file = data_dir / "ground_truth_annotations_synthetic.csv"
    _write_csv(
        gt_file,
        rows=[
            {
                "document_filename": d.filename,
                "true_total_entities_count": len(d.holes),
                "true_entities_with_location_count": sum(1 for h in d.holes if h.location_desc),
            }
            for d in docs
        ],
        fieldnames=[
            "document_filename",
            "true_total_entities_count",
            "true_entities_with_location_count",
        ],
    )

    # Docs
    for d in docs:
        _write_docx(docs_dir / d.filename, d)

    return {
        "documents_dir": docs_dir,
        "survey_points_file": survey_points_file,
        "ground_truth_file": gt_file,
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    paths = generate(project_root)

    print("Synthetic dataset generated:")
    for k, v in paths.items():
        print(f"- {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

