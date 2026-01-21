#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
系统检查脚本 - 验证KG钻孔提取系统的各个组件
"""

import sys
import traceback
from pathlib import Path
import importlib
from typing import Dict, List, Any

# 添加src目录到Python路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


class SystemChecker:
    """系统检查器"""
    
    def __init__(self):
        self.results = {}
        self.total_checks = 0
        self.passed_checks = 0
    
    def run_check(self, check_name: str, check_func):
        """运行单个检查"""
        print(f"检查 {check_name}...", end=" ")
        self.total_checks += 1
        
        try:
            result = check_func()
            if result:
                print("✅ 通过")
                self.passed_checks += 1
                self.results[check_name] = {"status": "pass", "details": result}
                return True
            else:
                print("❌ 失败")
                self.results[check_name] = {"status": "fail", "details": "检查返回False"}
                return False
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            self.results[check_name] = {"status": "error", "details": str(e), "traceback": traceback.format_exc()}
            return False
    
    def check_core_imports(self) -> bool:
        """检查核心模块导入"""
        from core import (
            LLMModel,
            DrillHoleEntity,
            Coordinate,
            ProcessResult,
            ConfigLoader,
            get_config_loader
        )
        return True
    
    def check_extraction_imports(self) -> bool:
        """检查提取模块导入"""
        from extraction import ExtractionPipeline
        return True
    
    def check_evaluation_imports(self) -> bool:
        """检查评估模块导入"""
        from evaluation import (
            SixMetricsProcessor,
            GroundTruthLoader,
            TokenizerManager,
            get_tokenizer_manager
        )
        return True
    
    def check_experiment_imports(self) -> bool:
        """检查实验模块导入"""
        from experiment import (
            ExperimentRunner,
            run_quick_experiment,
            run_full_experiment,
            ResultExporter
        )
        return True
    
    def check_main_package_import(self) -> bool:
        """检查主要模块导入（扁平化 src 后不再有 kg_drill_extraction 包）"""
        import core
        import extraction
        import evaluation
        import experiment

        required = {
            core: ['LLMModel', 'get_config_loader'],
            extraction: ['ExtractionPipeline'],
            evaluation: ['SixMetricsProcessor'],
            experiment: ['ExperimentRunner', 'run_quick_experiment'],
        }

        for module, attrs in required.items():
            for attr in attrs:
                if not hasattr(module, attr):
                    raise ImportError(f"{module.__name__} 缺少 {attr}")

        return True
    
    def check_config_system(self) -> bool:
        """检查配置系统"""
        from core import get_config_loader
        
        # 测试配置加载器
        loader = get_config_loader()
        if loader is None:
            return False
        
        # 测试配置获取
        default_model = loader.get('llm.default_model', 'fallback')
        if default_model == 'fallback':
            # 如果获取不到默认模型，检查是否至少有配置结构
            llm_config = loader.get('llm', {})
            if not llm_config:
                return False
        
        return True
    
    def check_llm_models(self) -> bool:
        """检查LLM模型枚举"""
        from core import LLMModel
        
        # 检查模型数量
        models = list(LLMModel)
        if len(models) < 5:  # 至少应该有5个模型
            return False
        
        # 检查一些关键模型
        required_models = [
            'DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN',
            'GPT_35_TURBO_OPENROUTER'
        ]
        
        for model_name in required_models:
            if not hasattr(LLMModel, model_name):
                return False
        
        return True
    
    def check_data_models(self) -> bool:
        """检查数据模型"""
        from core import (
            DrillHoleEntity,
            Coordinate,
            ProcessResult,
            SingleRunMetrics,
            SixMetricsScores
        )
        
        # 测试基本对象创建
        hole = DrillHoleEntity(
            hole_id="TEST001",
            location_desc="测试位置",
            confidence=0.95
        )
        
        coord = Coordinate(x=1.0, y=2.0, z=3.0)
        
        result = ProcessResult(
            document_name="test.docx",
            drill_holes=[hole],
            coordinates={"TEST001": {"start": coord}},
            processing_time=1.0
        )
        
        return all([hole, coord, result])
    
    def check_pipeline_creation(self) -> bool:
        """检查管道创建"""
        from extraction import ExtractionPipeline
        from core import LLMModel
        
        pipeline = ExtractionPipeline(model=LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN)
        
        # 检查组件是否存在
        required_components = [
            'document_processor',
            'entity_extractor', 
            'coordinate_inferencer'
        ]
        
        for component in required_components:
            if not hasattr(pipeline, component):
                return False
            if getattr(pipeline, component) is None:
                return False
        
        return True
    
    def check_metrics_processor(self) -> bool:
        """检查指标处理器"""
        from evaluation import SixMetricsProcessor
        
        processor = SixMetricsProcessor()
        
        # 检查关键方法
        required_methods = [
            'process_result_to_metrics',
            'aggregate_metrics',
            'validate_metrics'
        ]
        
        for method in required_methods:
            if not hasattr(processor, method):
                return False
            if not callable(getattr(processor, method)):
                return False
        
        return True
    
    def check_tokenizer_manager(self) -> bool:
        """检查分词器管理器"""
        from evaluation import get_tokenizer_manager
        
        manager = get_tokenizer_manager()
        
        # 测试基本功能
        token_count = manager.calculate_tokens("测试文本")
        if not isinstance(token_count, int) or token_count <= 0:
            return False
        
        return True
    
    def check_experiment_runner(self) -> bool:
        """检查实验执行器"""
        from experiment import ExperimentRunner
        
        runner = ExperimentRunner()
        
        # 检查基本属性
        required_attrs = [
            'models',
            'metrics_processor', 
            'ground_truth_loader'
        ]
        
        for attr in required_attrs:
            if not hasattr(runner, attr):
                return False
            if getattr(runner, attr) is None:
                return False
        
        return True
    
    def check_result_exporter(self) -> bool:
        """检查结果导出器"""
        from experiment import ResultExporter
        
        exporter = ResultExporter()
        
        # 检查导出器组件
        required_exporters = [
            'csv_exporter',
            'excel_exporter',
            'json_exporter'
        ]
        
        for exp in required_exporters:
            if not hasattr(exporter, exp):
                return False
            if getattr(exporter, exp) is None:
                return False
        
        return True
    
    def check_dependencies(self) -> Dict[str, bool]:
        """检查依赖库"""
        dependencies = {
            'pandas': False,
            'numpy': False,
            'transformers': False,
            'yaml': False,
            'openpyxl': False,
            'python-docx': False
        }
        
        for dep_name in dependencies:
            try:
                if dep_name == 'python-docx':
                    import docx
                elif dep_name == 'yaml':
                    import yaml
                else:
                    importlib.import_module(dep_name)
                dependencies[dep_name] = True
            except ImportError:
                dependencies[dep_name] = False
        
        return dependencies
    
    def run_all_checks(self):
        """运行所有检查"""
        print("KG钻孔提取系统检查")
        print("=" * 60)
        
        # 基础导入检查
        print("\n📦 模块导入检查:")
        self.run_check("核心模块导入", self.check_core_imports)
        self.run_check("提取模块导入", self.check_extraction_imports)
        self.run_check("评估模块导入", self.check_evaluation_imports)
        self.run_check("实验模块导入", self.check_experiment_imports)
        self.run_check("主包导入", self.check_main_package_import)
        
        # 系统组件检查
        print("\n⚙️  系统组件检查:")
        self.run_check("配置系统", self.check_config_system)
        self.run_check("LLM模型", self.check_llm_models)
        self.run_check("数据模型", self.check_data_models)
        
        # 功能模块检查
        print("\n🔧 功能模块检查:")
        self.run_check("提取管道", self.check_pipeline_creation)
        self.run_check("指标处理器", self.check_metrics_processor)
        self.run_check("分词器管理器", self.check_tokenizer_manager)
        self.run_check("实验执行器", self.check_experiment_runner)
        self.run_check("结果导出器", self.check_result_exporter)
        
        # 依赖检查
        print("\n📚 依赖库检查:")
        deps = self.check_dependencies()
        for dep_name, available in deps.items():
            status = "✅" if available else "❌"
            print(f"检查 {dep_name}... {status}")
            if available:
                self.passed_checks += 1
            self.total_checks += 1
        
        # 汇总结果
        print("\n" + "=" * 60)
        print("检查结果汇总:")
        print(f"总检查项: {self.total_checks}")
        print(f"通过检查: {self.passed_checks}")
        print(f"失败检查: {self.total_checks - self.passed_checks}")
        print(f"成功率: {self.passed_checks / self.total_checks * 100:.1f}%")
        
        if self.passed_checks == self.total_checks:
            print("\n🎉 所有检查通过！系统运行正常。")
            return True
        else:
            print(f"\n⚠️  {self.total_checks - self.passed_checks} 项检查失败。")
            
            # 显示失败详情
            print("\n失败详情:")
            for check_name, result in self.results.items():
                if result["status"] in ["fail", "error"]:
                    print(f"  ❌ {check_name}: {result['details']}")
            
            return False


def main():
    """主函数"""
    checker = SystemChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
