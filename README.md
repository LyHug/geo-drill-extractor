# Geo Drill Extractor

This repository contains the implementation used in our manuscript: "LLM-Powered Borehole Data Automation for 3D Geological Modeling Workflows: An Eight-Model Evaluation and the Efficiency-Effectiveness Paradox".

## Overview

Geo Drill Extractor is an end-to-end pipeline that:

- Parses borehole reports (Word documents) into structured borehole entities.
- Infers 3D coordinates from relative location descriptions using survey control points.
- Evaluates multiple LLMs under a unified prompting and parsing protocol that enforces machine-parseable JSON outputs.
- Reports both metric scores and failure modes (protocol/parsing vs. semantic/geometric errors) to avoid misattribution.

## Experimental Protocol (Paper Setting)

- Models: 8 core LLMs (see below)
- Documents: 30 reports
- Repetitions: 3 runs per model-document pair
- Total runs: 8 x 30 x 3 = 720
- Metrics (6D): Extraction Recall (ER), Location Recall (LR), Coordinate Success Rate (CSR), Efficiency Coefficient (EC), Processing Stability (PS), and Average Location Processing Time (ALPT)

## Quick Start

1. Install dependencies:

   - `python -m pip install -r requirements.txt`

2. Configure API keys:

   - Copy `.env.example` to `.env` and set `ALIYUN_API_KEY` and/or `OPENROUTER_API_KEY`.

3. Run a low-cost end-to-end check using the synthetic dataset (auto-generated if missing):

   - `python scripts/run_incremental_experiment.py --dataset synthetic --documents 3 --repetitions 1`

4. Run the full 8-model paper configuration (requires you to provide the real documents and annotation files via config):

   - `python run_full_test.py`

Results are written to `experiment_results/<timestamp>/`.

## Configuration

- Data paths are configured via `configs/config.yaml` (or overridden programmatically by scripts):
  - `data.documents_dir`: directory containing `.docx` reports
  - `data.survey_points_file`: survey control points CSV
  - `data.ground_truth_file`: ground-truth annotations CSV (for metric computation)
- Model routing is implemented in code (see `src/llm/`) and the model identifiers are defined in `src/core/models.py`.

## Core Models (Paper Configuration)

The paper configuration (used by `run_full_test.py`) evaluates the following 8 model values:

- Aliyun Bailian (DashScope compatible API):
  - `deepseek-r1-distill-qwen-7b-aliyun`
  - `deepseek-r1-distill-qwen-14b-aliyun`
  - `deepseek-r1-distill-qwen-32b-aliyun`
  - `qwen-max`
  - `qwq-32b`
- OpenRouter:
  - `gpt-3.5-turbo-openrouter`
  - `gpt-4o-mini-openrouter`
  - `gpt-4.1-openrouter`

## Output Artifacts

Each experiment run produces a timestamped folder under `experiment_results/` containing:

- `experiment_results.json`: metadata + exported artifacts
- `raw_results.json`: raw structured outputs per model
- `metrics_results.json` / `metrics_results.csv`: per-document metric table
- `failure_modes_summary.json` / `failure_modes_breakdown.csv`: failure mode aggregation and breakdown
- `processing_summary.txt`: a human-readable summary with file pointers

## License

MIT License. See `LICENSE`.
