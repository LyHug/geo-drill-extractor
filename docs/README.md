# 文档索引

本目录包含KG钻孔实体提取系统的完整文档。

## 📚 文档结构

### 用户文档
- [`user_guide/`](./user_guide/) - 用户使用指南
  - [`快速开始指南`](./user_guide/quick_start.md)
  - [`实验执行指南`](./user_guide/experiment_guide.md)
  - [`配置说明`](./user_guide/configuration.md)
  - [`故障排除`](./user_guide/troubleshooting.md)

### 开发文档
- [`developer/`](./developer/) - 开发者文档
  - [`开发环境设置`](./developer/development_setup.md)
  - [`代码规范`](./developer/coding_standards.md)
  - [`测试指南`](./developer/testing_guide.md)
  - [`贡献指南`](./developer/contributing.md)

### 架构文档
- [`architecture/`](./architecture/) - 系统架构文档
  - [`系统架构概述`](./architecture/system_overview.md)
  - [`模块设计`](./architecture/module_design.md)
  - [`数据流`](./architecture/data_flow.md)
  - [`重构历程`](./architecture/refactoring_history.md)

### API文档
- [`api/`](./api/) - API参考文档
  - [`核心模块API`](./api/core_modules.md)
  - [`提取管道API`](./api/extraction_pipeline.md)
  - [`实验执行API`](./api/experiment_runner.md)
  - [`配置管理API`](./api/config_loader.md)

### 示例文档
- [`examples/`](./examples/) - 使用示例
  - [`基础使用示例`](./examples/basic_usage.md)
  - [`高级配置示例`](./examples/advanced_config.md)
  - [`自定义实验示例`](./examples/custom_experiments.md)

## 🚀 快速导航

### 我想...
- **开始使用系统** → [`快速开始指南`](./user_guide/quick_start.md)
- **运行实验** → [`实验执行指南`](./user_guide/experiment_guide.md)
- **了解系统架构** → [`系统架构概述`](./architecture/system_overview.md)
- **开发新功能** → [`开发环境设置`](./developer/development_setup.md)
- **查看API文档** → [`API参考文档`](./api/)
- **解决问题** → [`故障排除`](./user_guide/troubleshooting.md)

## 📖 重要文档

### Stage 7 重构文档
- [重构历程](./architecture/refactoring_history.md) - 详细的7阶段重构过程
- [配置系统重构](./user_guide/configuration.md) - 新的模块化配置系统
- [模块架构](./architecture/module_design.md) - 重构后的模块设计

### 核心功能文档
- [6指标评估系统](./architecture/evaluation_system.md) - 详细的评估指标说明
- [多模型LLM集成](./api/llm_integration.md) - LLM模型集成文档
- [坐标推断算法](./architecture/coordinate_inference.md) - 坐标推断核心算法

## 🔧 配置和部署

- [配置文件说明](./user_guide/configuration.md) - 详细的配置选项
- [环境变量设置](./user_guide/environment_setup.md) - 环境配置指南
- [部署指南](./user_guide/deployment.md) - 生产环境部署

## 📊 性能和优化

- [性能优化指南](./developer/performance_optimization.md)
- [内存管理最佳实践](./developer/memory_management.md)
- [并发处理配置](./user_guide/parallel_processing.md)

## 🐛 故障排除

常见问题的快速解决方案：
- [API连接问题](./user_guide/troubleshooting.md#api-connection-issues)
- [内存不足问题](./user_guide/troubleshooting.md#memory-issues)
- [配置文件问题](./user_guide/troubleshooting.md#config-issues)
- [模型调用问题](./user_guide/troubleshooting.md#model-issues)

## 📝 更新日志

- [版本更新记录](./CHANGELOG.md) - 系统版本变更历史
- [Stage 7完成报告](../STAGE_7_COMPLETION.md) - 最新重构完成情况

---

> 💡 **提示**: 本文档会持续更新，建议收藏此索引页面以便快速导航到所需内容。

> ⭐ **推荐阅读顺序**: 快速开始 → 系统架构 → 实验执行 → 高级配置