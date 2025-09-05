# Geo Drill Extractor

This code is from our paper "LLM-Powered Data Automation for 3D Geological Model Updating: Uncovering Architectural Divergence and the Efficiency-Effectiveness Paradox"

## Overview

An AI-powered system that automatically extracts structured drill hole information from geological exploration reports (Word documents) and infers spatial coordinates using Large Language Models (LLMs). The system was evaluated on 7 state-of-the-art models with comprehensive performance analysis.

## Main Steps to Run the Code

1. **Environment Setup**
   - Install Python 3.10+ and required dependencies: `pip install -r requirements.txt`
   - Copy `.env.example` to `.env` and configure your API keys

2. **Data Preparation**
   - Place your geological exploration reports (.docx) in the `documents/` directory
   - Add survey control points data to `data/导线点.csv`
   - Prepare ground truth annotations in `data/ground_truth_annotations.csv`

3. **Configuration**
   - Set the model configurations in `configs/llm.yaml` 
   - Configure data paths and processing parameters in `configs/config.yaml`

4. **Run Extraction**
   - For full evaluation (paper reproduction): `python run_full_test.py`
   - For quick testing: `python new_experiment.py --type quick --documents 3`
   - For custom experiments: `python new_experiment.py --type custom --models deepseek-r1-distill-qwen-32b-aliyun --documents 10`

5. **Results Analysis**
   - Check results in `experiment_results/` directory
   - Review 6-metric evaluation: extraction recall, location recall, coordinate success rate, processing stability, efficiency coefficient, and processing time
   - Export formats: CSV, Excel (multi-sheet), and JSON

## Tested Models (Paper Configuration)

The following 7 models were evaluated in our paper:

### Aliyun Bailian Platform
- **DeepSeek R1 Distilled-Qwen-7B**
- **DeepSeek R1 Distilled-Qwen-14B** 
- **DeepSeek R1 Distilled-Qwen-32B**
- **Qwen2.5-Max**
- **QWQ-32B** (Reasoning model)

### OpenRouter Platform
- **GPT-3.5-Turbo**
- **GPT-4o-Mini**

## Key Features

- **Multi-model LLM Integration**: Comprehensive evaluation across 7 cutting-edge language models
- **Intelligent Document Processing**: Converts Word documents to structured data while preserving tables
- **Spatial Coordinate Inference**: AI-powered spatial reasoning to calculate drill hole coordinates from natural language descriptions
- **6-Metric Evaluation System**: Comprehensive evaluation framework measuring accuracy, consistency, and efficiency
- **Batch Processing**: Parallel processing with configurable concurrency (7 models × 30 documents × 3 repetitions)
- **Modular Architecture**: Clean, extensible codebase with comprehensive configuration system

## Paper Experimental Setup

- **Models**: 7 state-of-the-art LLMs 
- **Documents**: 30 geological exploration reports
- **Repetitions**: 3 rounds per model-document pair
- **Total Runs**: 630 individual extractions
- **Evaluation Metrics**: 6-dimensional performance assessment

## System Requirements

- Python 3.10+
- Windows/Linux/macOS
- API access to Aliyun Bailian and OpenRouter platforms
- Minimum 8GB RAM for processing large document sets

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.