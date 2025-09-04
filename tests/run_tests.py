"""
测试运行器 - 执行所有测试（不依赖pytest）
"""

import sys
import importlib
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, List, Any


class SimpleTestRunner:
    """简单测试运行器"""
    
    def __init__(self):
        self.results = {}
        self.total_tests = 0
        self.passed_tests = 0
        
        # 确保src目录在Python路径中
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
    
    def discover_tests(self, directory: Path) -> List[Path]:
        """发现测试文件"""
        return list(directory.rglob("test_*.py"))
    
    def run_test_file(self, test_file: Path) -> Dict[str, Any]:
        """运行单个测试文件"""
        print(f"运行测试文件: {test_file.name}")
        result = {"file": test_file.name, "passed": 0, "failed": 0, "errors": []}
        
        try:
            # 动态导入测试模块
            module_name = test_file.stem
            spec = importlib.util.spec_from_file_location(module_name, test_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找测试类和方法
            test_methods = []
            for name in dir(module):
                obj = getattr(module, name)
                if name.startswith('Test') and hasattr(obj, '__call__'):
                    # 测试类
                    test_instance = obj()
                    for method_name in dir(test_instance):
                        if method_name.startswith('test_'):
                            test_methods.append((test_instance, method_name))
                elif name.startswith('test_') and hasattr(obj, '__call__'):
                    # 测试函数
                    test_methods.append((None, name))
            
            # 运行测试
            for test_obj, test_name in test_methods:
                self.total_tests += 1
                try:
                    if test_obj:
                        # 运行测试类的方法
                        method = getattr(test_obj, test_name)
                        method()
                    else:
                        # 运行测试函数
                        func = getattr(module, test_name)
                        func()
                    
                    print(f"  ✅ {test_name}")
                    result["passed"] += 1
                    self.passed_tests += 1
                    
                except Exception as e:
                    print(f"  ❌ {test_name}: {str(e)}")
                    result["failed"] += 1
                    result["errors"].append(f"{test_name}: {str(e)}")
        
        except Exception as e:
            print(f"  💥 无法加载测试文件: {str(e)}")
            result["errors"].append(f"加载错误: {str(e)}")
        
        return result
    
    def run_tests_in_directory(self, directory: Path) -> Dict[str, Any]:
        """运行目录中的所有测试"""
        print(f"\n📁 运行目录: {directory}")
        print("=" * 50)
        
        test_files = self.discover_tests(directory)
        results = {"directory": str(directory), "files": [], "summary": {}}
        
        for test_file in test_files:
            file_result = self.run_test_file(test_file)
            results["files"].append(file_result)
        
        # 统计
        total_passed = sum(f["passed"] for f in results["files"])
        total_failed = sum(f["failed"] for f in results["files"])
        
        results["summary"] = {
            "files": len(test_files),
            "passed": total_passed,
            "failed": total_failed
        }
        
        print(f"\n目录测试总结: {total_passed} 通过, {total_failed} 失败")
        return results


def run_all_tests():
    """运行所有测试"""
    runner = SimpleTestRunner()
    
    print("KG钻孔提取系统测试运行器")
    print("=" * 60)
    
    tests_dir = Path(__file__).parent
    all_results = []
    
    # 运行单元测试
    unit_dir = tests_dir / "unit"
    if unit_dir.exists():
        unit_results = runner.run_tests_in_directory(unit_dir)
        all_results.append(unit_results)
    
    # 运行集成测试
    integration_dir = tests_dir / "integration"  
    if integration_dir.exists():
        integration_results = runner.run_tests_in_directory(integration_dir)
        all_results.append(integration_results)
    
    # 总结果
    print("\n" + "=" * 60)
    print("测试运行总结:")
    print(f"总测试数: {runner.total_tests}")
    print(f"通过测试: {runner.passed_tests}")
    print(f"失败测试: {runner.total_tests - runner.passed_tests}")
    print(f"成功率: {runner.passed_tests / runner.total_tests * 100:.1f}%")
    
    if runner.passed_tests == runner.total_tests:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {runner.total_tests - runner.passed_tests} 项测试失败")
        return 1


def run_unit_tests():
    """运行单元测试"""
    runner = SimpleTestRunner()
    tests_dir = Path(__file__).parent / "unit"
    results = runner.run_tests_in_directory(tests_dir)
    return 0 if results["summary"]["failed"] == 0 else 1


def run_integration_tests():
    """运行集成测试"""
    runner = SimpleTestRunner()
    tests_dir = Path(__file__).parent / "integration"
    results = runner.run_tests_in_directory(tests_dir)
    return 0 if results["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "unit":
            exit_code = run_unit_tests()
        elif test_type == "integration":
            exit_code = run_integration_tests()
        else:
            print(f"未知测试类型: {test_type}")
            print("使用: python run_tests.py [unit|integration]")
            exit_code = 1
    else:
        exit_code = run_all_tests()
    
    sys.exit(exit_code)