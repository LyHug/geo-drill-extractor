"""
实体提取器模块 - 从文本中提取钻孔实体
"""

import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .prompts import EXTRACTION_PROMPT_TEMPLATE
from ..core import (
    DrillHoleEntity,
    DrillHoleDesignParams,
    DrillHoleActualParams
)
from ..core.exceptions import (
    ExtractionException,
    EntityExtractionException,
    InvalidEntityFormatException,
    NoEntitiesFoundException
)
from ..llm import BaseLLMClient

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    实体提取器
    
    使用LLM从文本中提取结构化的钻孔实体信息
    """
    
    def __init__(self, llm_client: BaseLLMClient, enable_cache: bool = False, stream_mode: bool = False):
        """
        初始化实体提取器
        
        Args:
            llm_client: LLM客户端实例
            enable_cache: 是否启用缓存（实验时建议关闭）
            stream_mode: 是否启用流式输出显示
        """
        self.llm_client = llm_client
        self.enable_cache = enable_cache
        self.stream_mode = stream_mode
        self.extraction_cache = {} if enable_cache else None
        self.max_retries = 3
        self.retry_delay = 1
    
    def extract_entities(self, text: str, doc_name: str = "") -> List[DrillHoleEntity]:
        """
        从文本中提取钻孔实体
        
        Args:
            text: 输入文本
            doc_name: 文档名称（用于日志）
        
        Returns:
            钻孔实体列表
        
        Raises:
            EntityExtractionException: 实体提取失败
        """
        # 检查缓存
        if self.enable_cache and self.extraction_cache is not None:
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()
            if text_hash in self.extraction_cache:
                logger.info(f"使用缓存的提取结果: {doc_name}")
                return self.extraction_cache[text_hash]
        
        try:
            logger.info(f"开始处理文档: {doc_name}")
            
            # 提取实体
            entities = self._extract_from_text(text)
            
            # 验证实体
            validated_entities = self._validate_entities(entities)
            
            logger.info(f"从文档 {doc_name} 提取到 {len(validated_entities)} 个钻孔实体")
            
            # 更新缓存
            if self.enable_cache and self.extraction_cache is not None:
                self.extraction_cache[text_hash] = validated_entities
            
            return validated_entities
            
        except ExtractionException:
            raise
        except Exception as e:
            raise EntityExtractionException(
                f"Failed to extract entities from {doc_name}: {str(e)}",
                details={'document': doc_name, 'error': str(e)}
            )
    
    def _extract_from_text(self, text: str) -> List[DrillHoleEntity]:
        """
        从文本中提取实体（内部方法）
        
        Args:
            text: 输入文本
        
        Returns:
            钻孔实体列表
        """
        # 构建提示词
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=text)
        
        # 重试机制
        for attempt in range(self.max_retries):
            try:
                # 调用LLM - 支持流式输出
                if self.stream_mode and hasattr(self.llm_client, 'stream_generate'):
                    print(f"\n🤖 开始实体提取 (流式输出)...")
                    
                    # 收集流式响应
                    full_response = ""
                    for chunk in self.llm_client.stream_generate(prompt):
                        print(chunk, end='', flush=True)  # 显示最终内容
                        full_response += chunk
                    
                    print(f"\n✅ 实体提取完成，响应长度: {len(full_response)}")
                    
                    # 构建响应对象（模拟LLMResponse）
                    from ..llm.base import LLMResponse
                    response = LLMResponse(
                        content=full_response,
                        model=self.llm_client._get_model_name() if hasattr(self.llm_client, '_get_model_name') else 'unknown',
                        usage=None
                    )
                else:
                    response = self.llm_client.generate(prompt)
                    logger.debug(f"LLM响应: {response.content[:500]}...")
                
                # 解析响应
                entities_data = self._parse_response(response.content)
                
                # 转换为实体对象
                drill_entities = []
                for entity_dict in entities_data:
                    entity = self._dict_to_entity(entity_dict)
                    if entity:
                        drill_entities.append(entity)
                
                if not drill_entities:
                    logger.warning("未提取到任何实体")
                
                return drill_entities
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"提取失败（已重试{self.max_retries}次）: {str(e)}")
                    raise EntityExtractionException(
                        f"Failed after {self.max_retries} attempts: {str(e)}"
                    )
                logger.warning(f"提取失败，重试 {attempt + 1}/{self.max_retries}: {str(e)}")
                time.sleep(self.retry_delay)
        
        return []
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """
        解析LLM响应
        
        Args:
            response: LLM响应文本
        
        Returns:
            解析后的实体字典列表
        
        Raises:
            InvalidEntityFormatException: 响应格式无效
        """
        entities = []
        
        try:
            # 清理响应文本
            response = response.strip()
            
            # 移除markdown代码块标记
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            
            response = response.strip()
            
            # 尝试直接解析JSON
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试从混合内容中提取JSON
                # 尝试从混合内容中提取JSON
                response = self._extract_json_from_mixed_content(response)
                data = json.loads(response)
            
            # 处理不同的响应格式
            if isinstance(data, dict):
                # 单个实体
                entities.append(data)
            elif isinstance(data, list):
                # 多个实体
                entities.extend(data)
            else:
                raise InvalidEntityFormatException(
                    f"Unexpected response format: {type(data)}"
                )
                
        except json.JSONDecodeError as e:
            raise InvalidEntityFormatException(
                f"Failed to parse JSON response: {str(e)}",
                details={'response_snippet': response[:500]}
            )
        
        return entities
    
    def _extract_json_from_mixed_content(self, content: str) -> str:
        """
        从包含推理过程的响应中提取JSON数组
        
        用于处理包含推理过程的混合内容，从中提取纯净的JSON
        
        Args:
            content: 包含推理过程和JSON的混合内容
        
        Returns:
            提取出的纯净JSON字符串
        
        Raises:
            InvalidEntityFormatException: 找不到有效的JSON
        """
        # 策略1: 查找最后一个完整的JSON数组
        # 从后往前查找，因为JSON通常在推理过程之后
        
        # 查找所有可能的JSON数组起始位置
        json_start_positions = []
        for i in range(len(content)):
            if content[i] == '[':
                json_start_positions.append(i)
        
        # 从最后一个'['开始，尝试找到完整的JSON数组
        for start_pos in reversed(json_start_positions):
            try:
                # 找到对应的结束位置
                bracket_count = 0
                for end_pos in range(start_pos, len(content)):
                    if content[end_pos] == '[':
                        bracket_count += 1
                    elif content[end_pos] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            # 找到完整的JSON数组
                            json_candidate = content[start_pos:end_pos + 1]
                            
                            # 尝试解析以验证有效性
                            json.loads(json_candidate)
                            return json_candidate.strip()
            except (json.JSONDecodeError, IndexError):
                continue
        
        # 策略2: 查找JSON对象 (如果不是数组格式)
        json_start_positions = []
        for i in range(len(content)):
            if content[i] == '{':
                json_start_positions.append(i)
        
        for start_pos in reversed(json_start_positions):
            try:
                bracket_count = 0
                for end_pos in range(start_pos, len(content)):
                    if content[end_pos] == '{':
                        bracket_count += 1
                    elif content[end_pos] == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_candidate = content[start_pos:end_pos + 1]
                            
                            # 尝试解析以验证有效性
                            json.loads(json_candidate)
                            return json_candidate.strip()
            except (json.JSONDecodeError, IndexError):
                continue
        
        # 如果找不到有效的JSON，抛出异常
        raise InvalidEntityFormatException(
            "无法从响应中提取有效的JSON格式",
            details={
                'content_length': len(content),
                'content_preview': content[:200] + '...' if len(content) > 200 else content
            }
        )
    
    def _dict_to_entity(self, data: Dict[str, Any]) -> Optional[DrillHoleEntity]:
        """
        将字典转换为实体对象
        
        Args:
            data: 实体数据字典
        
        Returns:
            钻孔实体对象，如果数据无效则返回None
        """
        try:
            # 必需字段检查
            if not data.get('hole_id'):
                logger.warning(f"缺少hole_id字段: {data}")
                return None
            
            # 创建实体
            entity = DrillHoleEntity(
                hole_id=str(data.get('hole_id', '')),
                location_desc=data.get('location_desc'),
                confidence=data.get('confidence', 1.0),
                extracted_at=datetime.now()
            )
            
            # 处理设计参数
            if data.get('design_params'):
                dp = data['design_params']
                entity.design_params = DrillHoleDesignParams(
                    design_depth=self._safe_float(dp.get('design_depth')),
                    design_azimuth=self._safe_float(dp.get('design_azimuth')),
                    design_inclination=self._safe_float(dp.get('design_inclination')),
                    design_diameter=self._safe_float(dp.get('design_diameter')),
                    design_purpose=dp.get('design_purpose')
                )
            
            # 处理实际参数
            if data.get('actual_params'):
                ap = data['actual_params']
                entity.actual_params = DrillHoleActualParams(
                    actual_depth=self._safe_float(ap.get('actual_depth')),
                    actual_azimuth=self._safe_float(ap.get('actual_azimuth')),
                    actual_inclination=self._safe_float(ap.get('actual_inclination')),
                    actual_diameter=self._safe_float(ap.get('actual_diameter')),
                    start_formation=ap.get('start_formation'),
                    end_formation=ap.get('end_formation'),
                    drilling_date=ap.get('drilling_date')
                )
            
            return entity
            
        except Exception as e:
            logger.error(f"转换实体失败: {str(e)}, 数据: {data}")
            return None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """
        安全地将值转换为浮点数
        
        Args:
            value: 输入值
        
        Returns:
            浮点数或None
        """
        if value is None or value == '' or value == 'null':
            return None
        
        try:
            # 处理字符串中的数字
            if isinstance(value, str):
                # 移除单位和空格
                value = value.strip()
                value = value.replace('m', '').replace('米', '')
                value = value.replace('°', '').replace('度', '')
                value = value.replace('mm', '').replace('毫米', '')
                value = value.strip()
            
            return float(value)
        except (ValueError, TypeError):
            logger.debug(f"无法转换为浮点数: {value}")
            return None
    
    def _validate_entities(self, entities: List[DrillHoleEntity]) -> List[DrillHoleEntity]:
        """
        验证实体数据的有效性
        
        Args:
            entities: 实体列表
        
        Returns:
            验证后的实体列表
        """
        validated = []
        
        for entity in entities:
            # 基本验证
            if not entity.hole_id:
                logger.warning(f"实体缺少hole_id，跳过")
                continue
            
            # 验证数值范围
            if entity.design_params:
                dp = entity.design_params
                if dp.design_depth and (dp.design_depth < 0 or dp.design_depth > 10000):
                    logger.warning(f"设计深度异常: {dp.design_depth}")
                if dp.design_azimuth and (dp.design_azimuth < 0 or dp.design_azimuth >= 360):
                    logger.warning(f"设计方位角异常: {dp.design_azimuth}")
                if dp.design_inclination and (dp.design_inclination < -90 or dp.design_inclination > 90):
                    logger.warning(f"设计倾角异常: {dp.design_inclination}")
            
            if entity.actual_params:
                ap = entity.actual_params
                if ap.actual_depth and (ap.actual_depth < 0 or ap.actual_depth > 10000):
                    logger.warning(f"实际深度异常: {ap.actual_depth}")
                if ap.actual_azimuth and (ap.actual_azimuth < 0 or ap.actual_azimuth >= 360):
                    logger.warning(f"实际方位角异常: {ap.actual_azimuth}")
                if ap.actual_inclination and (ap.actual_inclination < -90 or ap.actual_inclination > 90):
                    logger.warning(f"实际倾角异常: {ap.actual_inclination}")
            
            validated.append(entity)
        
        return validated