"""
自定义异常类 - 定义系统中使用的所有异常
"""

from typing import Optional, Any, Dict


class KGExtractionException(Exception):
    """基础异常类"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


# 配置相关异常
class ConfigException(KGExtractionException):
    """配置异常"""
    pass


class ConfigNotFoundException(ConfigException):
    """配置文件未找到"""
    pass


class InvalidConfigException(ConfigException):
    """无效的配置"""
    pass


# LLM相关异常
class LLMException(KGExtractionException):
    """LLM异常基类"""
    pass


class LLMConnectionException(LLMException):
    """LLM连接异常"""
    pass


class LLMAPIException(LLMException):
    """LLM API调用异常"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_body: Optional[str] = None, **kwargs):
        details = {'status_code': status_code, 'response_body': response_body}
        details.update(kwargs)
        super().__init__(message, details)


class LLMTimeoutException(LLMException):
    """LLM调用超时"""
    pass


class LLMRateLimitException(LLMException):
    """LLM速率限制"""
    pass


class InvalidModelException(LLMException):
    """无效的模型"""
    pass


# 文档处理异常
class DocumentException(KGExtractionException):
    """文档处理异常基类"""
    pass


class DocumentNotFoundException(DocumentException):
    """文档未找到"""
    pass


class DocumentReadException(DocumentException):
    """文档读取异常"""
    pass


class DocumentParseException(DocumentException):
    """文档解析异常"""
    pass


class UnsupportedDocumentFormatException(DocumentException):
    """不支持的文档格式"""
    pass


# 提取相关异常
class ExtractionException(KGExtractionException):
    """提取异常基类"""
    pass


class EntityExtractionException(ExtractionException):
    """实体提取异常"""
    pass


class CoordinateInferenceException(ExtractionException):
    """坐标推理异常"""
    pass


class NoEntitiesFoundException(ExtractionException):
    """未找到实体"""
    pass


class InvalidEntityFormatException(ExtractionException):
    """无效的实体格式"""
    pass


# 数据相关异常
class DataException(KGExtractionException):
    """数据异常基类"""
    pass


class SurveyPointsNotFoundException(DataException):
    """导线点数据未找到"""
    pass


class InvalidSurveyPointsException(DataException):
    """无效的导线点数据"""
    pass


class GroundTruthNotFoundException(DataException):
    """真值数据未找到"""
    pass


class InvalidGroundTruthException(DataException):
    """无效的真值数据"""
    pass


# 评估相关异常
class EvaluationException(KGExtractionException):
    """评估异常基类"""
    pass


class MetricsCalculationException(EvaluationException):
    """指标计算异常"""
    pass


class InsufficientDataException(EvaluationException):
    """数据不足"""
    pass


class TokenizationException(EvaluationException):
    """分词异常"""
    pass


# 导出相关异常
class ExportException(KGExtractionException):
    """导出异常基类"""
    pass


class UnsupportedExportFormatException(ExportException):
    """不支持的导出格式"""
    pass


class ExportWriteException(ExportException):
    """导出写入异常"""
    pass


class InvalidExportPathException(ExportException):
    """无效的导出路径"""
    pass


# 实验相关异常
class ExperimentException(KGExtractionException):
    """实验异常基类"""
    pass


class ExperimentConfigException(ExperimentException):
    """实验配置异常"""
    pass


class ExperimentExecutionException(ExperimentException):
    """实验执行异常"""
    pass


class NoResultsException(ExperimentException):
    """无结果异常"""
    pass


# 验证相关异常
class ValidationException(KGExtractionException):
    """验证异常基类"""
    pass


class InvalidInputException(ValidationException):
    """无效输入"""
    pass


class ValidationFailedException(ValidationException):
    """验证失败"""
    pass


# 工具函数
def handle_exception(exception: Exception, context: str = None, 
                     reraise: bool = True) -> Optional[Dict[str, Any]]:
    """
    统一的异常处理函数
    
    Args:
        exception: 异常对象
        context: 上下文信息
        reraise: 是否重新抛出异常
    
    Returns:
        异常信息字典
    """
    error_info = {
        'type': type(exception).__name__,
        'message': str(exception),
        'context': context
    }
    
    if isinstance(exception, KGExtractionException):
        error_info['details'] = exception.details
    
    # 记录日志（这里可以集成日志系统）
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Exception in {context}: {error_info}")
    
    if reraise:
        raise
    
    return error_info