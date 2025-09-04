"""
核心数据模型 - 6指标评估体系核心数据结构
"""

import math
import numpy as np
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class LLMModel(Enum):
    """支持的LLM模型枚举"""
    # DeepSeek系列
    DEEPSEEK_V3_OFFICIAL = "deepseek-V3"
    DEEPSEEK_R1_OFFICIAL = "deepseek-r1"
    DEEPSEEK_R1_DISTILL_QWEN_7B_ALIYUN = "deepseek-r1-distill-qwen-7b-aliyun"
    DEEPSEEK_R1_DISTILL_QWEN_14B_ALIYUN = "deepseek-r1-distill-qwen-14b-aliyun"
    DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN = "deepseek-r1-distill-qwen-32b-aliyun"
    
    # Qwen系列
    QWEN3_14B = "qwen3-14b"
    QWEN3_32B = "qwen3-32b"
    QWQ = "qwq-32b"
    QWEN_MAX = "qwen-max"
    
    # GPT系列
    GPT_35_TURBO_OPENROUTER = "gpt-3.5-turbo-openrouter"
    GPT_4O_MINI_OPENROUTER = "gpt-4o-mini-openrouter"


@dataclass
class DrillHoleDesignParams:
    """钻孔设计参数"""
    design_depth: Optional[float] = None
    design_azimuth: Optional[float] = None
    design_inclination: Optional[float] = None
    design_diameter: Optional[float] = None
    design_purpose: Optional[str] = None


@dataclass
class DrillHoleActualParams:
    """钻孔实际参数"""
    actual_depth: Optional[float] = None
    actual_azimuth: Optional[float] = None
    actual_inclination: Optional[float] = None
    actual_diameter: Optional[float] = None
    start_formation: Optional[str] = None
    end_formation: Optional[str] = None
    drilling_date: Optional[str] = None


@dataclass
class DrillHoleEntity:
    """钻孔实体"""
    hole_id: str
    location_desc: Optional[str] = None
    location_desc_direction_type: Optional[str] = None
    design_params: Optional[DrillHoleDesignParams] = None
    actual_params: Optional[DrillHoleActualParams] = None
    confidence: float = 1.0
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class Coordinate:
    """空间坐标"""
    x: float
    y: float
    z: float
    confidence: float = 1.0
    method: str = "unknown"

    def distance_to(self, other: 'Coordinate') -> float:
        """计算到另一个坐标的距离"""
        return math.sqrt(
            (self.x - other.x) ** 2 + 
            (self.y - other.y) ** 2 + 
            (self.z - other.z) ** 2
        )
    
    def to_tuple(self) -> Tuple[float, float, float]:
        """转换为元组"""
        return (self.x, self.y, self.z)


@dataclass
class ProcessResult:
    """处理结果"""
    document_name: str
    drill_holes: List[DrillHoleEntity]
    coordinates: Dict[str, Dict[str, Coordinate]]
    processing_time: float
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if not self.drill_holes:
            return 0.0
        with_coords = sum(1 for h in self.drill_holes if h.hole_id in self.coordinates)
        return with_coords / len(self.drill_holes)


@dataclass
class BaseMetricsData:
    """基础指标数据"""
    model_name: str
    document_name: str
    timestamp: datetime = field(default_factory=datetime.now)

    # 人工标注数据
    true_total_entities: Optional[int] = None
    true_entities_with_location: Optional[int] = None

    # 文档和提取统计
    document_token_length: Optional[int] = None
    extracted_entities_count: int = 0
    extracted_entities_with_location_count: int = 0
    unique_location_descriptions_count: int = 0
    unique_location_descriptions_processing_time: Optional[float] = None
    extracted_coordinates_count: int = 0
    extraction_density: Optional[float] = None

    # 时间统计
    entity_extraction_time: float = 0.0
    total_processing_time: float = 0.0


@dataclass
class SingleRunMetricsData(BaseMetricsData):
    """单轮运行数据"""
    location_processing_times: List[float] = field(default_factory=list)
    repetition_round: Optional[int] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AggregatedMetricsData(BaseMetricsData):
    """聚合数据"""
    total_repetitions: Optional[int] = None
    aggregation_method: str = "mean"
    processing_time_cv: Optional[float] = None


@dataclass
class SixMetricsScores:
    """6个核心指标"""
    extraction_recall: Optional[float] = None          # 提取召回率
    location_recall: Optional[float] = None            # 位置召回率
    coordinate_success_rate: Optional[float] = None    # 坐标成功率
    processing_stability: Optional[float] = None       # 处理稳定性
    efficiency_coefficient: Optional[float] = None     # 效率系数
    avg_location_processing_time: Optional[float] = None  # 平均位置处理时间
    
    def to_dict(self) -> Dict[str, Optional[float]]:
        """转换为字典"""
        return asdict(self)
    
    @property
    def is_complete(self) -> bool:
        """检查是否所有指标都已计算"""
        return all([
            self.extraction_recall is not None,
            self.location_recall is not None,
            self.coordinate_success_rate is not None,
            self.efficiency_coefficient is not None
        ])


@dataclass
class SingleRunMetrics:
    """单轮完整指标"""
    raw_data: SingleRunMetricsData
    scores: SixMetricsScores = field(default_factory=SixMetricsScores)

    def calculate_six_metrics(self) -> bool:
        """计算6指标"""
        return calculate_six_metrics_from_raw_data(self.raw_data, self.scores)


@dataclass
class AggregatedMetrics:
    """聚合完整指标"""
    raw_data: AggregatedMetricsData
    scores: SixMetricsScores = field(default_factory=SixMetricsScores)


@dataclass
class GroundTruthData:
    """人工标注数据"""
    document_filename: str
    true_total_entities_count: int
    true_entities_with_location_count: int


@dataclass
class VerificationData:
    """坐标验证数据"""
    document_filename: str
    model_name: str
    repetition_round: int
    manually_verified_correct_coordinates_count: int


def calculate_six_metrics_from_raw_data(
    raw_data: BaseMetricsData, 
    scores: SixMetricsScores
) -> bool:
    """从原始数据计算6指标的通用方法"""
    calculated_count = 0

    # 1. 提取召回率
    if raw_data.true_total_entities and raw_data.true_total_entities > 0:
        scores.extraction_recall = (
            raw_data.extracted_entities_count / raw_data.true_total_entities
        )
        calculated_count += 1

    # 2. 位置召回率
    if raw_data.true_entities_with_location and raw_data.true_entities_with_location > 0:
        scores.location_recall = (
            raw_data.extracted_entities_with_location_count / 
            raw_data.true_entities_with_location
        )
        calculated_count += 1

    # 3. 坐标成功率
    if raw_data.true_entities_with_location and raw_data.true_entities_with_location > 0:
        scores.coordinate_success_rate = (
            raw_data.extracted_coordinates_count / 
            raw_data.true_entities_with_location
        )
        calculated_count += 1

    # 4. 效率系数
    if (raw_data.extraction_density and 
        raw_data.extraction_density > 0 and 
        raw_data.entity_extraction_time > 0):
        scores.efficiency_coefficient = (
            raw_data.entity_extraction_time / raw_data.extraction_density
        )
        calculated_count += 1

    return calculated_count >= 4

def calculate_drill_hole_endpoint(
    start_x: float, 
    start_y: float, 
    start_z: float,
    azimuth: float, 
    inclination: float,  # 文档中的倾角θ，有正负
    depth: float         # 文档中的L
) -> Tuple[float, float, float]:
    """
    计算钻孔终点坐标
    
    Args:
        start_x: 起点X坐标
        start_y: 起点Y坐标  
        start_z: 起点Z坐标
        azimuth: 方位角（度）
        inclination: 倾角（度）
        depth: 深度（米）
    
    Returns:
        终点坐标(x, y, z)
    """
    
    azimuth_rad = math.radians(azimuth)
    inclination_rad = math.radians(inclination)
    
    delta_x = depth * math.cos(inclination_rad) * math.sin(azimuth_rad)
    delta_y = depth * math.cos(inclination_rad) * math.cos(azimuth_rad)
    delta_z = depth * math.sin(inclination_rad)
    
    return start_x + delta_x, start_y + delta_y, start_z + delta_z