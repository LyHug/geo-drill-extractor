"""
真值数据加载器 - 管理人工标注的真值数据
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

from ..core import GroundTruthData, VerificationData
from ..core.exceptions import (
    DataException,
    ValidationException
)

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthStats:
    """真值数据统计"""
    total_documents: int
    total_entities: int
    total_entities_with_location: int
    avg_entities_per_doc: float
    location_coverage_rate: float


class GroundTruthLoader:
    """
    人工标注数据加载器
    
    负责加载和管理人工标注的真值数据，包括实体数量和坐标验证数据
    """
    
    def __init__(
        self, 
        annotations_file: Optional[str] = None,
        verification_file: Optional[str] = None
    ):
        """
        初始化真值数据加载器
        
        Args:
            annotations_file: 基础标注文件路径
            verification_file: 坐标验证文件路径（可选）
        """
        # 设置默认路径
        self.annotations_file = Path(annotations_file) if annotations_file else Path('./data/ground_truth_annotations.csv')
        self.verification_file = Path(verification_file) if verification_file else Path('./data/coordinate_verification_results.csv')
        
        # 数据存储
        self.annotations: Dict[str, GroundTruthData] = {}
        self.verifications: Dict[str, List[VerificationData]] = {}
        
        # 加载数据
        self._load_annotations()
        self._load_verifications()
    
    def _load_annotations(self):
        """加载基础标注数据"""
        if not self.annotations_file.exists():
            logger.warning(f"标注文件不存在: {self.annotations_file}")
            return
        
        try:
            df = pd.read_csv(self.annotations_file, encoding='utf-8')
            
            # 验证必需列
            required_columns = ['document_filename', 'true_total_entities_count', 'true_entities_with_location_count']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValidationException(
                    f"Missing required columns in annotations: {missing_columns}",
                    details={'available_columns': list(df.columns)}
                )
            
            # 加载数据
            for _, row in df.iterrows():
                doc_name = row['document_filename']
                
                # 数据验证
                total_entities = int(row['true_total_entities_count'])
                entities_with_location = int(row['true_entities_with_location_count'])
                
                if total_entities < 0 or entities_with_location < 0:
                    logger.warning(f"文档 {doc_name} 的实体数量为负数")
                    continue
                
                if entities_with_location > total_entities:
                    logger.warning(f"文档 {doc_name} 的位置实体数量超过总实体数量")
                    entities_with_location = total_entities
                
                self.annotations[doc_name] = GroundTruthData(
                    document_filename=doc_name,
                    true_total_entities_count=total_entities,
                    true_entities_with_location_count=entities_with_location
                )
            
            logger.info(f"成功加载 {len(self.annotations)} 个文档的标注数据")
            
        except Exception as e:
            if isinstance(e, DataException):
                raise
            raise ValidationException(
                f"Failed to load annotations: {str(e)}",
                details={'file': str(self.annotations_file)}
            )
    
    def _load_verifications(self):
        """加载坐标验证数据"""
        if not self.verification_file.exists():
            logger.info(f"坐标验证文件不存在: {self.verification_file}")
            return
        
        try:
            df = pd.read_csv(self.verification_file, encoding='utf-8')
            
            # 验证必需列
            required_columns = ['document_filename', 'model_name', 'repetition_round', 'manually_verified_correct_coordinates_count']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                logger.warning(f"坐标验证文件缺少列: {missing_columns}")
                return
            
            # 按文档分组
            for _, row in df.iterrows():
                doc_name = row['document_filename']
                
                verification = VerificationData(
                    document_filename=doc_name,
                    model_name=row['model_name'],
                    repetition_round=int(row['repetition_round']),
                    manually_verified_correct_coordinates_count=int(row['manually_verified_correct_coordinates_count'])
                )
                
                if doc_name not in self.verifications:
                    self.verifications[doc_name] = []
                self.verifications[doc_name].append(verification)
            
            logger.info(f"成功加载 {len(self.verifications)} 个文档的坐标验证数据")
            
        except Exception as e:
            logger.error(f"加载坐标验证数据失败: {str(e)}")
    
    def get_annotation(self, document_filename: str) -> Optional[GroundTruthData]:
        """
        获取文档的标注数据
        
        Args:
            document_filename: 文档文件名
        
        Returns:
            真值数据对象，如果不存在则返回None
        """
        return self.annotations.get(document_filename)
    
    def get_verification(
        self, 
        document_filename: str, 
        model_name: Optional[str] = None,
        repetition_round: Optional[int] = None
    ) -> List[VerificationData]:
        """
        获取文档的验证数据
        
        Args:
            document_filename: 文档文件名
            model_name: 模型名称（可选）
            repetition_round: 重复轮次（可选）
        
        Returns:
            验证数据列表
        """
        verifications = self.verifications.get(document_filename, [])
        
        # 过滤条件
        if model_name:
            verifications = [v for v in verifications if v.model_name == model_name]
        
        if repetition_round is not None:
            verifications = [v for v in verifications if v.repetition_round == repetition_round]
        
        return verifications
    
    def load_ground_truth(self) -> Dict[str, GroundTruthData]:
        """
        获取所有标注数据
        
        Returns:
            文档名到真值数据的映射
        """
        return self.annotations.copy()
    
    def get_statistics(self) -> GroundTruthStats:
        """
        获取真值数据统计信息
        
        Returns:
            统计信息对象
        """
        if not self.annotations:
            return GroundTruthStats(
                total_documents=0,
                total_entities=0,
                total_entities_with_location=0,
                avg_entities_per_doc=0.0,
                location_coverage_rate=0.0
            )
        
        total_docs = len(self.annotations)
        total_entities = sum(data.true_total_entities_count for data in self.annotations.values())
        total_entities_with_location = sum(data.true_entities_with_location_count for data in self.annotations.values())
        
        avg_entities = total_entities / total_docs if total_docs > 0 else 0
        location_rate = total_entities_with_location / total_entities if total_entities > 0 else 0
        
        return GroundTruthStats(
            total_documents=total_docs,
            total_entities=total_entities,
            total_entities_with_location=total_entities_with_location,
            avg_entities_per_doc=avg_entities,
            location_coverage_rate=location_rate
        )
    
    def validate_data(self) -> List[str]:
        """
        验证数据完整性
        
        Returns:
            验证错误列表
        """
        errors = []
        
        # 检查标注数据
        if not self.annotations:
            errors.append("未加载标注数据")
        
        # 检查数据一致性
        for doc_name, data in self.annotations.items():
            if data.true_entities_with_location_count > data.true_total_entities_count:
                errors.append(f"文档 {doc_name} 的位置实体数量超过总实体数量")
            
            if data.true_total_entities_count == 0:
                errors.append(f"文档 {doc_name} 的总实体数量为0")
        
        return errors
    
    def get_documents_list(self) -> List[str]:
        """获取所有有标注数据的文档列表"""
        return list(self.annotations.keys())
    
    def has_annotation(self, document_filename: str) -> bool:
        """检查文档是否有标注数据"""
        return document_filename in self.annotations