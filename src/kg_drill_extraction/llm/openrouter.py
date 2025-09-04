"""
OpenRouter LLM客户端实现
"""

from typing import Dict, List, Optional, Generator
import logging
from openai import OpenAI

from .base import BaseLLMClient, LLMConfig, LLMResponse
from ..core import LLMModel
from ..core.exceptions import LLMException, LLMAPIException

logger = logging.getLogger(__name__)


class OpenRouterClient(BaseLLMClient):
    """
    OpenRouter API客户端
    
    支持通过OpenRouter访问多种模型，包括GPT-3.5、GPT-4等
    """
    
    # 模型名称映射
    MODEL_NAME_MAP = {
        LLMModel.GPT_35_TURBO_OPENROUTER: "openai/gpt-3.5-turbo",
        LLMModel.GPT_4O_MINI_OPENROUTER: "openai/gpt-4o-mini",
    }
    
    def _initialize(self):
        """初始化OpenRouter客户端"""
        try:
            if not self.validate_config():
                raise LLMException(f"Invalid configuration for {self.model.value}")
            
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout
            )
            logger.info(f"OpenRouter客户端初始化成功: {self.model.value}")
        except Exception as e:
            self.handle_error(e, "初始化客户端失败")
    
    def _get_model_name(self) -> str:
        """获取OpenRouter的模型名称"""
        return self.MODEL_NAME_MAP.get(self.model, self.model.value)
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        生成文本响应
        
        Args:
            prompt: 输入提示词
            **kwargs: 额外参数（temperature、max_tokens等）
        
        Returns:
            LLM响应对象
        """
        try:
            # 合并配置和传入的参数
            temperature = kwargs.get('temperature', self.config.temperature)
            max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
            
            # 调用OpenAI API
            response = self._client.chat.completions.create(
                model=self._get_model_name(),
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            # 提取响应内容
            content = response.choices[0].message.content
            
            # 构建响应对象
            usage = None
            if hasattr(response, 'usage'):
                usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            
            return LLMResponse(
                content=content,
                model=self._get_model_name(),
                usage=usage,
                metadata={'response_id': response.id if hasattr(response, 'id') else None}
            )
            
        except Exception as e:
            self.handle_error(e, "generate")
    
    def stream_generate(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式生成文本响应
        
        Args:
            prompt: 输入提示词
            **kwargs: 额外参数
        
        Yields:
            响应文本片段
        """
        try:
            # 合并配置和传入的参数
            temperature = kwargs.get('temperature', self.config.temperature)
            max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
            
            # 创建流式响应
            stream = self._client.chat.completions.create(
                model=self._get_model_name(),
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            # 收集并yield响应片段
            for chunk in stream:
                # 跳过usage信息chunk
                if not chunk.choices and hasattr(chunk, 'usage'):
                    continue
                
                # 提取内容
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            self.handle_error(e, "stream_generate")
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        多轮对话接口
        
        Args:
            messages: 对话消息列表
            **kwargs: 额外参数
        
        Returns:
            LLM响应对象
        """
        try:
            # 合并配置和传入的参数
            temperature = kwargs.get('temperature', self.config.temperature)
            max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
            
            # 调用OpenAI API
            response = self._client.chat.completions.create(
                model=self._get_model_name(),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            # 提取响应内容
            content = response.choices[0].message.content
            
            # 构建响应对象
            usage = None
            if hasattr(response, 'usage'):
                usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            
            return LLMResponse(
                content=content,
                model=self._get_model_name(),
                usage=usage,
                metadata={'response_id': response.id if hasattr(response, 'id') else None}
            )
            
        except Exception as e:
            self.handle_error(e, "chat")