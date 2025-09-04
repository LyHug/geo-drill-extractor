"""
LLM客户端工厂
"""

from typing import Optional, Dict, Any
import logging

from .base import BaseLLMClient, LLMConfig
from .openrouter import OpenRouterClient
from .deepseek import DeepSeekClient
from .aliyun import AliyunClient
from ..core import LLMModel, get_config_loader
from ..core.exceptions import InvalidModelException, ConfigException

logger = logging.getLogger(__name__)


class LLMClientFactory:
    """
    LLM客户端工厂类
    
    负责根据模型类型创建相应的LLM客户端实例
    """
    
    # 模型到客户端类的映射
    MODEL_CLIENT_MAP = {
        # OpenRouter模型
        LLMModel.GPT_35_TURBO_OPENROUTER: OpenRouterClient,
        LLMModel.GPT_4O_MINI_OPENROUTER: OpenRouterClient,
        
        # DeepSeek官方模型
        LLMModel.DEEPSEEK_V3_OFFICIAL: DeepSeekClient,
        LLMModel.DEEPSEEK_R1_OFFICIAL: DeepSeekClient,
        
        # 阿里云百炼模型
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_7B_ALIYUN: AliyunClient,
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_14B_ALIYUN: AliyunClient,
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN: AliyunClient,
        LLMModel.QWEN3_14B: AliyunClient,
        LLMModel.QWEN3_32B: AliyunClient,
        LLMModel.QWQ: AliyunClient,
        LLMModel.QWEN_MAX: AliyunClient,
    }
    
    # 模型到API配置的映射
    MODEL_API_CONFIG = {
        # OpenRouter
        LLMModel.GPT_35_TURBO_OPENROUTER: {
            'api_key_name': 'openrouter',
            'base_url': 'https://openrouter.ai/api/v1'
        },
        LLMModel.GPT_4O_MINI_OPENROUTER: {
            'api_key_name': 'openrouter',
            'base_url': 'https://openrouter.ai/api/v1'
        },
        
        # DeepSeek官方
        LLMModel.DEEPSEEK_V3_OFFICIAL: {
            'api_key_name': 'deepseek-official',
            'base_url': 'https://api.deepseek.com/v1'
        },
        LLMModel.DEEPSEEK_R1_OFFICIAL: {
            'api_key_name': 'deepseek-official',
            'base_url': 'https://api.deepseek.com/v1'
        },
        
        # 阿里云百炼
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_7B_ALIYUN: {
            'api_key_name': 'aliyun-bailian',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        },
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_14B_ALIYUN: {
            'api_key_name': 'aliyun-bailian',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        },
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN: {
            'api_key_name': 'aliyun-bailian',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        },
        LLMModel.QWEN3_14B: {
            'api_key_name': 'aliyun-bailian',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        },
        LLMModel.QWEN3_32B: {
            'api_key_name': 'aliyun-bailian',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        },
        LLMModel.QWQ: {
            'api_key_name': 'aliyun-bailian',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        },
        LLMModel.QWEN_MAX: {
            'api_key_name': 'aliyun-bailian',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        },
    }
    
    @classmethod
    def create(
        cls,
        model: LLMModel,
        config_loader: Optional[Any] = None,
        config_override: Optional[Dict[str, Any]] = None
    ) -> BaseLLMClient:
        """
        创建LLM客户端实例
        
        Args:
            model: LLM模型枚举
            config_loader: 配置加载器实例（可选）
            config_override: 配置覆盖参数（可选）
        
        Returns:
            LLM客户端实例
        
        Raises:
            InvalidModelException: 不支持的模型
            ConfigException: 配置错误
        """
        # 检查模型是否支持
        if model not in cls.MODEL_CLIENT_MAP:
            raise InvalidModelException(
                f"Unsupported model: {model.value}",
                details={'available_models': [m.value for m in cls.MODEL_CLIENT_MAP.keys()]}
            )
        
        # 获取配置加载器
        if config_loader is None:
            config_loader = get_config_loader()
        
        # 获取API配置
        api_config = cls.MODEL_API_CONFIG.get(model, {})
        api_key_name = api_config.get('api_key_name')
        base_url = api_config.get('base_url')
        
        # 获取API密钥
        api_key = config_loader.get_api_key(api_key_name)
        if not api_key:
            raise ConfigException(
                f"API key not found for {api_key_name}",
                details={'model': model.value, 'api_key_name': api_key_name}
            )
        
        # 构建LLM配置
        llm_config = LLMConfig(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=config_loader.get('llm.temperature', 0.1),
            max_tokens=config_loader.get('llm.max_tokens', 8192),
            timeout=config_loader.get('llm.timeout', 30),
            retry_times=config_loader.get('llm.retry_times', 3),
            stream=config_loader.get('llm.stream', True)
        )
        
        # 应用配置覆盖
        if config_override:
            for key, value in config_override.items():
                if hasattr(llm_config, key):
                    setattr(llm_config, key, value)
        
        # 获取客户端类
        client_class = cls.MODEL_CLIENT_MAP[model]
        
        # 创建并返回客户端实例
        try:
            client = client_class(llm_config)
            logger.info(f"Created LLM client for {model.value}")
            return client
        except Exception as e:
            raise ConfigException(
                f"Failed to create LLM client for {model.value}",
                details={'error': str(e)}
            )
    
    @classmethod
    def get_supported_models(cls) -> Dict[str, str]:
        """
        获取支持的模型列表
        
        Returns:
            模型名称到提供商的映射
        """
        result = {}
        for model in cls.MODEL_CLIENT_MAP.keys():
            api_config = cls.MODEL_API_CONFIG.get(model, {})
            provider = api_config.get('api_key_name', 'unknown')
            result[model.value] = provider
        return result
    
    @classmethod
    def validate_model_config(cls, model: LLMModel, config_loader: Optional[Any] = None) -> bool:
        """
        验证模型配置是否完整
        
        Args:
            model: LLM模型枚举
            config_loader: 配置加载器实例
        
        Returns:
            配置是否有效
        """
        if model not in cls.MODEL_CLIENT_MAP:
            return False
        
        if config_loader is None:
            config_loader = get_config_loader()
        
        api_config = cls.MODEL_API_CONFIG.get(model, {})
        api_key_name = api_config.get('api_key_name')
        
        if not api_key_name:
            return False
        
        api_key = config_loader.get_api_key(api_key_name)
        return bool(api_key)