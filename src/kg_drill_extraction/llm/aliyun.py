"""
阿里云百炼平台LLM客户端实现
"""

from typing import Dict, List, Optional, Generator
import logging
from openai import OpenAI

from .base import BaseLLMClient, LLMConfig, LLMResponse
from ..core import LLMModel
from ..core.exceptions import LLMException

logger = logging.getLogger(__name__)


class AliyunClient(BaseLLMClient):
    """
    阿里云百炼平台API客户端
    
    支持通过阿里云百炼访问Qwen系列、DeepSeek R1蒸馏版等模型
    """
    
    # 模型名称映射
    MODEL_NAME_MAP = {
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_7B_ALIYUN: "deepseek-r1-distill-qwen-7b",
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_14B_ALIYUN: "deepseek-r1-distill-qwen-14b",
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN: "deepseek-r1-distill-qwen-32b",
        LLMModel.QWEN3_14B: "qwen3-14b",
        LLMModel.QWEN3_32B: "qwen3-32b",
        LLMModel.QWQ: "qwq-32b",
        LLMModel.QWEN_MAX: "qwen-max",
    }
    
    def _initialize(self):
        """初始化阿里云百炼客户端"""
        try:
            if not self.validate_config():
                raise LLMException(f"Invalid configuration for {self.model.value}")
            
            # 阿里云百炼使用OpenAI兼容API
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout
            )
            logger.info(f"阿里云百炼客户端初始化成功: {self.model.value}")
        except Exception as e:
            self.handle_error(e, "初始化客户端失败")
    
    def _get_model_name(self) -> str:
        """获取阿里云百炼的模型名称"""
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
            
            # 构建消息
            messages = [{"role": "user", "content": prompt}]
            
            
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
                metadata={
                    'response_id': response.id if hasattr(response, 'id') else None,
                    'provider': 'aliyun'
                }
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
            stream_params = {
                'model': self._get_model_name(),
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'stream': True,
                'stream_options': {"include_usage": True}
            }
            
            
            stream = self._client.chat.completions.create(**stream_params)
            
            # 统一处理所有模型的流式响应
            for chunk in stream:
                if not chunk.choices and hasattr(chunk, 'usage'):
                    continue

                delta = chunk.choices[0].delta

                # if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                #     print(delta.reasoning_content, end='', flush=True)

                if hasattr(delta, "content") and delta.content:
                    yield delta.content

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
                metadata={
                    'response_id': response.id if hasattr(response, 'id') else None,
                    'provider': 'aliyun'
                }
            )
            
        except Exception as e:
            self.handle_error(e, "chat")