# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import difflib
import re
import os
from typing import Tuple

from openai import OpenAI
from comps import CustomLogger
from comps.dataprep.config import get_dataprep_llm_config, get_llm_extra_body
from comps.dataprep.prompt.llm_prompts import get_sop_qa_prompt, get_sop_background_prompt, get_sop_supplement_prompt

logger = CustomLogger("prepare_genera_util", "INFO")

# 定义常量
SOP_QA_FIELDS = [
    "作业事项任务",
    "所需材料物品等",
    "具体做什么",
    "做到什么程度",
    "特别风险",
    "特别风险管控"
]
SOP_INVALID_VALUES = ["", "/", None]
QUESTION_TYPE_LIST = ["填空题", "问答题"]


TOTAL_ROUNDS = int(os.getenv("TOTAL_ROUNDS", 10))
MAX_SUPPLEMENT_ROUNDS = int(os.getenv("MAX_SUPPLEMENT_ROUNDS", 3))

# =================== SOP文件 问答对生成 Prompt ===================
# 修改：增加 min_pairs、total_rows 参数，实现全局目标与每行最低题量约束
async def make_multi_qa_prompt_sop_international(row: dict, filename: str, lang: str = "zh", user_prompt: str = "", min_pairs: int = 1, total_rows: int = 1) -> str:
    """
    SOP文件多字段问答对生成 Prompt（题型和难度自适应，题量随内容丰富度自动调整）
    - 增加：全局最低题量 TOTAL_ROUNDS 与本行最低组数 M（1组=问答题+填空题）
    - 保证严格交替与数量平衡，素材不足则降级到可配对最大组数 K
    - SOP多语言问答对生成提示词
      lang: "zh" 为中文, "th" 为泰文
    """
    extra_info = get_extra_info(row, lang)
    prompt = get_sop_qa_prompt(
        row_content=row.get('内容', '').strip(),
        filename=filename,
        extra_info=extra_info,
        lang=lang,
        user_prompt=user_prompt,
        min_pairs=min_pairs,
        total_rows=total_rows,
        TOTAL_ROUNDS=TOTAL_ROUNDS
    )
    return prompt

def parse_multi_qa_response(text: str, row: dict, filename: str) -> list:
    """解析 LLM 返回的问答对，放宽为允许同字段多题"""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    pattern = r"题目[:：](.*?)\n题型[:：](.*?)\n答案[:：](.*?)\n难度因子[:：](.*?)\n来源字段[:：](.*?)(?=\n题目|$)"
    matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
    results = []
    for idx, (ques, qtype_in_ans, ans, diff, field) in enumerate(matches):
        ques = f"【{os.path.splitext(os.path.basename(filename))[0]}】{ques.strip()}"
        ans = ans.strip()
        qtype = qtype_in_ans.strip()
        diff = diff.strip()
        field = field.strip()
        if str(row.get(field, "")).strip() in SOP_INVALID_VALUES:
            continue
        if qtype == "问答题":
            try:
                scoring_points = eval(ans)
                if not isinstance(scoring_points, list):
                    scoring_points = [ans]
            except:
                scoring_points = [p.strip() for p in re.split(r'[\n;；]', ans) if p.strip()]
            seen = set()
            unique_points = []
            for p in scoring_points:
                if p not in seen:
                    seen.add(p)
                    unique_points.append(p)
            answer_data = str(unique_points)
        else:
            answer_data = ans
        try:
            diff_value = float(re.findall(r"[0-9.]+", diff)[0])
            diff_value = max(0.0, min(1.0, diff_value))
        except:
            diff_value = 0.5

        position_parts = []
        for key in ['阶段', '步骤序号', '作业点']:
            value = row.get(key)
            if value:
                position_parts.append(str(value))
        position_parts.append(field)
        position = '-'.join(position_parts)

        qa_item = {
            "行号": row["行号"],
            "题目": ques,
            "题型": qtype,
            "答案": answer_data,
            "难度因子": diff_value,
            "定位": position,
            "内容": row.get("内容", ""),
            "来源字段": field
        }
        results.append(qa_item)
        # is_valid, reason = validate_qa_quality(qa_item, row)
        # if is_valid:
        #     results.append(qa_item)
    return results

async def batch_generate_qa_multi_fields(structured_rows: list, filename: str, client: OpenAI, user_prompt: str,sop_id:int,db_client, lang: str="zh"):
    """批量生成多字段问答对 (加入最小题量与补充逻辑)"""
    all_qa = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_rows = len(structured_rows)
    # 按总目标粗分最低组数（每组2题）
    min_pairs_base = max(1, (TOTAL_ROUNDS + total_rows - 1) // (2 * total_rows))
    for idx, row in enumerate(structured_rows):
        logger.info(f"正在处理第 {idx + 1}/{total_rows} 行...")
        row = clean_row(row)
        # 生成背景描述
        background_content, prompt_tokens_background, completion_tokens_background = await generate_background_description(row, filename, client, lang)
        # 生成问答对
        prompt = await make_multi_qa_prompt_sop_international(row, filename, lang, user_prompt, min_pairs=min_pairs_base, total_rows=total_rows)
        field_count = sum(1 for f in SOP_QA_FIELDS if str(row.get(f, "")).strip() not in SOP_INVALID_VALUES)
        temperature = 0.2 if field_count > 4 else 0.3
        llm_config = get_dataprep_llm_config()
        model_name = llm_config.model
        extra_body = get_llm_extra_body(model_name)
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=4000,
                extra_body=extra_body
            )
            if hasattr(response, 'usage') and response.usage:
                total_prompt_tokens += response.usage.prompt_tokens + prompt_tokens_background
                total_completion_tokens += response.usage.completion_tokens + completion_tokens_background
            resp_text = response.choices[0].message.content
            qa_list = parse_multi_qa_response(resp_text, row, filename)
            for qa in qa_list:
                qa["背景"] = background_content
            all_qa.extend(qa_list)
            logger.info(f"本行生成 {len(qa_list)} 题")
        except Exception as e:
            logger.info(f"处理失败: {str(e)}")
            continue
    db_client.update_percent_by_id(sop_id, "80%", lang=lang)
    # 补充逻辑
    if len(all_qa) < TOTAL_ROUNDS:
        logger.info(f"总题量 {len(all_qa)} < 目标 TOTAL_ROUNDS={TOTAL_ROUNDS}，开始补充生成")
        supplement_round = 0
        existing_titles = {q['题目'] for q in all_qa}
        while len(all_qa) < TOTAL_ROUNDS and supplement_round < MAX_SUPPLEMENT_ROUNDS:
            need = TOTAL_ROUNDS - len(all_qa)
            logger.info(f"补充轮次 {supplement_round + 1} / {MAX_SUPPLEMENT_ROUNDS}，尚需 {need} 题")
            for row in structured_rows:
                if len(all_qa) >= TOTAL_ROUNDS:
                    break
                extra = await generate_sop_supplement(row, filename, existing_titles, need, client, user_prompt)
                for qa in extra:
                    qa['背景'] = qa.get('背景', '')
                all_qa.extend(extra)
                existing_titles.update({e['题目'] for e in extra})
            supplement_round += 1
        if len(all_qa) < TOTAL_ROUNDS:
            logger.info(f"补充后仍未达到 TOTAL_ROUNDS，当前 {len(all_qa)}")
        else:
            logger.info(f"补充后达到目标题量 {len(all_qa)}")
    logger.info(f"\n{'=' * 50}")
    logger.info(f"总计生成: {len(all_qa)} 道题目")
    logger.info(f"Token 使用: prompt={total_prompt_tokens}, completion={total_completion_tokens}")
    logger.info(f"{'=' * 50}\n")
    return all_qa, total_prompt_tokens, total_completion_tokens


async def generate_background_description(row, filename: str, client: OpenAI, lang: str = "zh") -> Tuple[str, int, int]:
    """
    生成 SOP 问答的背景描述。
    生成背景描述的国际化版本
    lang: "zh" 为中文, "th" 为泰文, "en" 为英文
    """
    prompt = get_sop_background_prompt(
        filename=filename,
        row_content=row.get('内容', ''),
        lang=lang
    )
    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            extra_body=extra_body
        )
        backend_info = response.choices[0].message.content.strip()
        prompt_tokens = 0
        completion_tokens = 0
        if hasattr(response, 'usage') and response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens

        return backend_info, prompt_tokens, completion_tokens
    except Exception as e:
        logger.error(f"背景描述生成失败: {e}")
        return "", 0, 0

def validate_qa_quality(qa_item: dict, row: dict) -> tuple:
    """检查生成的 QA 质量，包括题目长度、格式、与原文相关度"""
    question = qa_item['题目']
    answer = qa_item['答案']
    qtype = qa_item['题型']
    content = row.get('内容', '')

    # 2 填空题检查
    if qtype == '填空题':
        if '______' not in question:
            return False, "填空题缺少空格"
        if not isinstance(answer, str):
            return False, "填空题答案格式错误（应为字符串）"
        if len(answer.strip()) < 1 or len(answer.strip()) > 25:
            return False, f"填空题答案长度不合适: {len(answer.strip())}字"
        # 填空题必须在原文中出现
        if answer.strip() not in content and not any(word in content for word in re.split(r'[，,]', answer)):
            return False, "填空题答案与原文不符"

    # 3 问答题检查
    elif qtype == '问答题':
        # 确保答案是字符串形式的列表
        if not isinstance(answer, str):
            return False, "问答题答案格式错误（应为列表字符串）"
        try:
            ans_list = eval(answer)
            if not isinstance(ans_list, list) or len(ans_list) == 0:
                return False, "问答题答案列表为空"
        except:
            return False, "问答题答案解析失败"

        # 相关度检查：至少有一个评分点能与原文匹配
        # is_related, msg = check_answer_relevance(ans_list, content)
        # if not is_related:
        #     return False, msg

    # 4 题目模板化检测
    # template_phrases = ['在第', '在步骤', '在作业', '完成后', '的第']
    # template_count = sum(1 for phrase in template_phrases if phrase in question)
    # if template_count >= 3:
    #     return False, "题目过于模板化"

    return True, "通过"

def check_answer_relevance(ans_list, content, threshold=0.6):
    """
    检查问答题答案与原文内容的相关度（支持模糊匹配）
    - ans_list: 答案要点列表（list[str]）
    - content: 原文文本（str）
    - threshold: 相似度阈值（默认0.6）
    返回 (bool, str) -> 是否相关, 说明
    """
    if not ans_list or not content:
        return False, "缺少答案或原文内容"

    # 预处理原文文本（去空格、全角符号）
    normalized_content = re.sub(r'\s+', '', content.replace('　', ''))
    found_count = 0

    for point in ans_list:
        point = point.strip()
        if not point:
            continue

        # 提取中文关键词（2字以上的短语）
        keywords = re.findall(r'[\u4e00-\u9fa5]{2,}', point)
        if not keywords:
            continue

        matched = False
        for kw in keywords:
            # 精确匹配
            if kw in normalized_content:
                matched = True
                break

            #  模糊相似度匹配（字符串相似度）
            ratio = difflib.SequenceMatcher(None, kw, normalized_content).ratio()
            if ratio >= threshold:
                matched = True
                break

            # 部分词重叠匹配（至少60%字出现在原文）
            overlap = sum(1 for ch in kw if ch in normalized_content) / len(kw)
            if overlap >= 0.6:
                matched = True
                break

        if matched:
            found_count += 1

    # 计算整体匹配比例
    total_points = len(ans_list)
    relevance_ratio = found_count / total_points if total_points else 0

    # 按比例评估结果
    if relevance_ratio == 0:
        return False, "答案与原文相关度不足"
    elif relevance_ratio < 0.4:
        return False, f"部分相关（匹配度 {relevance_ratio:.2f}）"
    else:
        return True, f"相关度良好（匹配度 {relevance_ratio:.2f}）"

def clean_row(row: dict) -> dict:
    """
    清洗单行数据:
    - 去除首尾空白
    - 合并多余空格/制表符
    - 直接移除换行符
    """
    cleaned = {}
    for k, v in row.items():
        if isinstance(v, str):
            s = v.strip()
            s = re.sub(r'[ \t]+', ' ', s)
            s = re.sub(r'\r?\n+', '', s)
            s = re.sub(r' ', '', s)
            cleaned[k] = s
        else:
            cleaned[k] = v
    return cleaned

async def generate_sop_supplement(row: dict, filename: str, existing_titles: set, need: int, client: OpenAI, user_prompt: str, lang: str = "zh") -> list:
    """补充生成 SOP 问答，确保总题量接近 TOTAL_ROUNDS (轻量补充)"""
    # 构建业务维度信息（有就显示，没有就为空）
    extra_info = get_extra_info(row, lang)

    if need <= 0:
        return []
    prompt = get_sop_supplement_prompt(
        filename=filename,
        row_content=row.get('内容', '').strip(),
        existing_titles_count=len(existing_titles),
        need=need,
        extra_info=extra_info,
        user_prompt=user_prompt,
        lang=lang,
        TOTAL_ROUNDS=TOTAL_ROUNDS
    )
    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
            extra_body=extra_body
        )
        resp_text = response.choices[0].message.content
        qa_list = parse_multi_qa_response(resp_text, row,filename)
        # 去重（标题级）
        filtered = [q for q in qa_list if q['题目'] not in existing_titles]
        return filtered
    except Exception as e:
        logger.info(f"补充失败: {e}")
        return []

def get_extra_info(row: dict, lang: str = "zh") -> str:
    """构建业务维度信息字符串"""
    info_parts = []
    if lang == "th":
        if row.get('阶段'): info_parts.append(f"ขั้นตอน: {row['阶段']}")
        if row.get('步骤序号'): info_parts.append(f"ลำดับ: {row['步骤序号']}")
        if row.get('作业点'): info_parts.append(f"จุดงาน: {row['作业点']}")
    elif lang == "en":
        if row.get('阶段'): info_parts.append(f"Stage: {row['阶段']}")
        if row.get('步骤序号'): info_parts.append(f"Step No.: {row['步骤序号']}")
        if row.get('作业点'): info_parts.append(f"Work Point: {row['作业点']}")
    else:
        if row.get('阶段'): info_parts.append(f"阶段：{row['阶段']}")
        if row.get('步骤序号'): info_parts.append(f"步骤：{row['步骤序号']}")
        if row.get('作业点'): info_parts.append(f"作业点：{row['作业点']}")

    return " | ".join(info_parts) if info_parts else ""
