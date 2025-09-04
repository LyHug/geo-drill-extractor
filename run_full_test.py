#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
直接运行7个核心模型完整测试的简单脚本
配置：7个模型 + 30个文档 + 3轮重复 + 流式输出
支持的模型：DeepSeek R1系列、GPT系列、Qwen系列
"""



import sys
from pathlib import Path
import time
from datetime import datetime

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from kg_drill_extraction.experiment import ExperimentRunner
from kg_drill_extraction.core import LLMModel



def main():
    """主函数 - 直接运行完整测试"""
    print("🚀 KG钻孔提取系统 - 7个核心模型完整测试")
    print("="*50)
    print("⚙️  测试配置: 7个模型 × 30个文档 × 3轮重复")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    start_time = time.time()

    try:
        # 获取所有模型并创建实验执行器
        all_models = list(LLMModel)
        target_values = [
                        'deepseek-r1-distill-qwen-7b-aliyun',
                        'deepseek-r1-distill-qwen-14b-aliyun',
                        'deepseek-r1-distill-qwen-32b-aliyun',
                        'gpt-3.5-turbo-openrouter',
                        'gpt-4o-mini-openrouter',
                        'qwen-max',
                        'qwq-32b'
                         ]
        experiment_models = [
            model for model in all_models if model.value in target_values]
        print(f"🤖 加载 {len(experiment_models)} 个实验模型...")

        runner = ExperimentRunner(models=experiment_models, stream_mode=True)

        # 运行实验
        print("📊 开始执行实验...")
        results = runner.run_experiment(
            repetitions=3,
            test_documents=30,
            save_results=True
        )

        # 计算时间
        elapsed_time = time.time() - start_time

        # 显示结果
        print("\n" + "="*50)
        print("🎉 测试完成！")

        metadata = results.get('metadata', {})
        statistics = results.get('statistics', {})

        successful_runs = statistics.get('successful_runs', 0)
        failed_runs = statistics.get('failed_runs', 0)
        success_rate = (successful_runs /
                        max(successful_runs + failed_runs, 1)) * 100

        print(f"⏱️  总时间: {elapsed_time/60:.1f} 分钟")
        print(
            f"📊 成功率: {success_rate:.1f}% ({successful_runs}/{successful_runs + failed_runs})")
        print(f"📄 文档数: {metadata.get('total_documents', 0)}")
        print(f"🤖 模型数: {len(metadata.get('models', []))}")

        # 显示输出目录
        raw_results = results.get('raw_results', {})
        if raw_results:
            for model_data in raw_results.values():
                if isinstance(model_data, dict) and 'output_dir' in model_data:
                    output_dir = Path(model_data['output_dir']).parent
                    print(f"📁 结果: {output_dir}")
                    break

        if success_rate >= 90:
            print("✅ 测试成功！")
        else:
            print("⚠️  部分测试失败")

    except KeyboardInterrupt:
        print(f"\n⏹️  测试中断 (运行时间: {(time.time() - start_time)/60:.1f}分钟)")
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
