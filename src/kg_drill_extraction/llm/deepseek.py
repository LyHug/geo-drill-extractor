"""
DeepSeek LLM客户端实现
"""

from typing import Dict, List, Optional, Generator
import logging
from openai import OpenAI

from .base import BaseLLMClient, LLMConfig, LLMResponse
from ..core import LLMModel
from ..core.exceptions import LLMException

logger = logging.getLogger(__name__)


class DeepSeekClient(BaseLLMClient):
    """
    DeepSeek官方API客户端
    
    支持DeepSeek V3和R1系列模型
    """
    
    # 模型名称映射
    MODEL_NAME_MAP = {
        LLMModel.DEEPSEEK_V3_OFFICIAL: "deepseek-chat",
        LLMModel.DEEPSEEK_R1_OFFICIAL: "deepseek-reasoner",
    }
    
    def _initialize(self):
        """初始化DeepSeek客户端"""
        try:
            if not self.validate_config():
                raise LLMException(f"Invalid configuration for {self.model.value}")
            
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout
            )
            logger.info(f"DeepSeek客户端初始化成功: {self.model.value}")
        except Exception as e:
            self.handle_error(e, "初始化客户端失败")
    
    def _get_model_name(self) -> str:
        """获取DeepSeek的模型名称"""
        return self.MODEL_NAME_MAP.get(self.model, self.model.value)
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        生成文本响应
        
        Args:
            prompt: 输入提示词
            **kwargs: 额外参数
        
        Returns:
            LLM响应对象
        """
        try:
            # 合并配置和传入的参数
            temperature = kwargs.get('temperature', self.config.temperature)
            max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
            
            # 对于DeepSeek R1，可能需要特殊处理
            messages = [{"role": "user", "content": prompt}]
            
            # 如果是reasoner模型，可以添加思考链提示
            if self.model == LLMModel.DEEPSEEK_R1_OFFICIAL:
                # R1模型支持推理模式
                kwargs['reasoning_effort'] = kwargs.get('reasoning_effort', 'medium')
            
            # 调用API
            response = self._client.chat.completions.create(
                model=self._get_model_name(),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **{k: v for k, v in kwargs.items() if k not in ['temperature', 'max_tokens']}
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
            
            # 对于R1模型，可能有推理过程
            metadata = {'response_id': response.id if hasattr(response, 'id') else None}
            if hasattr(response.choices[0], 'reasoning_content'):
                metadata['reasoning'] = response.choices[0].reasoning_content
            
            return LLMResponse(
                content=content,
                model=self._get_model_name(),
                usage=usage,
                metadata=metadata
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
            
            messages = [{"role": "user", "content": prompt}]
            
            # 创建流式响应
            stream = self._client.chat.completions.create(
                model=self._get_model_name(),
                messages=messages,
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
            
            # 调用API
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