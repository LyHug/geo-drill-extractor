"""
配置管理模块 - 单例模式配置加载器，支持热更新和环境变量
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from threading import Lock
from datetime import datetime


class ConfigLoaderMeta(type):
    """线程安全的单例元类"""
    _instances = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class ConfigLoader(metaclass=ConfigLoaderMeta):
    """
    配置文件加载器 - 单例模式
    
    特性:
    - 线程安全的单例实现
    - 支持配置热更新
    - 环境变量自动替换
    - 嵌套配置访问
    - 配置验证
    """

    def __init__(self, config_path: str = None):
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return

        # 智能查找项目根目录和配置文件
        if config_path is None:
            config_path = self._find_project_config_file()
            if not config_path:
                config_path = "configs/config.yaml"  # 默认路径

        self.config_path = Path(config_path)
        self._config = None
        self._last_modified = None
        self._initialized = True

        # 初始化加载配置
        self._load_config()

    def _find_project_config_file(self) -> Optional[str]:
        """
        智能查找项目配置文件
        
        查找策略:
        1. 从当前工作目录开始向上查找包含configs/config.yaml的目录
        2. 检查是否包含其他项目标志文件（如src目录、requirements.txt等）
        3. 返回找到的config.yaml的完整路径
        """
        current_dir = Path.cwd()
        max_depth = 5  # 最多向上查找5层目录
        
        for _ in range(max_depth):
            # 检查当前目录是否包含configs/config.yaml
            config_file = current_dir / "configs" / "config.yaml"
            if config_file.exists():
                # 验证这是正确的项目目录（包含其他项目标志）
                project_indicators = [
                    current_dir / "src" / "kg_drill_extraction",
                    current_dir / "data",
                    current_dir / "documents", 
                    current_dir / "run_full_test.py"
                ]
                
                # 如果至少有2个指标存在，认为找到了正确的项目目录
                if sum(1 for indicator in project_indicators if indicator.exists()) >= 2:
                    return str(config_file)
            
            # 向上一级目录查找
            parent_dir = current_dir.parent
            if parent_dir == current_dir:  # 已到达文件系统根目录
                break
            current_dir = parent_dir
        
        # 如果没找到，尝试脚本文件相对路径
        try:
            # 获取当前模块文件路径
            import inspect
            current_file = Path(inspect.getfile(self.__class__))
            # 假设结构: src/kg_drill_extraction/core/config.py
            project_root = current_file.parent.parent.parent.parent
            config_file = project_root / "configs" / "config.yaml"
            if config_file.exists():
                return str(config_file)
        except:
            pass
            
        return None

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            # 如果配置文件不存在，返回默认配置
            print(f"警告: 配置文件不存在 {self.config_path}, 使用默认配置")
            self._config = self._get_default_config()
            return self._config

        current_modified = self.config_path.stat().st_mtime

        # 如果文件未修改且已有配置，直接返回缓存
        if self._config and self._last_modified == current_modified:
            return self._config

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 递归替换环境变量
        self._config = self._replace_env_vars(config)
        self._last_modified = current_modified

        return self._config

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'llm': {
                'default_model': 'deepseek-r1',
                'temperature': 0.1,
                'max_tokens': 8192,
                'timeout': 30,
                'retry_times': 3,
                'api_keys': {}
            },
            'data': {
                'documents_dir': './documents',
                'survey_points_file': './data/导线点.csv',
                'output_dir': './output'
            },
            'processing': {
                'parallel': {
                    'enabled': True,
                    'max_workers': 5,
                    'max_concurrent_llm_calls': 10
                },
                'text_chunking': {
                    'max_chunk_size': 2000,
                    'overlap': 200
                },
                'cache': {
                    'enabled': False,
                    'max_size': 1000,
                    'ttl': 3600
                }
            },
            'output': {
                'batch_formats': ['csv', 'excel', 'json'],
                'single_format': 'json'
            },
            'logging': {
                'level': 'INFO',
                'file': 'extraction_chain.log'
            }
        }

    @property
    def config(self) -> Dict[str, Any]:
        """获取配置，支持热更新"""
        return self._load_config()

    def _replace_env_vars(self, obj: Any) -> Any:
        """递归替换配置中的环境变量引用"""
        if isinstance(obj, dict):
            return {k: self._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            # 提取环境变量名
            env_var = obj[2:-1]
            value = os.getenv(env_var)
            if value is None:
                print(f"警告: 环境变量 {env_var} 未设置")
                return None
            return value
        else:
            return obj

    # API密钥管理
    def get_api_key(self, service: str) -> Optional[str]:
        """获取指定服务的 API Key"""
        api_keys = self.config.get('llm', {}).get('api_keys', {})
        key = api_keys.get(service)
        
        # 如果没有配置，尝试从环境变量获取
        if not key:
            env_var_map = {
                'deepseek-official': 'DEEPSEEK_API_KEY',
                'aliyun-bailian': 'ALIYUN_API_KEY',
                'openrouter': 'OPENROUTER_API_KEY'
            }
            env_var = env_var_map.get(service)
            if env_var:
                key = os.getenv(env_var)
        
        return key

    # 模型配置
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """获取指定模型的配置"""
        models = self.config.get('llm', {}).get('models', {})
        return models.get(model_name, {})

    # 输出配置
    def get_output_config(self) -> Dict[str, Any]:
        """获取输出配置"""
        return self.config.get('output', {})

    def get_csv_export_config(self) -> Dict[str, Any]:
        """获取CSV导出配置"""
        return self.get_output_config().get('csv_export', {})

    def get_excel_export_config(self) -> Dict[str, Any]:
        """获取Excel导出配置"""
        return self.get_output_config().get('excel_export', {})

    def get_json_export_config(self) -> Dict[str, Any]:
        """获取JSON导出配置"""
        return self.get_output_config().get('json_export', {})

    # 字段配置
    def get_csv_fields(self) -> List[Dict[str, Any]]:
        """获取CSV字段配置"""
        csv_config = self.get_csv_export_config()
        return csv_config.get('main_fields', [])

    def get_excel_sheet_config(self, sheet_name: str) -> Dict[str, Any]:
        """获取Excel工作表配置"""
        excel_config = self.get_excel_export_config()
        sheet_map = {
            'main': 'main_sheet',
            'coord': 'coord_sheet',
            'stats': 'stats_sheet'
        }
        return excel_config.get(sheet_map.get(sheet_name, sheet_name), {})

    def get_json_fields(self, field_type: str) -> List[str]:
        """获取JSON导出的字段配置"""
        json_config = self.get_json_export_config()
        return json_config.get(f'{field_type}_fields', [])

    def get_drill_hole_fields(self, section: str = None) -> List[str]:
        """获取钻孔实体字段配置"""
        json_config = self.get_json_export_config()
        drill_hole_fields = json_config.get('drill_hole_fields', {})

        if section:
            return drill_hole_fields.get(section, [])

        # 返回所有字段
        all_fields = []
        for field_list in drill_hole_fields.values():
            if isinstance(field_list, list):
                all_fields.extend(field_list)
        return all_fields

    # 处理配置
    def get_processing_config(self) -> Dict[str, Any]:
        """获取处理配置"""
        return self.config.get('processing', {})

    def get_parallel_config(self) -> Dict[str, Any]:
        """获取并行处理配置"""
        return self.get_processing_config().get('parallel', {})

    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return self.get_processing_config().get('cache', {})

    def get_text_chunking_config(self) -> Dict[str, Any]:
        """获取文本分块配置"""
        return self.get_processing_config().get('text_chunking', {})

    # 其他配置
    def get_validation_config(self) -> Dict[str, Any]:
        """获取验证配置"""
        return self.config.get('validation', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config.get('logging', {})

    def get_data_paths(self) -> Dict[str, str]:
        """获取数据路径配置"""
        data_config = self.config.get('data', {})
        
        # 如果配置文件存在，基于配置文件的目录来计算相对路径
        if self.config_path.exists():
            project_root = self.config_path.parent.parent  # configs/config.yaml -> 项目根目录
            return {
                'documents_dir': str(project_root / data_config.get('documents_dir', 'documents').lstrip('./')),
                'survey_points_file': str(project_root / data_config.get('survey_points_file', 'data/导线点.csv').lstrip('./')),
                'output_dir': str(project_root / data_config.get('output_dir', 'output').lstrip('./')),
                'ground_truth_file': str(project_root / data_config.get('ground_truth_file', 'data/ground_truth_annotations.csv').lstrip('./')),
            }
        else:
            # 使用传统的相对路径（向后兼容）
            return {
                'documents_dir': data_config.get('documents_dir', './documents'),
                'survey_points_file': data_config.get('survey_points_file', './data/导线点.csv'),
                'output_dir': data_config.get('output_dir', './output'),
                'ground_truth_file': data_config.get('ground_truth_file', './data/ground_truth_annotations.csv'),
            }

    # 通用配置访问
    def get(self, path: str, default: Any = None) -> Any:
        """
        获取嵌套配置值
        
        Args:
            path: 点分隔的配置路径，如 'llm.default_model'
            default: 默认值
        
        Returns:
            配置值或默认值
        """
        keys = path.split('.')
        current = self.config

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def set(self, path: str, value: Any) -> None:
        """
        设置配置值（仅内存中，不写入文件）
        
        Args:
            path: 点分隔的配置路径
            value: 要设置的值
        """
        keys = path.split('.')
        current = self._config

        # 导航到目标位置
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # 设置值
        current[keys[-1]] = value

    # 配置管理
    def reload_config(self) -> Dict[str, Any]:
        """强制重新加载配置文件"""
        self._last_modified = None
        return self._load_config()

    def validate_config(self) -> List[str]:
        """验证配置完整性"""
        errors = []

        # 检查必要的配置项
        required_paths = [
            'llm.default_model',
            'data.documents_dir',
            'data.output_dir',
        ]

        for path in required_paths:
            if self.get(path) is None:
                errors.append(f"缺少必要配置: {path}")

        # 检查输出格式有效性
        valid_formats = ['csv', 'excel', 'json']
        batch_formats = self.get('output.batch_formats', [])
        single_format = self.get('output.single_format', 'json')

        for fmt in batch_formats:
            if fmt not in valid_formats:
                errors.append(f"无效的批量导出格式: {fmt}")

        if single_format not in valid_formats:
            errors.append(f"无效的单文件导出格式: {single_format}")

        return errors

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息"""
        return {
            'config_file': str(self.config_path),
            'last_modified': datetime.fromtimestamp(self._last_modified).isoformat() if self._last_modified else None,
            'llm_model': self.get('llm.default_model'),
            'api_keys_configured': len(self.config.get('llm', {}).get('api_keys', {})),
            'data_paths': self.get_data_paths(),
            'validation_errors': self.validate_config()
        }

    def __str__(self) -> str:
        """字符串表示"""
        summary = self.get_config_summary()
        return f"ConfigLoader(file={summary['config_file']}, model={summary['llm_model']})"

    def __repr__(self) -> str:
        return self.__str__()


# 便捷的全局实例获取函数
_config_loader_instance = None

def get_config_loader(config_path: str = None) -> ConfigLoader:
    """
    获取配置加载器实例（单例）
    
    Args:
        config_path: 配置文件路径，如果为None则自动查找
    
    Returns:
        ConfigLoader实例
    """
    global _config_loader_instance
    if _config_loader_instance is None:
        _config_loader_instance = ConfigLoader(config_path)
    return _config_loader_instance


def get_config(config_path: str = None) -> Dict[str, Any]:
    """
    获取配置字典
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        配置字典
    """
    return get_config_loader(config_path).config