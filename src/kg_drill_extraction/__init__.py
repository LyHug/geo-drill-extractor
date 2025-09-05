"""
Geo Drill Extractor - 主包初始化

一个基于LLM的地质钻孔实体提取系统，支持从Word文档中提取钻孔信息并推断空间坐标。

主要功能：
- 多种LLM模型支持 (DeepSeek、Qwen、GPT等)
- 文档处理和实体提取
- 坐标推断和空间分析
- 6指标评估体系
- 多格式结果导出
- 实验执行和管理

使用示例：
    from kg_drill_extraction import ExtractionPipeline, LLMModel
    
    # 创建提取管道
    pipeline = ExtractionPipeline(model=LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN)
    
    # 处理文档
    result = pipeline.process_document("document.docx")
    
    # 查看提取结果
    print(f"提取到 {len(result.drill_holes)} 个钻孔实体")
    print(f"推断出 {len(result.coordinates)} 个坐标")
    
    # 运行实验
    from kg_drill_extraction.experiment import run_quick_experiment
    results = run_quick_experiment()
"""

# 核心模型和配置
from .core import (
    # 数据模型
    LLMModel,
    DrillHoleEntity,
    DrillHoleDesignParams,
    DrillHoleActualParams,
    Coordinate,
    ProcessResult,
    SingleRunMetrics,
    SingleRunMetricsData,
    AggregatedMetrics,
    AggregatedMetricsData,
    SixMetricsScores,
    GroundTruthData,
    VerificationData,
    
    # 配置管理
    ConfigLoader,
    get_config_loader,
    get_config,
    
    # 异常类
    KGExtractionException,
    ConfigException,
    LLMException,
    DocumentException,
    ExtractionException,
    DataException,
    EvaluationException,
    ExportException,
    ExperimentException,
    ValidationException,
    
    # 工具函数
    calculate_six_metrics_from_raw_data
)

# 提取管道
from .extraction import ExtractionPipeline

# 评估系统
from .evaluation import (
    SixMetricsProcessor,
    GroundTruthLoader,
    GroundTruthStats,
    TokenizerManager,
    get_tokenizer_manager
)

# 实验系统
from .experiment import (
    ExperimentRunner,
    run_quick_experiment,
    run_full_experiment,
    ResultExporter
)

__version__ = "0.1.0"
__author__ = "Geo Research Team"
__email__ = "team@geo-research.com"

__all__ = [
    # 核心数据模型
    'LLMModel',
    'DrillHoleEntity', 
    'DrillHoleDesignParams',
    'DrillHoleActualParams',
    'Coordinate',
    'ProcessResult',
    'SingleRunMetrics',
    'SingleRunMetricsData', 
    'AggregatedMetrics',
    'AggregatedMetricsData',
    'SixMetricsScores',
    'GroundTruthData',
    'VerificationData',
    
    # 主要功能
    'ExtractionPipeline',
    
    # 评估系统
    'SixMetricsProcessor',
    'GroundTruthLoader',
    'GroundTruthStats',
    'TokenizerManager',
    'get_tokenizer_manager',
    
    # 实验系统
    'ExperimentRunner',
    'run_quick_experiment',
    'run_full_experiment',
    'ResultExporter',
    
    # 配置管理
    'ConfigLoader',
    'get_config_loader',
    'get_config',
    
    # 异常处理
    'KGExtractionException',
    'ConfigException', 
    'LLMException',
    'DocumentException',
    'ExtractionException',
    'DataException',
    'EvaluationException',
    'ExportException',
    'ExperimentException',
    'ValidationException',
    
    # 工具函数
    'calculate_six_metrics_from_raw_data',
]