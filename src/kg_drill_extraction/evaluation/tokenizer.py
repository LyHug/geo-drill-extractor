"""
分词器管理模块 - 管理多种LLM模型的分词器
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

from ..core import LLMModel
from ..core.exceptions import EvaluationException

logger = logging.getLogger(__name__)


@dataclass
class TokenizerInfo:
    """分词器信息"""
    model_id: str
    trust_remote_code: bool = False
    loaded: bool = False
    error_message: Optional[str] = None


class TokenizerManager:
    """
    分词器管理器
    
    负责管理和缓存多种LLM模型的分词器，提供统一的token计算接口
    """
    
    # 模型到Hugging Face模型ID的映射
    MODEL_TOKENIZER_MAP = {
        # DeepSeek系列
        LLMModel.DEEPSEEK_V3_OFFICIAL: TokenizerInfo("deepseek-ai/deepseek-v3", trust_remote_code=True),
        LLMModel.DEEPSEEK_R1_OFFICIAL: TokenizerInfo("deepseek-ai/deepseek-r1", trust_remote_code=True),
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_7B_ALIYUN: TokenizerInfo("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", trust_remote_code=True),
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_14B_ALIYUN: TokenizerInfo("deepseek-ai/DeepSeek-R1-Distill-Qwen-14B", trust_remote_code=True),
        LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN: TokenizerInfo("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", trust_remote_code=True),
        
        # Qwen系列
        LLMModel.QWEN3_14B: TokenizerInfo("Qwen/Qwen3-14B", trust_remote_code=True),
        LLMModel.QWEN3_32B: TokenizerInfo("Qwen/Qwen3-32B", trust_remote_code=True),
        LLMModel.QWQ: TokenizerInfo("Qwen/QwQ-32B-Preview", trust_remote_code=True),
        LLMModel.QWEN_MAX: TokenizerInfo("Qwen/Qwen2.5-72B", trust_remote_code=True),  # 使用较小的替代模型
        
        # GPT系列 (使用GPT-2分词器作为近似)
        LLMModel.GPT_35_TURBO_OPENROUTER: TokenizerInfo("gpt2", trust_remote_code=False),
        LLMModel.GPT_4O_MINI_OPENROUTER: TokenizerInfo("gpt2", trust_remote_code=False),
    }
    
    def __init__(self, fallback_to_char_count: bool = True):
        """
        初始化分词器管理器
        
        Args:
            fallback_to_char_count: 当分词器加载失败时是否回退到字符计数
        """
        self._tokenizers: Dict[LLMModel, Any] = {}
        self._fallback_to_char_count = fallback_to_char_count
        self._failed_models = set()
        
        # 尝试导入transformers
        try:
            from transformers import AutoTokenizer
            self._AutoTokenizer = AutoTokenizer
            self._transformers_available = True
        except ImportError:
            logger.warning("transformers库不可用，将使用字符计数作为fallback")
            self._AutoTokenizer = None
            self._transformers_available = False
    
    def get_tokenizer(self, model: LLMModel) -> Optional[Any]:
        """
        获取指定模型的分词器
        
        Args:
            model: LLM模型枚举
        
        Returns:
            分词器对象，加载失败时返回None
        """
        # 检查缓存
        if model in self._tokenizers:
            return self._tokenizers[model]
        
        # 检查是否已知加载失败
        if model in self._failed_models:
            return None
        
        # 检查transformers可用性
        if not self._transformers_available:
            self._failed_models.add(model)
            return None
        
        # 获取分词器信息
        tokenizer_info = self.MODEL_TOKENIZER_MAP.get(model)
        if not tokenizer_info:
            logger.warning(f"未找到模型 {model.value} 的分词器配置")
            self._failed_models.add(model)
            return None
        
        # 尝试加载分词器
        try:
            logger.info(f"加载分词器: {tokenizer_info.model_id}")
            tokenizer = self._AutoTokenizer.from_pretrained(
                tokenizer_info.model_id,
                trust_remote_code=tokenizer_info.trust_remote_code
            )
            
            # 缓存分词器
            self._tokenizers[model] = tokenizer
            tokenizer_info.loaded = True
            
            logger.info(f"分词器加载成功: {model.value}")
            return tokenizer
            
        except Exception as e:
            error_msg = f"分词器加载失败 {model.value}: {str(e)}"
            logger.warning(error_msg)
            
            tokenizer_info.error_message = error_msg
            self._failed_models.add(model)
            return None
    
    def calculate_tokens(
        self, 
        text: str, 
        model: Optional[LLMModel] = None
    ) -> int:
        """
        计算文本的token数量
        
        Args:
            text: 输入文本
            model: LLM模型（如果为None则使用默认分词器）
        
        Returns:
            token数量
        
        Raises:
            TokenizationException: 分词失败且不允许fallback时
        """
        if not text:
            return 0
        
        # 如果指定了模型，尝试使用对应的分词器
        if model:
            tokenizer = self.get_tokenizer(model)
            if tokenizer:
                try:
                    tokens = tokenizer.encode(text, add_special_tokens=True)
                    return len(tokens)
                except Exception as e:
                    logger.warning(f"使用分词器计算token失败: {str(e)}")
        
        # 尝试使用默认分词器（DeepSeek R1 Distill Qwen 32B）
        default_model = LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN
        if model != default_model:  # 避免无限递归
            try:
                return self.calculate_tokens(text, default_model)
            except:
                pass
        
        # Fallback到字符计数
        if self._fallback_to_char_count:
            # 中文字符近似token比例为1:1，英文单词约为1:0.75
            chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
            other_chars = len(text) - chinese_chars
            estimated_tokens = chinese_chars + int(other_chars * 0.75)
            
            logger.debug(f"使用字符计数估算tokens: {estimated_tokens}")
            return estimated_tokens
        else:
            raise EvaluationException(
                f"Failed to calculate tokens for text (length: {len(text)})",
                details={'model': model.value if model else None}
            )
    
    def calculate_tokens_batch(
        self,
        texts: list,
        model: Optional[LLMModel] = None
    ) -> list:
        """
        批量计算token数量
        
        Args:
            texts: 文本列表
            model: LLM模型
        
        Returns:
            token数量列表
        """
        return [self.calculate_tokens(text, model) for text in texts]
    
    def get_tokenizer_info(self, model: LLMModel) -> TokenizerInfo:
        """
        获取分词器信息
        
        Args:
            model: LLM模型枚举
        
        Returns:
            分词器信息对象
        """
        info = self.MODEL_TOKENIZER_MAP.get(model)
        if not info:
            return TokenizerInfo(
                model_id="unknown",
                loaded=False,
                error_message="Unsupported model"
            )
        
        # 更新加载状态
        info.loaded = model in self._tokenizers
        return info
    
    def get_available_tokenizers(self) -> Dict[LLMModel, TokenizerInfo]:
        """
        获取所有可用的分词器信息
        
        Returns:
            模型到分词器信息的映射
        """
        available = {}
        for model, info in self.MODEL_TOKENIZER_MAP.items():
            # 尝试加载以更新状态
            if model not in self._failed_models and model not in self._tokenizers:
                self.get_tokenizer(model)
            
            info_copy = TokenizerInfo(
                model_id=info.model_id,
                trust_remote_code=info.trust_remote_code,
                loaded=model in self._tokenizers,
                error_message=info.error_message
            )
            available[model] = info_copy
        
        return available
    
    def clear_cache(self):
        """清除分词器缓存"""
        self._tokenizers.clear()
        self._failed_models.clear()
        logger.info("分词器缓存已清除")
    
    def preload_tokenizers(self, models: Optional[list] = None):
        """
        预加载分词器
        
        Args:
            models: 要预加载的模型列表，如果为None则加载所有支持的模型
        """
        target_models = models or list(self.MODEL_TOKENIZER_MAP.keys())
        
        logger.info(f"开始预加载 {len(target_models)} 个分词器...")
        
        success_count = 0
        for model in target_models:
            if self.get_tokenizer(model):
                success_count += 1
        
        logger.info(f"预加载完成: {success_count}/{len(target_models)} 个分词器加载成功")


# 全局分词器管理器实例
_tokenizer_manager = None

def get_tokenizer_manager() -> TokenizerManager:
    """获取全局分词器管理器实例"""
    global _tokenizer_manager
    if _tokenizer_manager is None:
        _tokenizer_manager = TokenizerManager()
    return _tokenizer_manager