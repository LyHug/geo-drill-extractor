# Synthetic dataset (dummy data)

This repository cannot redistribute the real engineering documents used in the paper due to confidentiality constraints. To support reproducibility of the pipeline logic, we provide a small **synthetic dataset** (no confidential content).

## Generate files

Run:

```bash
python scripts/generate_synthetic_dataset.py
```

It creates:

- `Supplementary/synthetic_dataset/documents_zh/` (Chinese `.docx` files; **actual inputs** used by the pipeline)
- `Supplementary/synthetic_dataset/documents_en/` (English `.docx` translations for reviewer readability)
- `Supplementary/synthetic_dataset/data/survey_points_synthetic.csv`
- `Supplementary/synthetic_dataset/data/ground_truth_annotations_synthetic.csv`

## Use in code (example)

If you want to run experiments on the synthetic dataset, point the config paths to these files:

- `documents_dir`: `./Supplementary/synthetic_dataset/documents_zh`
- `survey_points_file`: `./Supplementary/synthetic_dataset/data/survey_points_synthetic.csv`
- `ground_truth_file`: `./Supplementary/synthetic_dataset/data/ground_truth_annotations_synthetic.csv`

`ConfigLoader` supports in-memory overrides via `config_loader.set(...)`.
