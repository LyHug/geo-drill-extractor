"""
指标处理器 - 计算6指标评估体系的核心指标
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any, Union
from collections import defaultdict

from .ground_truth import GroundTruthLoader
from .tokenizer import get_tokenizer_manager
from ..core import (
    ProcessResult,
    SingleRunMetrics,
    SingleRunMetricsData,
    AggregatedMetrics,
    AggregatedMetricsData,
    SixMetricsScores,
    LLMModel,
    calculate_six_metrics_from_raw_data
)
from ..core.exceptions import (
    EvaluationException,
    DataException
)

logger = logging.getLogger(__name__)


class SixMetricsProcessor:
    """
    6指标处理器
    
    负责计算和聚合6指标评估体系的所有指标，包括：
    1. 提取召回率
    2. 位置召回率  
    3. 坐标成功率
    4. 处理稳定性
    5. 效率系数
    6. 平均位置处理时间
    """
    
    def __init__(self, ground_truth_loader: Optional[GroundTruthLoader] = None):
        """
        初始化指标处理器
        
        Args:
            ground_truth_loader: 真值数据加载器
        """
        self.ground_truth_loader = ground_truth_loader
        self.tokenizer_manager = get_tokenizer_manager()
    
    def process_result_to_metrics(
        self,
        result: ProcessResult,
        model: LLMModel,
        repetition_round: Optional[int] = None,
        document_text: Optional[str] = None
    ) -> SingleRunMetrics:
        """
        将处理结果转换为单轮指标
        
        Args:
            result: 处理结果对象
            model: 使用的模型
            repetition_round: 重复轮次
            document_text: 原始文档文本（用于token计算）
        
        Returns:
            单轮指标对象
        
        Raises:
            MetricsCalculationException: 指标计算失败
        """
        try:
            # 获取真值数据
            ground_truth = None
            if self.ground_truth_loader:
                ground_truth = self.ground_truth_loader.get_annotation(result.document_name)
            
            # 创建基础指标数据
            metrics_data = SingleRunMetricsData(
                model_name=model.value,
                document_name=result.document_name,
                repetition_round=repetition_round
            )
            
            # 设置真值数据
            if ground_truth:
                metrics_data.true_total_entities = ground_truth.true_total_entities_count
                metrics_data.true_entities_with_location = ground_truth.true_entities_with_location_count
            
            # 计算文档token长度
            if document_text:
                metrics_data.document_token_length = self.tokenizer_manager.calculate_tokens(
                    document_text, model
                )
            
            # 提取统计信息
            metrics_data.extracted_entities_count = len(result.drill_holes)
            metrics_data.extracted_entities_with_location_count = sum(
                1 for hole in result.drill_holes if hole.location_desc
            )
            
            # 坐标统计
            metrics_data.extracted_coordinates_count = len(result.coordinates)
            
            # 时间统计
            metrics_data.total_processing_time = result.processing_time
            
            # 从结果元数据中提取更多信息
            metadata = result.metadata or {}
            metrics_data.entity_extraction_time = metadata.get('entity_extraction_time', 0)
            
            # 位置处理时间统计
            if 'location_processing_times' in metadata:
                metrics_data.location_processing_times = metadata['location_processing_times']
                
            metrics_data.unique_location_descriptions_count = metadata.get(
                'unique_location_descriptions_count', 0
            )
            metrics_data.unique_location_descriptions_processing_time = metadata.get(
                'total_location_processing_time', 0
            )
            
            # 计算提取密度
            if metrics_data.document_token_length and metrics_data.document_token_length > 0:
                metrics_data.extraction_density = (
                    metrics_data.extracted_entities_count / metrics_data.document_token_length
                ) * 1000  # 每1000个token的实体数
            
            # 记录错误
            metrics_data.errors = result.errors
            
            # 创建指标对象
            metrics = SingleRunMetrics(
                raw_data=metrics_data,
                scores=SixMetricsScores()
            )
            
            # 计算6指标
            self._calculate_six_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            raise EvaluationException(
                f"Failed to calculate metrics for {result.document_name}: {str(e)}",
                details={
                    'document': result.document_name,
                    'model': model.value,
                    'repetition_round': repetition_round
                }
            )
    
    def _calculate_six_metrics(self, metrics: SingleRunMetrics):
        """
        计算6个核心指标
        
        Args:
            metrics: 单轮指标对象（会被修改）
        """
        data = metrics.raw_data
        scores = metrics.scores
        
        # 使用核心模块的通用计算函数
        calculate_six_metrics_from_raw_data(data, scores)
        
        # 计算平均位置处理时间
        if data.location_processing_times:
            scores.avg_location_processing_time = np.mean(data.location_processing_times)
        elif data.unique_location_descriptions_processing_time and data.unique_location_descriptions_count > 0:
            scores.avg_location_processing_time = (
                data.unique_location_descriptions_processing_time / 
                data.unique_location_descriptions_count
            )
    
    def aggregate_metrics(
        self,
        single_run_metrics: List[SingleRunMetrics],
        aggregation_method: str = "mean"
    ) -> AggregatedMetrics:
        """
        聚合多轮指标数据
        
        Args:
            single_run_metrics: 单轮指标列表
            aggregation_method: 聚合方法（mean, median等）
        
        Returns:
            聚合指标对象
        
        Raises:
            InsufficientDataException: 数据不足
        """
        if not single_run_metrics:
            raise DataException("No metrics data to aggregate")
        
        # 检查数据一致性
        first_metric = single_run_metrics[0]
        model_name = first_metric.raw_data.model_name
        doc_name = first_metric.raw_data.document_name
        
        for metric in single_run_metrics[1:]:
            if metric.raw_data.model_name != model_name:
                raise EvaluationException("Inconsistent model names in metrics")
            if metric.raw_data.document_name != doc_name:
                raise EvaluationException("Inconsistent document names in metrics")
        
        # 创建聚合数据
        aggregated_data = AggregatedMetricsData(
            model_name=model_name,
            document_name=doc_name,
            total_repetitions=len(single_run_metrics),
            aggregation_method=aggregation_method
        )
        
        # 聚合基础数据（使用第一轮的静态数据）
        first_data = first_metric.raw_data
        aggregated_data.true_total_entities = first_data.true_total_entities
        aggregated_data.true_entities_with_location = first_data.true_entities_with_location
        aggregated_data.document_token_length = first_data.document_token_length
        
        # 聚合变化数据
        if aggregation_method == "mean":
            aggregated_data = self._aggregate_mean(single_run_metrics, aggregated_data)
        elif aggregation_method == "median":
            aggregated_data = self._aggregate_median(single_run_metrics, aggregated_data)
        else:
            raise EvaluationException(f"Unsupported aggregation method: {aggregation_method}")
        
        # 创建聚合指标
        aggregated_metrics = AggregatedMetrics(
            raw_data=aggregated_data,
            scores=SixMetricsScores()
        )
        
        # 聚合分数
        self._aggregate_scores(single_run_metrics, aggregated_metrics, aggregation_method)
        
        return aggregated_metrics
    
    def _aggregate_mean(
        self,
        metrics_list: List[SingleRunMetrics],
        aggregated_data: AggregatedMetricsData
    ) -> AggregatedMetricsData:
        """使用平均值聚合数据"""
        # 提取所有数值
        extracted_counts = [m.raw_data.extracted_entities_count for m in metrics_list]
        location_counts = [m.raw_data.extracted_entities_with_location_count for m in metrics_list]
        coord_counts = [m.raw_data.extracted_coordinates_count for m in metrics_list]
        processing_times = [m.raw_data.total_processing_time for m in metrics_list]
        entity_extraction_times = [m.raw_data.entity_extraction_time for m in metrics_list]
        
        # 计算平均值
        aggregated_data.extracted_entities_count = int(np.mean(extracted_counts))
        aggregated_data.extracted_entities_with_location_count = int(np.mean(location_counts))
        aggregated_data.extracted_coordinates_count = int(np.mean(coord_counts))
        aggregated_data.total_processing_time = np.mean(processing_times)
        aggregated_data.entity_extraction_time = np.mean(entity_extraction_times)
        
        # 计算处理时间稳定性（变异系数）
        if len(processing_times) > 1:
            cv = np.std(processing_times) / np.mean(processing_times)
            aggregated_data.processing_time_cv = cv
        
        # 聚合位置处理时间
        all_location_times = []
        unique_counts = []
        unique_total_times = []
        
        for metric in metrics_list:
            if metric.raw_data.location_processing_times:
                all_location_times.extend(metric.raw_data.location_processing_times)
            if metric.raw_data.unique_location_descriptions_count:
                unique_counts.append(metric.raw_data.unique_location_descriptions_count)
            if metric.raw_data.unique_location_descriptions_processing_time:
                unique_total_times.append(metric.raw_data.unique_location_descriptions_processing_time)
        
        if unique_counts:
            aggregated_data.unique_location_descriptions_count = int(np.mean(unique_counts))
        if unique_total_times:
            aggregated_data.unique_location_descriptions_processing_time = np.mean(unique_total_times)
        
        # 计算提取密度
        if aggregated_data.document_token_length and aggregated_data.document_token_length > 0:
            aggregated_data.extraction_density = (
                aggregated_data.extracted_entities_count / aggregated_data.document_token_length
            ) * 1000
        
        return aggregated_data
    
    def _aggregate_median(
        self,
        metrics_list: List[SingleRunMetrics],
        aggregated_data: AggregatedMetricsData
    ) -> AggregatedMetricsData:
        """使用中位数聚合数据"""
        # 提取所有数值
        extracted_counts = [m.raw_data.extracted_entities_count for m in metrics_list]
        location_counts = [m.raw_data.extracted_entities_with_location_count for m in metrics_list]
        coord_counts = [m.raw_data.extracted_coordinates_count for m in metrics_list]
        processing_times = [m.raw_data.total_processing_time for m in metrics_list]
        entity_extraction_times = [m.raw_data.entity_extraction_time for m in metrics_list]
        
        # 计算中位数
        aggregated_data.extracted_entities_count = int(np.median(extracted_counts))
        aggregated_data.extracted_entities_with_location_count = int(np.median(location_counts))
        aggregated_data.extracted_coordinates_count = int(np.median(coord_counts))
        aggregated_data.total_processing_time = np.median(processing_times)
        aggregated_data.entity_extraction_time = np.median(entity_extraction_times)
        
        # 其他逻辑与mean类似
        return self._aggregate_mean(metrics_list, aggregated_data)  # 复用部分逻辑
    
    def _aggregate_scores(
        self,
        metrics_list: List[SingleRunMetrics],
        aggregated_metrics: AggregatedMetrics,
        method: str
    ):
        """聚合分数"""
        scores_data = {
            'extraction_recall': [],
            'location_recall': [],
            'coordinate_success_rate': [],
            'processing_stability': [],
            'efficiency_coefficient': [],
            'avg_location_processing_time': []
        }
        
        # 收集所有分数
        for metric in metrics_list:
            scores = metric.scores
            if scores.extraction_recall is not None:
                scores_data['extraction_recall'].append(scores.extraction_recall)
            if scores.location_recall is not None:
                scores_data['location_recall'].append(scores.location_recall)
            if scores.coordinate_success_rate is not None:
                scores_data['coordinate_success_rate'].append(scores.coordinate_success_rate)
            if scores.efficiency_coefficient is not None:
                scores_data['efficiency_coefficient'].append(scores.efficiency_coefficient)
            if scores.avg_location_processing_time is not None:
                scores_data['avg_location_processing_time'].append(scores.avg_location_processing_time)
        
        # 聚合分数
        agg_func = np.mean if method == "mean" else np.median
        
        if scores_data['extraction_recall']:
            aggregated_metrics.scores.extraction_recall = agg_func(scores_data['extraction_recall'])
        if scores_data['location_recall']:
            aggregated_metrics.scores.location_recall = agg_func(scores_data['location_recall'])
        if scores_data['coordinate_success_rate']:
            aggregated_metrics.scores.coordinate_success_rate = agg_func(scores_data['coordinate_success_rate'])
        if scores_data['efficiency_coefficient']:
            aggregated_metrics.scores.efficiency_coefficient = agg_func(scores_data['efficiency_coefficient'])
        if scores_data['avg_location_processing_time']:
            aggregated_metrics.scores.avg_location_processing_time = agg_func(scores_data['avg_location_processing_time'])
        
        # 处理稳定性使用变异系数
        if aggregated_metrics.raw_data.processing_time_cv is not None:
            # 稳定性分数 = 1 - 变异系数（值越小越稳定）
            aggregated_metrics.scores.processing_stability = max(0, 1 - aggregated_metrics.raw_data.processing_time_cv)
    
    def batch_process_results(
        self,
        results_by_model: Dict[str, List[ProcessResult]],
        documents_content: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[AggregatedMetrics]]:
        """
        批量处理结果并生成聚合指标
        
        Args:
            results_by_model: 按模型分组的结果
            documents_content: 文档内容映射（可选，用于token计算）
        
        Returns:
            按模型分组的聚合指标
        """
        metrics_by_model = defaultdict(list)
        
        for model_name, results in results_by_model.items():
            try:
                # 解析模型枚举
                model_enum = self._get_model_enum(model_name)
                
                # 按文档分组
                doc_groups = defaultdict(list)
                for result in results:
                    doc_groups[result.document_name].append(result)
                
                # 处理每个文档组
                for doc_name, doc_results in doc_groups.items():
                    try:
                        # 转换为单轮指标
                        single_metrics = []
                        doc_text = documents_content.get(doc_name, "") if documents_content else None
                        
                        for i, result in enumerate(doc_results):
                            metric = self.process_result_to_metrics(
                                result=result,
                                model=model_enum,
                                repetition_round=i + 1,
                                document_text=doc_text
                            )
                            single_metrics.append(metric)
                        
                        # 聚合指标
                        if single_metrics:
                            aggregated = self.aggregate_metrics(single_metrics)
                            metrics_by_model[model_name].append(aggregated)
                            
                    except Exception as e:
                        logger.error(f"处理文档 {doc_name} 的指标失败: {str(e)}")
                        
            except Exception as e:
                logger.error(f"处理模型 {model_name} 的结果失败: {str(e)}")
        
        return dict(metrics_by_model)
    
    def _get_model_enum(self, model_name: str) -> LLMModel:
        """将模型名称转换为枚举"""
        # 尝试直接匹配
        for model in LLMModel:
            if model.value == model_name or model.name == model_name:
                return model
        
        # 默认返回
        logger.warning(f"未找到模型枚举: {model_name}")
        return LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN
    
    def validate_metrics(
        self, 
        metrics: Union[SingleRunMetrics, AggregatedMetrics]
    ) -> List[str]:
        """
        验证指标数据
        
        Args:
            metrics: 指标对象
        
        Returns:
            验证错误列表
        """
        errors = []
        
        if not metrics.raw_data.model_name:
            errors.append("模型名称不能为空")
        if not metrics.raw_data.document_name:
            errors.append("文档名称不能为空")
        if metrics.raw_data.extracted_entities_count < 0:
            errors.append("提取实体数量不能为负数")
        if metrics.scores.extraction_recall is not None and not (0 <= metrics.scores.extraction_recall <= 2.0):
            errors.append("提取召回率超出合理范围")
        if metrics.scores.coordinate_success_rate is not None and not (0 <= metrics.scores.coordinate_success_rate <= 1.0):
            errors.append("坐标成功率超出合理范围")
        
        return errors
    
    def calculate_comprehensive_scores(
        self, 
        metrics_list: List[Union[SingleRunMetrics, AggregatedMetrics]]
    ) -> Dict[str, float]:
        """
        计算综合得分
        
        Args:
            metrics_list: 指标列表
            
        Returns:
            综合得分字典
        """
        if not metrics_list:
            return {}
        
        # 权重配置
        weights = {
            'coordinate_success_rate': 0.30,
            'extraction_recall': 0.25,
            'efficiency_coefficient': 0.20,  # 越小越好
            'location_recall': 0.15,
            'processing_stability': 0.05,
            'avg_location_processing_time': 0.05  # 越小越好
        }
        
        scores = {}
        for metric_name, weight in weights.items():
            values = [getattr(m.scores, metric_name) for m in metrics_list
                      if getattr(m.scores, metric_name, None) is not None]
            if values:
                if metric_name in ['efficiency_coefficient', 'avg_location_processing_time']:
                    # 越小越好的指标，取倒数
                    normalized_score = 1.0 / (1.0 + np.mean(values))
                else:
                    normalized_score = np.mean(values)
                scores[metric_name] = normalized_score * weight
        
        return {
            'individual_scores': scores,
            'comprehensive_score': sum(scores.values()),
            'total_weight_used': sum(weights[k] for k in scores.keys())
        }
    
    def get_metrics_summary(
        self, 
        metrics_list: List[Union[SingleRunMetrics, AggregatedMetrics]]
    ) -> Dict[str, Any]:
        """
        获取指标摘要
        
        Args:
            metrics_list: 指标列表
            
        Returns:
            摘要信息字典
        """
        if not metrics_list:
            return {}
        
        # 区分单轮和聚合数据
        single_run_count = sum(1 for m in metrics_list if isinstance(m, SingleRunMetrics))
        aggregated_count = sum(1 for m in metrics_list if isinstance(m, AggregatedMetrics))
        
        # 计算各指标的统计信息
        metric_stats = {}
        for metric_name in ['extraction_recall', 'location_recall', 'coordinate_success_rate',
                            'processing_stability', 'efficiency_coefficient', 'avg_location_processing_time']:
            values = [getattr(m.scores, metric_name) for m in metrics_list
                      if getattr(m.scores, metric_name, None) is not None]
            if values:
                metric_stats[metric_name] = {
                    'count': len(values),
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values)
                }
        
        return {
            'total_metrics': len(metrics_list),
            'single_run_count': single_run_count,
            'aggregated_count': aggregated_count,
            'metric_statistics': metric_stats,
            'comprehensive_scores': self.calculate_comprehensive_scores(metrics_list)
        }