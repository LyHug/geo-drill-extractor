"""
LLM基础客户端抽象类
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Generator
import logging
from dataclasses import dataclass

from ..core import LLMModel
from ..core.exceptions import LLMException, LLMTimeoutException, LLMAPIException

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM配置"""
    model: LLMModel
    api_key: str
    base_url: str
    temperature: float = 0.1
    max_tokens: int = 8192
    timeout: int = 30
    retry_times: int = 3
    stream: bool = True


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseLLMClient(ABC):
    """
    LLM客户端基类
    
    提供统一的LLM调用接口，所有具体的LLM实现都应继承此类
    """
    
    def __init__(self, config: LLMConfig):
        """
        初始化LLM客户端
        
        Args:
            config: LLM配置对象
        """
        self.config = config
        self.model = config.model
        self._client = None
        self._initialize()
    
    @abstractmethod
    def _initialize(self):
        """初始化具体的客户端实现"""
        pass
    
    @abstractmethod
    def _get_model_name(self) -> str:
        """
        获取实际使用的模型名称
        
        Returns:
            模型名称字符串
        """
        pass
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        生成文本响应
        
        Args:
            prompt: 输入提示词
            **kwargs: 额外参数
        
        Returns:
            LLM响应对象
        
        Raises:
            LLMException: LLM调用异常
        """
        pass
    
    @abstractmethod
    def stream_generate(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式生成文本响应
        
        Args:
            prompt: 输入提示词
            **kwargs: 额外参数
        
        Yields:
            响应文本片段
        
        Raises:
            LLMException: LLM调用异常
        """
        pass
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        多轮对话接口
        
        Args:
            messages: 对话消息列表
            **kwargs: 额外参数
        
        Returns:
            LLM响应对象
        """
        # 默认实现：将messages转换为单个prompt
        prompt = self._messages_to_prompt(messages)
        return self.generate(prompt, **kwargs)
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        将对话消息转换为单个提示词
        
        Args:
            messages: 对话消息列表
        
        Returns:
            合并后的提示词
        """
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def validate_config(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            配置是否有效
        """
        if not self.config.api_key:
            logger.error(f"API key missing for {self.model.value}")
            return False
        
        if not self.config.base_url:
            logger.error(f"Base URL missing for {self.model.value}")
            return False
        
        return True
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """
        统一的错误处理
        
        Args:
            error: 异常对象
            context: 错误上下文
        
        Raises:
            LLMException: 转换后的LLM异常
        """
        error_msg = f"LLM错误 [{self.model.value}] {context}: {str(error)}"
        logger.error(error_msg)
        
        # 根据错误类型转换为特定异常
        if "timeout" in str(error).lower():
            raise LLMTimeoutException(error_msg)
        elif "api" in str(error).lower() or "status" in str(error).lower():
            raise LLMAPIException(error_msg)
        else:
            raise LLMException(error_msg)
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model.value})"
    
    def __repr__(self) -> str:
        return self.__str__()