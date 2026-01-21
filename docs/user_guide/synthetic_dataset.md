# Synthetic dataset (dummy data)

This repository cannot redistribute the real engineering documents used in the paper due to confidentiality constraints. To support reproducibility of the pipeline logic, we provide a small **synthetic dataset** (no confidential content).

## Generate files

Run:

```bash
python scripts/generate_synthetic_dataset.py
```

It creates:

- `documents_synthetic/` (2 synthetic `.docx` files)
- `data_synthetic/survey_points_synthetic.csv`
- `data_synthetic/ground_truth_annotations_synthetic.csv`

## Use in code (example)

If you want to run experiments on the synthetic dataset, point the config paths to these files:

- `documents_dir`: `./documents_synthetic`
- `survey_points_file`: `./data_synthetic/survey_points_synthetic.csv`
- `ground_truth_file`: `./data_synthetic/ground_truth_annotations_synthetic.csv`

`ConfigLoader` supports in-memory overrides via `config_loader.set(...)`.
