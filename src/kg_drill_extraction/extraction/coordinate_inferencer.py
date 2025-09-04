"""
坐标推理器模块 - 基于导线点和位置描述推断空间坐标
"""

import json
import time
import math
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from .prompts import LOCATION_ANALYSIS_PROMPT
from ..core import (
    DrillHoleEntity,
    Coordinate,
    calculate_drill_hole_endpoint
)
from ..core.exceptions import (
    CoordinateInferenceException,
    DataException,
    SurveyPointsNotFoundException,
    InvalidSurveyPointsException
)
from ..llm import BaseLLMClient

logger = logging.getLogger(__name__)


class CoordinateInferencer:
    """
    坐标推理器
    
    基于导线点数据和自然语言位置描述推断钻孔的空间坐标
    """
    
    def __init__(
        self, 
        survey_points_file: str,
        llm_client: BaseLLMClient,
        enable_cache: bool = False,
        stream_mode: bool = False
    ):
        """
        初始化坐标推理器
        
        Args:
            survey_points_file: 导线点文件路径
            llm_client: LLM客户端实例
            enable_cache: 是否启用缓存
            stream_mode: 是否启用流式输出显示
        """
        self.llm_client = llm_client
        self.enable_cache = enable_cache
        self.stream_mode = stream_mode
        self.survey_points = None
        self.point_dict = {}
        self._location_analysis_cache = {} if enable_cache else None
        
        # 加载导线点数据
        self._load_survey_points(survey_points_file)
    
    def _load_survey_points(self, file_path: str):
        """
        加载导线点数据
        
        Args:
            file_path: 导线点文件路径
        
        Raises:
            SurveyPointsNotFoundException: 导线点文件不存在
            InvalidSurveyPointsException: 导线点数据无效
        """
        path = Path(file_path)
        
        if not path.exists():
            raise SurveyPointsNotFoundException(
                f"Survey points file not found: {file_path}",
                details={'path': str(path.absolute())}
            )
        
        try:
            # 加载CSV文件
            self.survey_points = pd.read_csv(path, encoding='utf-8')
            
            # 验证必需列
            required_columns = ['FID', 'X', 'Y', 'Z']
            missing_columns = [col for col in required_columns if col not in self.survey_points.columns]
            
            if missing_columns:
                # 尝试其他可能的列名
                alt_columns = {
                    'FID': ['点号', '点位', 'ID', 'Point_ID'],
                    'X': ['x', 'X坐标', 'East', 'E'],
                    'Y': ['y', 'Y坐标', 'North', 'N'],
                    'Z': ['z', 'Z坐标', 'Height', 'H', 'Elevation']
                }
                
                for req_col in missing_columns:
                    for alt_col in alt_columns.get(req_col, []):
                        if alt_col in self.survey_points.columns:
                            self.survey_points.rename(columns={alt_col: req_col}, inplace=True)
                            break
            
            # 再次检查
            missing_columns = [col for col in required_columns if col not in self.survey_points.columns]
            if missing_columns:
                raise InvalidSurveyPointsException(
                    f"Missing required columns: {missing_columns}",
                    details={'available_columns': list(self.survey_points.columns)}
                )
            
            # 构建空间索引
            self._build_spatial_index()
            
            logger.info(f"加载了 {len(self.point_dict)} 个导线点")
            
        except Exception as e:
            if isinstance(e, DataException):
                raise
            raise InvalidSurveyPointsException(
                f"Failed to load survey points: {str(e)}",
                details={'file': file_path}
            )
    
    def _build_spatial_index(self):
        """构建空间索引"""
        self.point_dict = {}
        
        for _, row in self.survey_points.iterrows():
            point_id = str(row['FID'])
            
            # 提取点号中的数字部分（如"XQ15"→"15"）
            import re
            match = re.search(r'(\d+)', point_id)
            if match:
                numeric_id = match.group(1)
                self.point_dict[numeric_id] = {
                    'x': float(row['X']),
                    'y': float(row['Y']),
                    'z': float(row['Z']),
                    'full_id': point_id
                }
            
            # 同时保存完整ID
            self.point_dict[point_id] = {
                'x': float(row['X']),
                'y': float(row['Y']),
                'z': float(row['Z']),
                'full_id': point_id
            }
    
    def infer_coordinates(
        self, 
        drill_holes: List[DrillHoleEntity]
    ) -> Tuple[Dict[str, Dict[str, Coordinate]], Dict[str, Any]]:
        """
        推断钻孔坐标
        
        Args:
            drill_holes: 钻孔实体列表
        
        Returns:
            (坐标字典, 时间统计信息)
        """
        if not self.point_dict:
            logger.warning("没有可用的导线点数据，跳过坐标推断")
            return {}, {}
        
        coordinates = {}
        location_processing_times = []
        
        # 按位置描述分组
        location_groups = self._group_by_location(drill_holes)
        unique_location_count = len(location_groups)
        
        logger.info(f"共有 {unique_location_count} 种不同的位置描述")
        
        # 处理每个位置组
        for location_desc, holes in location_groups.items():
            try:
                # 记录处理时间
                start_time = time.time()
                
                # 分析位置描述
                location_info = self._analyze_location_with_cache(location_desc)
                
                end_time = time.time()
                location_processing_times.append(end_time - start_time)
                
                # 计算坐标
                if location_info:
                    group_coords = self._process_location_group(location_info, holes)
                    coordinates.update(group_coords)
                    
            except Exception as e:
                logger.error(f"推断坐标失败 (位置: {location_desc}): {str(e)}")
                continue
        
        # 统计信息
        timing_stats = {
            'location_processing_times': location_processing_times,
            'unique_location_descriptions_count': unique_location_count,
            'total_location_processing_time': sum(location_processing_times),
            'avg_location_processing_time': np.mean(location_processing_times) if location_processing_times else 0
        }
        
        return coordinates, timing_stats
    
    def _group_by_location(self, drill_holes: List[DrillHoleEntity]) -> Dict[str, List[DrillHoleEntity]]:
        """
        按位置描述分组
        
        Args:
            drill_holes: 钻孔实体列表
        
        Returns:
            位置描述到钻孔列表的映射
        """
        location_groups = defaultdict(list)
        
        for hole in drill_holes:
            if hole.location_desc:
                location_desc = hole.location_desc.strip()
                location_groups[location_desc].append(hole)
        
        return dict(location_groups)
    
    def _analyze_location_with_cache(self, location_desc: str) -> Optional[Dict[str, Any]]:
        """
        分析位置描述（带缓存）
        
        Args:
            location_desc: 位置描述文本
        
        Returns:
            位置分析结果
        """
        # 检查缓存
        if self.enable_cache and self._location_analysis_cache is not None:
            if location_desc in self._location_analysis_cache:
                logger.debug(f"使用缓存的位置分析结果: {location_desc}")
                return self._location_analysis_cache[location_desc]
        
        # 调用LLM分析
        location_info = self._analyze_location_description(location_desc)
        
        # 更新缓存
        if self.enable_cache and self._location_analysis_cache is not None:
            self._location_analysis_cache[location_desc] = location_info
        
        return location_info
    
    def _analyze_location_description(self, location_desc: str) -> Optional[Dict[str, Any]]:
        """
        使用LLM分析位置描述
        
        Args:
            location_desc: 位置描述文本
        
        Returns:
            分析结果字典
        """
        prompt = LOCATION_ANALYSIS_PROMPT.format(location_desc=location_desc)
        
        try:
            # 调用LLM - 支持流式输出
            if self.stream_mode and hasattr(self.llm_client, 'stream_generate'):
                print(f"\n🗺️  开始位置分析 (流式输出)...")
                response_content = ""
                
                for chunk in self.llm_client.stream_generate(prompt):
                    print(chunk, end='', flush=True)  # 显示最终内容
                    response_content += chunk
                
                print(f"\n✅ 位置分析完成，响应长度: {len(response_content)}")
                
                # 构建响应对象（模拟LLMResponse）
                from ..llm.base import LLMResponse
                response = LLMResponse(
                    content=response_content,
                    model=self.llm_client._get_model_name() if hasattr(self.llm_client, '_get_model_name') else 'unknown',
                    usage=None
                )
            else:
                response = self.llm_client.generate(prompt)
                logger.debug(f"位置分析响应: {response.content[:500]}...")
            
            # 解析响应
            content = response.content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            location_info = json.loads(content)
            
            # 验证必需字段
            if not location_info.get('参考点号'):
                logger.warning(f"位置分析结果缺少参考点号: {location_desc}")
                return None
            
            return location_info
            
        except Exception as e:
            logger.error(f"位置描述分析失败: {str(e)}")
            return None
    
    def _process_location_group(
        self, 
        location_info: Dict[str, Any],
        holes: List[DrillHoleEntity]
    ) -> Dict[str, Dict[str, Coordinate]]:
        """
        处理位置组的坐标计算
        
        Args:
            location_info: 位置分析信息
            holes: 该位置的钻孔列表
        
        Returns:
            钻孔ID到坐标的映射
        """
        group_coordinates = {}
        
        # 计算起点坐标
        start_coords = self._calculate_start_coordinate(location_info)
        
        if not start_coords:
            logger.warning(f"无法计算起点坐标: {location_info}")
            return group_coordinates
        
        # 获取置信度和方法
        confidence = location_info.get('置信度', 0.8)
        method = self._determine_method(location_info)
        
        # 为每个钻孔创建坐标
        for hole in holes:
            # 记录方向类型
            hole.location_desc_direction_type = location_info.get('方向类型')
            
            hole_coords = {}
            
            # 起点坐标
            start_coord = Coordinate(
                x=start_coords[0],
                y=start_coords[1],
                z=start_coords[2],
                confidence=confidence,
                method=method
            )
            hole_coords['start'] = start_coord
            
            # 计算终点坐标
            if hole.actual_params:
                end_coord = self._calculate_end_coordinate(
                    start_coord,
                    hole.actual_params.actual_azimuth,
                    hole.actual_params.actual_inclination,
                    hole.actual_params.actual_depth
                )
                if end_coord:
                    hole_coords['end'] = end_coord
            elif hole.design_params:
                end_coord = self._calculate_end_coordinate(
                    start_coord,
                    hole.design_params.design_azimuth,
                    hole.design_params.design_inclination,
                    hole.design_params.design_depth
                )
                if end_coord:
                    hole_coords['end'] = end_coord
            
            group_coordinates[hole.hole_id] = hole_coords
        
        return group_coordinates
    
    def _calculate_start_coordinate(self, location_info: Dict[str, Any]) -> Optional[Tuple[float, float, float]]:
        """
        计算起点坐标
        
        Args:
            location_info: 位置分析信息
        
        Returns:
            (x, y, z)坐标元组
        """
        ref_point_id = str(location_info.get('参考点号', ''))
        if not ref_point_id or ref_point_id not in self.point_dict:
            logger.warning(f"参考点 {ref_point_id} 不存在")
            return None
        
        ref_point = self.point_dict[ref_point_id]
        direction_type = location_info.get('方向类型', '')
        
        # 根据方向类型计算坐标
        if direction_type == 'forward':
            return self._calculate_forward_position(location_info, ref_point)
        elif direction_type == 'backward':
            return self._calculate_backward_position(location_info, ref_point)
        elif direction_type == 'between':
            return self._calculate_between_position(location_info, ref_point)
        elif direction_type == 'lateral':
            return self._calculate_lateral_position(location_info, ref_point)
        else:
            # 默认返回参考点坐标
            return (ref_point['x'], ref_point['y'], ref_point['z'])
    
    def _calculate_forward_position(
        self, 
        location_info: Dict[str, Any],
        ref_point: Dict[str, float]
    ) -> Optional[Tuple[float, float, float]]:
        """计算前进方向的位置"""
        distance = location_info.get('距离', 0)
        direction_ref_id = location_info.get('方向参考点号')
        
        if direction_ref_id and str(direction_ref_id) in self.point_dict:
            direction_point = self.point_dict[str(direction_ref_id)]
            
            # 计算方向向量
            dx = direction_point['x'] - ref_point['x']
            dy = direction_point['y'] - ref_point['y']
            
            # 归一化
            length = math.sqrt(dx**2 + dy**2)
            if length > 0:
                dx /= length
                dy /= length
                
                # 计算新位置
                x = ref_point['x'] + dx * distance
                y = ref_point['y'] + dy * distance
                z = ref_point['z']  # 暂时保持高程不变
                
                # 应用偏移
                x, y, z = self._apply_offsets(x, y, z, location_info, dx, dy)
                
                return (x, y, z)
        
        return None
    
    def _calculate_backward_position(
        self, 
        location_info: Dict[str, Any],
        ref_point: Dict[str, float]
    ) -> Optional[Tuple[float, float, float]]:
        """计算后退方向的位置"""
        # 与forward相反
        location_info_copy = location_info.copy()
        location_info_copy['距离'] = -location_info.get('距离', 0)
        return self._calculate_forward_position(location_info_copy, ref_point)
    
    def _calculate_between_position(
        self, 
        location_info: Dict[str, Any],
        ref_point: Dict[str, float]
    ) -> Optional[Tuple[float, float, float]]:
        """计算两点之间的位置"""
        direction_ref_id = location_info.get('方向参考点号')
        
        if direction_ref_id and str(direction_ref_id) in self.point_dict:
            direction_point = self.point_dict[str(direction_ref_id)]
            
            # 默认在中点
            ratio = 0.5
            if location_info.get('距离'):
                # 如果有距离，计算比例
                total_distance = math.sqrt(
                    (direction_point['x'] - ref_point['x'])**2 +
                    (direction_point['y'] - ref_point['y'])**2
                )
                if total_distance > 0:
                    ratio = location_info['距离'] / total_distance
            
            # 插值计算
            x = ref_point['x'] + (direction_point['x'] - ref_point['x']) * ratio
            y = ref_point['y'] + (direction_point['y'] - ref_point['y']) * ratio
            z = ref_point['z'] + (direction_point['z'] - ref_point['z']) * ratio
            
            # 应用偏移
            dx = direction_point['x'] - ref_point['x']
            dy = direction_point['y'] - ref_point['y']
            length = math.sqrt(dx**2 + dy**2)
            if length > 0:
                dx /= length
                dy /= length
                x, y, z = self._apply_offsets(x, y, z, location_info, dx, dy)
            
            return (x, y, z)
        
        return None
    
    def _calculate_lateral_position(
        self, 
        location_info: Dict[str, Any],
        ref_point: Dict[str, float]
    ) -> Optional[Tuple[float, float, float]]:
        """计算侧向位置"""
        # 暂时返回参考点坐标
        return (ref_point['x'], ref_point['y'], ref_point['z'])
    
    def _apply_offsets(
        self,
        x: float, y: float, z: float,
        location_info: Dict[str, Any],
        dx: float, dy: float
    ) -> Tuple[float, float, float]:
        """应用侧向和垂直偏移"""
        # 侧向偏移
        lateral_offset = location_info.get('侧向偏移', {})
        if lateral_offset.get('方向') and lateral_offset.get('距离'):
            # 计算垂直于前进方向的向量
            perp_dx = -dy
            perp_dy = dx
            
            offset_distance = lateral_offset['距离']
            if lateral_offset['方向'] == 'left':
                offset_distance = -offset_distance
            
            x += perp_dx * offset_distance
            y += perp_dy * offset_distance
        
        # 垂直偏移
        vertical_offset = location_info.get('垂直偏移', {})
        if vertical_offset.get('方向') and vertical_offset.get('距离'):
            if vertical_offset['方向'] == 'up':
                z += vertical_offset['距离']
            elif vertical_offset['方向'] == 'down':
                z -= vertical_offset['距离']
        
        return (x, y, z)
    
    def _calculate_end_coordinate(
        self,
        start_coord: Coordinate,
        azimuth: Optional[float],
        inclination: Optional[float],
        depth: Optional[float]
    ) -> Optional[Coordinate]:
        """
        计算终点坐标
        
        Args:
            start_coord: 起点坐标
            azimuth: 方位角
            inclination: 倾角
            depth: 深度
        
        Returns:
            终点坐标对象
        """
        if azimuth is None or inclination is None or depth is None:
            return None
        
        try:
            end_x, end_y, end_z = calculate_drill_hole_endpoint(
                start_coord.x, start_coord.y, start_coord.z,
                azimuth, inclination, depth
            )
            
            return Coordinate(
                x=end_x,
                y=end_y,
                z=end_z,
                confidence=start_coord.confidence * 0.9,  # 终点置信度略低
                method=f"{start_coord.method}_calculated"
            )
        except Exception as e:
            logger.error(f"计算终点坐标失败: {str(e)}")
            return None
    
    def _determine_method(self, location_info: Dict[str, Any]) -> str:
        """确定坐标推断方法"""
        direction_type = location_info.get('方向类型', 'unknown')
        confidence = location_info.get('置信度', 0)
        
        if confidence > 0.9:
            return f"high_confidence_{direction_type}"
        elif confidence > 0.7:
            return f"medium_confidence_{direction_type}"
        else:
            return f"low_confidence_{direction_type}"