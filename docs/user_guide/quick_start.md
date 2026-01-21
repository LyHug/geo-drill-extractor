# 快速开始指南

本指南将帮助你在5分钟内开始使用KG钻孔实体提取系统。

## 🎯 系统简介

KG钻孔实体提取系统是一个基于大语言模型（LLM）的地质钻孔数据提取工具，能够：
- 从地质勘探报告中提取钻孔实体信息
- 基于自然语言描述推断钻孔坐标
- 使用6指标评估系统评估提取质量
- 支持多种LLM模型和批量处理

## ⚡ 5分钟快速开始

### 1. 环境检查

确保你的系统已安装Python 3.10+：

```bash
python --version
```

### 2. 安装依赖

```bash
# 核心依赖
pip install openai python-docx pandas numpy transformers PyYAML

# 可选依赖（用于Excel导出）
pip install openpyxl xlsxwriter
```

### 3. 配置API密钥

编辑 `configs/config.yaml` 文件，填入你的API密钥：

```yaml
llm:
  api_keys:
    aliyun-bailian: "your-aliyun-api-key"    # 推荐使用
    deepseek-official: "your-deepseek-key"   # 可选
    openrouter: "your-openrouter-key"        # 可选
```

### 4. 准备数据文件

确保以下数据文件存在：
- `documents/`（或 `configs/config.yaml` 的 `data.documents_dir` 指向的目录；论文实验默认：`documents/实验用钻孔文档/`）- 待处理的Word文档（.docx格式）
- `data/导线点.csv` - 测量控制点坐标
- `data/ground_truth_annotations.csv` - 标注数据（可选）

### 5. 运行第一个实验

选择以下任一方式开始：

#### 方式1：生产级完整测试（推荐）
```bash
python run_full_test.py
```
- ✅ 使用可靠模型
- ✅ 30个文档，3轮重复
- ✅ 完整的6指标评估

#### 方式2：快速功能验证
```bash
python scripts/run_incremental_experiment.py --dataset synthetic --documents 3 --repetitions 1
```
- ⚡ 3个文档，1轮测试
- ⚡ 用时约2-5分钟

#### 方式3：自定义实验
```bash
python scripts/run_incremental_experiment.py --dataset real --models deepseek-r1-distill-qwen-32b-aliyun --documents 10 --repetitions 2
```

## 📊 查看结果

实验完成后，结果保存在：
- `experiment_results/YYYY-MM-DD_HH-MM-SS/` - 实验结果目录
  - `experiment_results.json` - 完整实验数据
  - `metrics_results.json` - 6指标评估结果
  - `metrics_results.csv` - 6指标评估结果（CSV，便于统计分析/绘图）
  - `raw_results.json` - 原始提取结果
  - `failure_modes_summary.json` - 失败模式汇总（区分协议/解析失败 vs 坐标推断失败）
  - `failure_modes_breakdown.csv` - 失败模式明细表（按原因统计）

### 结果解读

#### 6指标评估结果示例：
```json
{
  "extraction_recall": 1.0,          // 实体提取召回率
  "location_recall": 1.0,            // 位置描述提取率
  "coordinate_success_rate": 0.95,   // 坐标推断成功率
  "processing_stability": 0.92,      // 处理稳定性
  "efficiency_coefficient": 8.5,     // 效率系数
  "avg_location_processing_time": 5.2 // 平均处理时间
}
```

#### 性能指标：
- **extraction_recall = 1.0**: 完美提取所有钻孔实体
- **coordinate_success_rate = 0.95**: 95%的坐标推断成功
- **efficiency_coefficient = 8.5**: 良好的token使用效率

## 🎨 界面和输出

### 运行界面
```
🚀 KG钻孔提取系统 - 完整测试
==================================================
⚙️  测试配置: 1个模型 × 30个文档 × 3轮重复
🕐 开始时间: 2025-09-04 14:30:00

🤖 加载 1 个实验模型...
📊 开始执行实验...
处理 ZK1.docx - 模型 deepseek-r1-distill-qwen-32b-aliyun - 第 1/3 轮
处理 ZK2.docx - 模型 deepseek-r1-distill-qwen-32b-aliyun - 第 1/3 轮
...

==================================================
🎉 测试完成！
⏱️  总时间: 45.2 分钟
📊 成功率: 98.9% (89/90)
📄 文档数: 30
🤖 模型数: 1
📁 结果: experiment_results\2025-09-04_14-30-00
✅ 测试成功！
```

### 输出文件结构
```
experiment_results/2025-09-04_14-30-00/
 ├── experiment_results.json      # 完整实验数据
 ├── metrics_results.json         # 6指标评估结果  
 ├── metrics_results.csv          # 6指标评估结果（CSV）
 ├── raw_results.json            # 原始提取结果
 ├── failure_modes_summary.json   # 失败模式汇总
 ├── failure_modes_breakdown.csv  # 失败模式明细
 └── processing_summary.txt      # 处理摘要
```

## 🔧 基础配置

## 🧪 Synthetic dataset（可复现用假数据）

真实工程文档可能受保密限制无法公开。仓库提供了可复现管线逻辑的合成数据（dummy data），详见：`docs/user_guide/synthetic_dataset.md`。

### 常用配置项

编辑 `configs/config.yaml` 以调整系统行为：

```yaml
# 选择默认模型
llm:
  default_model: "deepseek-r1-distill-qwen-32b-aliyun"  # 推荐
  # default_model: "qwen-max"                           # 备选
  # default_model: "gpt-3.5-turbo-openrouter"          # 需要OpenRouter

# 并发处理配置
processing:
  parallel:
    max_workers: 5                    # 并行工作线程数
    max_concurrent_llm_calls: 10      # 最大并发LLM调用数

# 实验配置
experiment:
  default_repetitions: 3              # 默认重复次数
  test_documents: 30                  # 默认测试文档数
```

## ⚠️ 常见问题

### 1. API连接失败
```bash
❌ 测试失败: HTTP 401 - Authentication failed
```
**解决方案**: 检查API密钥配置是否正确

### 2. 找不到文档文件
```bash
❌ 找不到文档目录: documents
```
**解决方案**: 确保 `documents/` 目录存在且包含 `.docx` 文件
（或检查 `configs/config.yaml` 中 `data.documents_dir` 是否指向实际存放文档的目录）。

### 3. 内存不足
```bash
❌ MemoryError: 内存不足
```
**解决方案**: 减少并行处理线程数：
```yaml
processing:
  parallel:
    max_workers: 2
    max_concurrent_llm_calls: 5
```

## 📈 下一步

- 📖 阅读 [`实验执行指南`](./experiment_guide.md) 了解更多实验选项
- ⚙️ 查看 [`配置说明`](./configuration.md) 进行高级配置
- 🏗️ 浏览 [`系统架构`](../architecture/system_overview.md) 了解系统设计
- 🔍 查看 [`故障排除`](./troubleshooting.md) 解决具体问题

## 💡 小贴士

1. **首次使用建议**: 先运行 `python new_experiment.py --type quick` 验证环境
2. **性能优化**: 使用阿里云模型(`aliyun-bailian`)通常速度最快
3. **结果分析**: 重点关注 `coordinate_success_rate` 和 `extraction_recall` 指标
4. **生产环境**: 使用 `run_full_test.py` 获得最稳定的结果

---

🎉 **恭喜！** 你已经成功开始使用KG钻孔实体提取系统。有问题请查看其他文档或联系支持。
