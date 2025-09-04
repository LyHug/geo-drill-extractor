#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
分词器测试脚本
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from transformers import AutoTokenizer
from kg_drill_extraction.core import LLMModel
from kg_drill_extraction.evaluation import TokenizerManager

# 加载 R1 分词器（需 trust_remote_code）
tokenizer_r1 = AutoTokenizer.from_pretrained(
    "deepseek-ai/deepseek-r1", trust_remote_code=True)

# 加载 V3 分词器
tokenizer_v3 = AutoTokenizer.from_pretrained(
    "deepseek-ai/deepseek-v3", trust_remote_code=True)

# 加载 DeepSeek-R1-Distill-Qwen-14B 分词器（需 trust_remote_code）
tokenizer_r1_qwen_14b = AutoTokenizer.from_pretrained(
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B", trust_remote_code=True)

tokenizer_r1_qwen_32b = AutoTokenizer.from_pretrained(
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", trust_remote_code=True)

# 加载 DeepSeek-R1-Distill-Qwen-32B 分词器
tokenizer_qwen3_14b = AutoTokenizer.from_pretrained(
    "Qwen/Qwen3-14B", trust_remote_code=True)

tokenizer_qwen3_32b = AutoTokenizer.from_pretrained(
    "Qwen/Qwen3-32B", trust_remote_code=True)


tokenizer_qwq_32b = AutoTokenizer.from_pretrained(
    "Qwen/QwQ-32B", trust_remote_code=True)


# text = '冀中能源股份有限公司邢台矿\n\n25303综采工作面第七阶段底板超前钻探\n\n竣工报告\n\n编\u3000\u3000制：\n\n审\u3000\u3000核：\n\n队    长：\n\n总工程师：\n\n二零一九年十月十六日\n\n冀中能源股份有限公司邢台矿\n\n25303综采工作面第七阶段底板超前钻探竣工报告\n\n25303综采工作面第七阶段底板超前钻探工程于2019年10月16日竣工，共施工3个钻孔，累计进尺455.5m，注浆5T，所有钻孔均按设计要求施工，各项指标验收合格，符合钻探设计要求，现将钻探验收情况汇总如下：\n\n一、任务来源\n\n探查25303运输巷掘进前方底板是否存在隐伏导含水构造，确保巷道掘进不受水害影响。具体参数如下：\n\n钻孔施工参数表\n\n| 钻探位置 | 孔号 | 方位 | 倾角 | 开孔层位 | 终孔位置 | 终孔孔深 |\n|---|---|---|---|---|---|---|\n| 25303运输巷316#点前65m | 303C-22 | 204° | -2° | 5#煤底板 | 5#煤底板下46.7m | 153m |\n| 25303运输巷316#点前65m | 303C-23 | 192° | -3° | 5#煤底板 | 5#煤底板下47m | 151.5m |\n| 25303运输巷316#点前65m | 303C-24 | 180° | -5° | 5#煤底板 | 5#煤底板下45.7m | 151m |\n| 合计 |  |  |  |  |  | 455.5m |\n\n自设计接收以后，钻机队严格按照设计要求组织生产，于2019年10月8日开始，2019年10月16日完成钻探工程。\n\n二、钻探情况\n\n1．303C-22钻孔，设计位置：25303运输巷316#点前65m；设计方位：204°；设计倾角：-2°；设计孔深：151m。\n\n该孔2019年10月8日夜班开孔，实际方位204°，倾角-2°，以φ108mm钻头钻进至22.5m，孔内下入φ75 mm套皮管21m，注浆凝固套管，注浆固管用水泥0.25T。凝固好后用φ60mm钻头扫孔23m，做耐压试验，试验压力为7.03Mpa，稳定38min，管壁及四周不漏水，试验压力合格后，继续钻进至153m位置终孔。后进行注浆封孔，用水泥1.5T，封孔终压7.03Mpa。封孔后管内及四周无渗水，封孔质量良好。\n\n2．303C-23钻孔，设计位置：25303运输巷316#点前65m；设计方位：192°；设计倾角：-3°；设计孔深：151m。\n\n该孔2019年10月8日早班开孔，实际方位192°，倾角-3°，以φ108mm钻头钻进至22.5m，孔内下入φ75 mm套皮管21m，注浆凝固套管，注浆固管用水泥0.2T。凝固好后用φ60mm钻头扫孔23m，做耐压试验，试验压力为7.03Mpa，稳定34min，管壁及四周不漏水，试验压力合格后，继续钻进至151.5m位置终孔。对钻孔进行测斜，该孔右偏1.63m，下垂1.68m，总偏移量2.34m。后进行注浆封孔，用水泥1.8T，封孔终压7.03Mpa。封孔后管内及四周无渗水，封孔质量良好。\n\n3．303C-24钻孔，设计位置：25303运输巷316#点前65m；设计方位：180°；设计倾角：-5°；设计孔深：151m。\n\n该孔2019年10月9日夜班开孔，实际方位180°，倾角-5°，以φ108mm钻头钻进至22.5m，孔内下入φ75 mm套皮管21m，注浆凝固套管，注浆固管用水泥0.2T。凝固好后用φ60mm钻头扫孔23m，做耐压试验，试验压力为7.03Mpa，稳定36min，管壁及四周不漏水，试验压力合格后，继续钻进至151m位置终孔。后进行注浆封孔，用水泥1.7T，封孔终压7.03Mpa。封孔后管内及四周无渗水，封孔质量良好。\n\n三、结论\n\n25303综采工作面第七阶段底板超前钻探工程按设计要求已完工，施工质量均达到设计要求。\n'
text = '冀中能源股份有限公司邢台矿'
print("R1 Tokens:", len(tokenizer_r1.encode(text, add_special_tokens=True)))
print("V3 Tokens:", len(tokenizer_v3.encode(text, add_special_tokens=True)))
print("r1_qwen_14b Tokens:", len(
    tokenizer_r1_qwen_14b.encode(text, add_special_tokens=True)))
print("r1_qwen_32b Tokens:", len(
    tokenizer_r1_qwen_32b.encode(text, add_special_tokens=True)))
print("qwen3_14b Tokens:", len(
    tokenizer_qwen3_14b.encode(text, add_special_tokens=True)))
print("qwen3_32b Tokens:", len(
    tokenizer_qwen3_32b.encode(text, add_special_tokens=True)))
print("qwq_32b Tokens:", len(
    tokenizer_qwq_32b.encode(text, add_special_tokens=True)))

# 使用新的TokenizerManager测试
print("\n=== 使用新TokenizerManager测试 ===")
tokenizer_manager = TokenizerManager()

# 测试不同模型的token计算
models_to_test = [
    LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN,
    LLMModel.DEEPSEEK_V3_OFFICIAL,
    LLMModel.QWEN3_14B,
    LLMModel.QWEN3_32B,
    LLMModel.QWQ
]

for model in models_to_test:
    try:
        token_count = tokenizer_manager.calculate_tokens(text, model)
        print(f"{model.value}: {token_count} tokens")
    except Exception as e:
        print(f"{model.value}: Error - {str(e)}")

# 测试批量计算
print(f"\n=== 批量计算测试 ===")
test_texts = [
    "短文本",
    "这是一个中等长度的测试文本，包含一些中文内容。",
    text  # 原始长文本
]

for model in [LLMModel.DEEPSEEK_R1_DISTILL_QWEN_32B_ALIYUN]:
    try:
        token_counts = tokenizer_manager.calculate_tokens_batch(test_texts, model)
        print(f"{model.value}:")
        for i, count in enumerate(token_counts):
            text_preview = test_texts[i][:20] + "..." if len(test_texts[i]) > 20 else test_texts[i]
            print(f"  - '{text_preview}': {count} tokens")
        break
    except Exception as e:
        print(f"批量测试失败: {str(e)}")

print("\n=== 分词器信息 ===")
available_tokenizers = tokenizer_manager.get_available_tokenizers()
for model, info in available_tokenizers.items():
    status = "✅ 已加载" if info.loaded else "❌ 未加载"
    print(f"{model.value}: {status} - {info.model_id}")
    if info.error_message:
        print(f"  错误: {info.error_message}")
