"""
Pytest配置文件
"""
import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# 测试配置
import pytest


@pytest.fixture(scope="session")
def test_data_dir():
    """测试数据目录"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def temp_output_dir(tmp_path_factory):
    """临时输出目录"""
    return tmp_path_factory.mktemp("output")


@pytest.fixture(scope="module")
def mock_config():
    """模拟配置"""
    return {
        'llm': {
            'default_model': 'DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN',
            'timeout': 30,
            'max_retries': 2
        },
        'data': {
            'documents_dir': './documents',
            'output_dir': './output'
        }
    }