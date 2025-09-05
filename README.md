# Geo Drill Extractor

🚀 **地质钻孔实体提取系统** - 使用大语言模型从地质勘探报告中提取结构化信息并推断坐标位置

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 核心特性

- 🤖 **多模型支持**: 支持10+大语言模型，包括DeepSeek R1、QWQ-32B、Qwen系列、GPT系列
- 📄 **文档处理**: 自动解析Word文档(.docx)，保留表格结构
- 🎯 **智能提取**: 区分设计参数和实际施工参数的结构化提取
- 🗺️ **坐标推断**: 基于自然语言描述和测量点进行空间推理
- 📊 **6指标评估**: 全面的性能评估框架
- 🔄 **流式处理**: 支持实时流式输出显示
- ⚙️ **模块化架构**: 现代化Python包结构，易于扩展

## 🏗️ 架构概览

```
geo-drill-extractor/
├── 🚀 run_full_test.py           # 生产级完整测试脚本
├── 🧪 new_experiment.py          # 灵活实验工具
├── 📁 src/kg_drill_extraction/   # 核心Python包
│   ├── core/                     # 核心模型和配置
│   ├── llm/                      # LLM集成层
│   ├── extraction/               # 提取管道
│   ├── evaluation/               # 评估系统
│   └── experiment/               # 实验执行器
├── 📁 configs/                   # 模块化配置文件
├── 📁 tests/                     # 测试系统
├── 📁 documents/                 # 待处理文档
├── 📁 data/                      # 标注数据和测量点
└── 📁 experiment_results/        # 实验输出结果
```

## 🚀 快速开始

### 安装依赖

```bash
pip install openai python-docx pandas numpy transformers PyYAML
```

### 配置API密钥

**方式一：环境变量配置（推荐）**

复制 `.env.example` 为 `.env` 并填入真实API密钥：

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥
```

**方式二：直接修改配置文件**

在 `configs/llm.yaml` 中配置你的API密钥：

```yaml
api_keys:
  aliyun-bailian: "your_aliyun_api_key"
  deepseek-official: "your_deepseek_api_key" 
  openrouter: "your_openrouter_api_key"
```

### 运行测试

```bash
# 生产级完整测试
python run_full_test.py

# 快速功能验证
python new_experiment.py --type quick --documents 3

# 自定义实验
python new_experiment.py --type custom --models qwq-32b --documents 10 --repetitions 2
```

## 🤖 支持的模型

### 阿里云百炼平台
- QWQ-32B-Preview (推理模型)
- Qwen-Max
- Qwen3-14B/32B  
- DeepSeek R1蒸馏版 (7B/14B/32B)

### DeepSeek官方
- DeepSeek V3
- DeepSeek R1

### OpenRouter
- GPT-3.5-Turbo
- GPT-4o-Mini

## 📊 评估指标

系统提供6项核心指标：

1. **提取召回率** - 实体检测准确性
2. **位置召回率** - 位置描述提取准确性  
3. **坐标成功率** - 空间推理准确性
4. **处理稳定性** - 跨轮次一致性
5. **效率系数** - Token使用优化
6. **平均位置处理时间** - 性能指标

## 🔧 配置系统

支持模块化配置管理：

- `configs/config.yaml` - 主配置文件
- `configs/llm.yaml` - LLM模型配置
- `configs/data.yaml` - 数据路径配置
- `configs/processing.yaml` - 处理配置
- `configs/experiment.yaml` - 实验预设

## 🧪 实验功能

### 完整测试
```bash
python run_full_test.py  # 7个模型 × 30个文档 × 3轮重复
```

### 灵活实验
```bash
# 快速测试
python new_experiment.py --type quick

# 完整实验  
python new_experiment.py --type full

# 自定义实验
python new_experiment.py --type custom --models deepseek-v3 qwq-32b --documents 20
```

## 📈 结果输出

实验结果保存到 `experiment_results/YYYY-MM-DD_HH-MM-SS/`:

- `experiment_results.json` - 完整实验数据
- `metrics_results.json` - 评估指标
- `raw_results.json` - 原始处理结果

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用 [MIT许可证](LICENSE)

## 🙏 致谢

感谢以下技术和平台的支持：
- 阿里云百炼平台
- DeepSeek
- OpenRouter
- OpenAI API标准