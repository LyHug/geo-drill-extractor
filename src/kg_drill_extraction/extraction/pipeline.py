"""
提取流水线模块 - 协调文档处理、实体提取和坐标推理
"""

import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .document_processor import DocumentProcessor
from .entity_extractor import EntityExtractor
from .coordinate_inferencer import CoordinateInferencer
from ..core import (
    LLMModel,
    ProcessResult,
    DrillHoleEntity,
    Coordinate,
    get_config_loader
)
from ..core.exceptions import (
    ExtractionException,
    DocumentException,
    LLMException
)
from ..llm import LLMClientFactory, BaseLLMClient

logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """
    提取流水线
    
    协调整个提取过程，从文档处理到实体提取再到坐标推理
    """
    
    def __init__(
        self,
        model: Optional[LLMModel] = None,
        llm_client: Optional[BaseLLMClient] = None,
        config_loader: Optional[Any] = None,
        survey_points_file: Optional[str] = None,
        enable_cache: bool = False,
        stream_mode: bool = False
    ):
        """
        初始化提取流水线
        
        Args:
            model: LLM模型枚举（如果提供llm_client则忽略）
            llm_client: LLM客户端实例（优先使用）
            config_loader: 配置加载器
            survey_points_file: 导线点文件路径
            enable_cache: 是否启用缓存（实验时建议关闭）
            stream_mode: 是否启用流式输出显示
        """
        # 获取配置
        self.config_loader = config_loader or get_config_loader()
        
        # 初始化LLM客户端
        if llm_client:
            self.llm_client = llm_client
            self.model = llm_client.model if hasattr(llm_client, 'model') else None
        elif model:
            self.model = model
            self.llm_client = LLMClientFactory.create(model, self.config_loader)
        else:
            # 使用默认模型
            default_model_name = self.config_loader.get('llm.default_model')
            self.model = self._get_model_enum(default_model_name)
            self.llm_client = LLMClientFactory.create(self.model, self.config_loader)
        
        # 获取数据路径
        data_paths = self.config_loader.get_data_paths()
        if not survey_points_file:
            survey_points_file = data_paths.get('survey_points_file')
        
        # 初始化组件
        self.document_processor = DocumentProcessor()
        self.entity_extractor = EntityExtractor(
            llm_client=self.llm_client,
            enable_cache=enable_cache,
            stream_mode=stream_mode
        )
        self.coordinate_inferencer = CoordinateInferencer(
            survey_points_file=survey_points_file,
            llm_client=self.llm_client,
            enable_cache=enable_cache,
            stream_mode=stream_mode
        )
        
        self.enable_cache = enable_cache
        self.stream_mode = stream_mode
        logger.info(f"ExtractionPipeline初始化完成，模型: {self.model}")
    
    def _get_model_enum(self, model_name: str) -> LLMModel:
        """
        将模型名称转换为枚举
        
        Args:
            model_name: 模型名称字符串
        
        Returns:
            LLM模型枚举
        """
        # 尝试直接匹配
        for model in LLMModel:
            if model.value == model_name:
                return model
        
        # 尝试名称匹配
        for model in LLMModel:
            if model.name == model_name.upper().replace('-', '_'):
                return model
        
        # 默认模型
        logger.warning(f"未找到模型 {model_name}，使用默认模型")
        return LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN
    
    def process_document(self, file_path: Union[str, Path]) -> ProcessResult:
        """
        处理单个文档
        
        Args:
            file_path: 文档文件路径
        
        Returns:
            处理结果对象
        
        Raises:
            DocumentException: 文档处理异常
            ExtractionException: 提取异常
        """
        file_path = Path(file_path)
        doc_name = file_path.name
        
        logger.info(f"开始处理文档: {doc_name}")
        start_time = time.time()
        
        errors = []
        drill_holes = []
        coordinates = {}
        metadata = {
            'model': self.model.value if self.model else 'unknown',
            'file_path': str(file_path.absolute()),
            'file_size': file_path.stat().st_size if file_path.exists() else 0
        }
        
        try:
            # 1. 文档处理
            logger.info(f"步骤1: 转换文档为Markdown")
            markdown_text = self.document_processor.process_document(str(file_path))
            metadata['markdown_length'] = len(markdown_text)
            
            # 2. 实体提取
            logger.info(f"步骤2: 提取钻孔实体")
            entity_start_time = time.time()
            drill_holes = self.entity_extractor.extract_entities(markdown_text, doc_name)
            entity_extraction_time = time.time() - entity_start_time
            metadata['entity_extraction_time'] = entity_extraction_time
            metadata['entity_count'] = len(drill_holes)
            
            # 3. 坐标推理
            logger.info(f"步骤3: 推断空间坐标")
            coord_start_time = time.time()
            coordinates, timing_stats = self.coordinate_inferencer.infer_coordinates(drill_holes)
            coord_inference_time = time.time() - coord_start_time
            metadata['coord_inference_time'] = coord_inference_time
            metadata['coordinate_count'] = len(coordinates)
            metadata.update(timing_stats)
            
        except DocumentException as e:
            logger.error(f"文档处理失败: {str(e)}")
            errors.append({
                'type': 'DocumentException',
                'message': str(e),
                'details': e.details if hasattr(e, 'details') else {}
            })
        except ExtractionException as e:
            logger.error(f"实体提取失败: {str(e)}")
            errors.append({
                'type': 'ExtractionException',
                'message': str(e),
                'details': e.details if hasattr(e, 'details') else {}
            })
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            errors.append({
                'type': 'UnknownError',
                'message': str(e)
            })
        
        # 计算总处理时间
        total_time = time.time() - start_time
        
        # 构建结果
        result = ProcessResult(
            document_name=doc_name,
            drill_holes=drill_holes,
            coordinates=coordinates,
            processing_time=total_time,
            errors=errors,
            metadata=metadata
        )
        
        # 日志汇总
        logger.info(f"文档处理完成: {doc_name}")
        logger.info(f"  - 提取实体: {len(drill_holes)} 个")
        logger.info(f"  - 推断坐标: {len(coordinates)} 个")
        logger.info(f"  - 处理时间: {total_time:.2f} 秒")
        if errors:
            logger.warning(f"  - 错误数量: {len(errors)} 个")
        
        return result
    
    def process_documents_batch(
        self,
        file_paths: List[Union[str, Path]],
        max_workers: Optional[int] = None
    ) -> List[ProcessResult]:
        """
        批量处理文档
        
        Args:
            file_paths: 文档文件路径列表
            max_workers: 最大并行数（None表示串行处理）
        
        Returns:
            处理结果列表
        """
        results = []
        
        if max_workers and max_workers > 1:
            # 并行处理
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                future_to_path = {
                    executor.submit(self.process_document, path): path
                    for path in file_paths
                }
                
                # 收集结果
                for future in as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"处理文档失败 {path}: {str(e)}")
                        # 创建错误结果
                        results.append(ProcessResult(
                            document_name=Path(path).name,
                            drill_holes=[],
                            coordinates={},
                            processing_time=0,
                            errors=[{
                                'type': 'ProcessingError',
                                'message': str(e)
                            }]
                        ))
        else:
            # 串行处理
            for path in file_paths:
                try:
                    result = self.process_document(path)
                    results.append(result)
                except Exception as e:
                    logger.error(f"处理文档失败 {path}: {str(e)}")
                    results.append(ProcessResult(
                        document_name=Path(path).name,
                        drill_holes=[],
                        coordinates={},
                        processing_time=0,
                        errors=[{
                            'type': 'ProcessingError',
                            'message': str(e)
                        }]
                    ))
        
        return results
    
    def get_statistics(self, results: List[ProcessResult]) -> Dict[str, Any]:
        """
        获取处理统计信息
        
        Args:
            results: 处理结果列表
        
        Returns:
            统计信息字典
        """
        total_entities = sum(len(r.drill_holes) for r in results)
        total_coordinates = sum(len(r.coordinates) for r in results)
        total_errors = sum(len(r.errors) for r in results)
        total_time = sum(r.processing_time for r in results)
        
        successful_docs = sum(1 for r in results if not r.errors)
        failed_docs = sum(1 for r in results if r.errors)
        
        return {
            'total_documents': len(results),
            'successful_documents': successful_docs,
            'failed_documents': failed_docs,
            'total_entities': total_entities,
            'total_coordinates': total_coordinates,
            'total_errors': total_errors,
            'total_processing_time': total_time,
            'avg_processing_time': total_time / len(results) if results else 0,
            'avg_entities_per_doc': total_entities / len(results) if results else 0,
            'coordinate_success_rate': total_coordinates / total_entities if total_entities else 0
        }