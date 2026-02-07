#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run an incremental experiment with a small number of documents/repetitions.

Default: use the synthetic dataset (dummy data) to validate the full pipeline and
export artifacts (metrics CSV + failure-mode summaries) with minimal cost.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incremental experiment runner")
    parser.add_argument(
        "--dataset",
        choices=["synthetic", "real"],
        default="synthetic",
        help="Which dataset to use (default: synthetic)",
    )
    parser.add_argument(
        "--documents",
        type=int,
        default=1,
        help="Limit number of documents (default: 1)",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Repetitions per model-document pair (default: 1)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="gpt-3.5-turbo-openrouter,deepseek-r1-distill-qwen-7b-aliyun",
        help="Comma-separated model values (default: gpt-3.5 + deepseek-r1-7b)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    project_root = Path(__file__).resolve().parents[1]  # repo root
    os.chdir(project_root)

    src_path = project_root / "src"
    sys.path.insert(0, str(src_path))

    # Load config and override data paths if using synthetic dataset
    from core import get_config_loader, LLMModel
    from experiment import ExperimentRunner

    config_loader = get_config_loader()

    if args.dataset == "synthetic":
        dataset_root = project_root / "Supplementary" / "synthetic_dataset"
        docs_dir = dataset_root / "documents_zh"
        data_dir = dataset_root / "data"
        survey_points_file = data_dir / "survey_points_synthetic.csv"
        ground_truth_file = data_dir / "ground_truth_annotations_synthetic.csv"

        if not (docs_dir.exists() and survey_points_file.exists() and ground_truth_file.exists()):
            generator = project_root / "scripts" / "generate_synthetic_dataset.py"
            print("Synthetic dataset not found; generating...")
            os.system(
                f"\"{sys.executable}\" \"{generator}\" --output-root \"Supplementary/synthetic_dataset\""
            )

        docs_dir_rel = docs_dir.relative_to(project_root).as_posix()
        survey_points_rel = survey_points_file.relative_to(project_root).as_posix()
        ground_truth_rel = ground_truth_file.relative_to(project_root).as_posix()

        config_loader.set("data.documents_dir", f"./{docs_dir_rel}")
        config_loader.set("data.survey_points_file", f"./{survey_points_rel}")
        config_loader.set("data.ground_truth_file", f"./{ground_truth_rel}")

    model_values: List[str] = [m.strip() for m in args.models.split(",") if m.strip()]
    model_enums: List[LLMModel] = []
    for mv in model_values:
        try:
            model_enums.append(LLMModel(mv))
        except ValueError:
            raise SystemExit(f"Unknown model value: {mv}")

    runner = ExperimentRunner(models=model_enums, config_loader=config_loader, stream_mode=False)

    print(
        f"Running incremental experiment: dataset={args.dataset}, models={len(model_enums)}, "
        f"documents={args.documents}, repetitions={args.repetitions}"
    )

    runner.run_experiment(
        repetitions=args.repetitions,
        test_documents=args.documents,
        save_results=True,
    )

    output_dir = runner.current_experiment_dir
    print(f"Done. Output dir: {output_dir}")
    if output_dir and output_dir.exists():
        for name in [
            "experiment_results.json",
            "raw_results.json",
            "metrics_results.json",
            "metrics_results.csv",
            "failure_modes_summary.json",
            "failure_modes_breakdown.csv",
            "processing_summary.txt",
        ]:
            p = output_dir / name
            if p.exists():
                print(f"- {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
