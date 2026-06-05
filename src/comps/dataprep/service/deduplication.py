# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import re
import asyncio
import os
from typing import List, Dict, Any
from comps import CustomLogger
from comps.dataprep.config import get_dataprep_llm_config, get_llm_extra_body

logger = CustomLogger("dataprep-deduplication", os.getenv("LOG_LEVEL", "INFO"))

async def deduplicate_questions(client: Any, qa_results: List[Dict[str, Any]], lang: str = "zh") -> List[Dict[str, Any]]:
    """
    利用模型去重问答，支持多语言提示词
    """
    if not qa_results:
        return []
    questions_list = [
        {
            "i": idx,
            "q": qa.get("题目", ""),
            "t": qa.get("题型", ""),
            "a": qa.get("答案", "")
        }
        for idx, qa in enumerate(qa_results)
    ]

    questions_text = json.dumps(questions_list, ensure_ascii=False)

    # ======== 根据语言切换提示词 ========
    if lang == "th":
        instruction = (
            "คุณเป็นผู้เชี่ยวชาญในการกำจัดคำถามที่ซ้ำซ้อน (Semantic Deduplication)\n"
            "【กฎการตัดสินใจ】\n"
            "1. หากคำถามมีเนื้อหาเหมือนกันหรือคล้ายกันมาก ให้จัดอยู่ในกลุ่มเดียวกัน\n"
            "2. **สำคัญ**: หากคำถามเหมือนกันแต่ตรรกะของคำตอบข้อหนึ่งผิด (เช่น ถามเวลาแต่ตอบสถานะปุ่ม) "
            "ให้เลือกข้อที่คำตอบมีความสมเหตุสมผลและสอดคล้องกับคำถามมากที่สุดเป็น 'ตัวแทน' (Representative)\n"
            "3. แยกประเภท 'คำถามอัตนัย' (问答题) และ 'คำถามเติมคำ' (填空题) ออกจากกันเสมอ"
        )
    elif lang == "en":
        instruction = (
            "You are a semantic deduplication assistant for Q&A pairs.\n"
            "【Decision Rules】\n"
            "1. Group questions that have the same or very similar semantic meaning.\n"
            "2. **CRITICAL**: If questions are duplicates but one has a logical error in the answer "
            "(e.g., asking for time but answering with a button state), always select the one with the most logical and accurate answer as the 'Representative'.\n"
            "3. Do not mix '问答题' and '填空题'."
        )
    else:
        instruction = (
            "你是一个语义去重助手。请将意思相同或极度相似的题目归类。\n"
            "【判定规则】\n"
            "1. 题型必须一致（问答题/填空题不可混淆）。\n"
            "2. **核心要求**：如果题目相同，但其中一项答案逻辑错误（例如问时间却回答状态），"
            "必须选择逻辑最正确、与问法最匹配的一项作为代表（Representative）。"
        )

    # 3. 构造最终提示词
    prompt = f"""{instruction}

    输出格式 - NDJSON】
    - 仅输出纯文本 NDJSON，每行一条。
    - 格式：r:<代表项索引>|g:<所有重复项索引，逗号分隔>
    
    示例：
    r:0|g:0,2
    r:15|g:15,43
    
    【数据】
    {questions_text}
    """

    # 调用模型
    llm_config = get_dataprep_llm_config()
    extra_body = get_llm_extra_body(llm_config.model)

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=llm_config.model,
        temperature=0,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
        extra_body=extra_body
    )

    if hasattr(response, 'usage') and response.usage:
        logger.info(f"total_tokens: {response.usage.total_tokens}")

    ndjson_text = response.choices[0].message.content.strip()
    ndjson_text = re.sub(r'<think>.*?</think>', '', ndjson_text, flags=re.DOTALL)
    ndjson_text = re.sub(r'<thinking>.*?</thinking>', '', ndjson_text, flags=re.DOTALL)
    ndjson_text = ndjson_text.strip()

    # ======== 解析 NDJSON ========
    def parse_short_ndjson(text):
        parsed = []
        for line in text.splitlines():
            line = line.strip()
            if not line or "|" not in line: continue
            try:
                left, right = line.split("|", 1)
                rep = int(left.replace("r:", "").strip())
                groups = [int(x) for x in right.replace("g:", "").strip().split(",") if x.strip()]
                parsed.append({"rep": rep, "group": groups})
            except:
                continue
        return parsed

    parsed_result = parse_short_ndjson(ndjson_text)

    unique_qa_results = []
    seen_indices = set()
    for item in parsed_result:
        idx = item["rep"]
        if idx not in seen_indices:
            qa = qa_results[idx].copy()
            qa["group_indices"] = item["group"]
            unique_qa_results.append(qa)
            seen_indices.update(item["group"])

    return unique_qa_results
