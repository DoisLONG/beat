# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import os
import re
from typing import List, Dict, Any, Tuple
from openai import OpenAI
from comps.dataprep.prompt.prompt_manager import PromptRegistry, PromptKey, Lang
from comps import CustomLogger
from comps.dataprep.config import (
    DATAPREP_QA_CONCURRENCY_LIMIT,
    get_dataprep_llm_config,
    get_llm_extra_body,
)
from comps.dataprep.service.content_agent import extract_knowledge_point, build_essay_questions, \
    build_gap_filling_question, get_client
from comps.dataprep.service.generation_constraint_qa import make_excel_qa_constraint_prompt
from comps.dataprep.utils import extract_json_from_response, clean_prefix

logger = CustomLogger("dataprep-universal_qa", "INFO")

# Constants
TOTAL_ROUNDS = int(os.getenv("TOTAL_ROUNDS", 10))
MAX_SUPPLEMENT_ROUNDS = int(os.getenv("MAX_SUPPLEMENT_ROUNDS", 3))
MAX_TOKENS_QA = 4000
MAX_TOKENS_BG = 2000
CONCURRENCY_LIMIT = DATAPREP_QA_CONCURRENCY_LIMIT
QA_PARSE_PATTERN = re.compile(r"题目[:：](.*?)\n题型[:：](.*?)\n答案[:：](.*?)\n难度因子[:：](.*?)(?=\n题目|$)",
                               re.DOTALL | re.MULTILINE)


def _extract_qa_objects(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("qa_list", "questions", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload:
            return [payload]
    return []


def _map_question_type_to_cn(raw_type: object) -> str:
    value = str(raw_type or "").strip().lower().replace("-", "_")
    mapping = {
        "short_answer": "问答题",
        "essay": "问答题",
        "qa": "问答题",
        "问答题": "问答题",
        "fill_in_the_blank": "填空题",
        "fill_blank": "填空题",
        "blank": "填空题",
        "填空题": "填空题",
    }
    return mapping.get(value, "")


def get_file_type(filename: str) -> str:
    """
    根据文件扩展名确定文件类型。
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.xlsx', '.xls']:
        return 'excel'
    elif ext in ['.docx', '.doc', '.pdf']:
        return 'word_pdf'
    else:
        return 'unknown'


def row_to_text(row: dict) -> str:
    """
    将行字典转换为文本表示形式。
    """
    lines = []
    for k, v in row.items():
        if isinstance(v, dict):
            lines.append(f"{k}: {row_to_text(v)}")
        elif isinstance(v, list):
            if len(v) == 0:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for i, item in enumerate(v):
                    lines.append(f"  [{i + 1}]")
                    if isinstance(item, (dict, list)):
                        lines.append(row_to_text(item))
                    else:
                        lines.append(f"    {item}")
        else:
            v_str = str(v).strip().replace("\n", " ")
            lines.append(f"{k}: {v_str}")
    return "\n".join(lines)


async def make_excel_qa_prompt(row: dict, client: OpenAI,filename: str, user_prompt: str = "", min_pairs: int = 1,
                               total_items: int = 1, lang: str = "zh", ) -> str:
    """
    根据excel行内容生成问答对.
    使用PromptRegistry注册器方式获取提示词模板，支持多语言.
    """
    # 处理行内容
    # row_content = row_to_text(row)
    # 先提取一边知识点，在让模型根据有知识点参与的提示词进行题目生成
    prompt = PromptRegistry.get(
        PromptKey.GET_UNIVERSAL_EXCEL_KNOWLEDGE_235B,
        Lang(lang),
        excel_row_json=json.dumps(row,ensure_ascii=False)
    )
    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    # 提取一下
    res = await asyncio.to_thread(
        client.chat.completions.create,
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        extra_body=extra_body,
        temperature=0.3
    )
    try:
        knowledge_list = extract_json_from_response(res.choices[0].message.content)
    except ValueError as exc:
        logger.warning(f"Excel知识点提取结果不是有效JSON，当前行跳过出题: {exc}")
        return ""

    if not isinstance(knowledge_list, dict):
        logger.warning("Excel知识点提取结果不是对象，当前行跳过出题")
        return ""

    knowledge_infos = knowledge_list.get("knowledge_infos")
    if not isinstance(knowledge_infos, list) or not knowledge_infos:
        logger.info("Excel知识点提取结果为空，当前行不生成题目")
        return ""

    # 获取提示词模板并填充参数
    prompt = PromptRegistry.get(
        PromptKey.MAKE_UNIVERSAL_EXCEL_QA_235B,
        Lang(lang),
        knowledge_point_infos=json.dumps(knowledge_infos,
                                         ensure_ascii=False),
        excel_row_json=json.dumps(row, ensure_ascii=False)
    )
    if user_prompt:
        if lang == "th":
            prompt += f"\n【ข้อกำหนดเพิ่มเติม】{user_prompt}\n\n"
        elif lang == "en":
            prompt += f"\n【Additional Requirements】{user_prompt}\n\n"
        else:
            prompt += f"\n【补充要求】{user_prompt}\n\n"
    return prompt

def parse_qa_response(text: str, item: dict, filename: str) -> list:
    """
    解析 QA 响应
    """
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    try:
        payload = extract_json_from_response(text)
    except ValueError as exc:
        logger.warning(f"通用QA解析失败，模型未返回有效JSON: {exc}")
        return []

    qa_objects = _extract_qa_objects(payload)
    results = []
    for qa in qa_objects:
        ques = str(qa.get("question", "")).strip()
        qtype = _map_question_type_to_cn(qa.get("question_type", ""))
        if not ques or not qtype:
            continue

        # 题目添加文件名前缀
        ques = f"【{os.path.splitext(os.path.basename(filename))[0]}】{ques}"
        raw_answer = qa.get("answer", "")
        if qtype == "问答题":
            if isinstance(raw_answer, list):
                scoring_points = [
                    clean_prefix(str(point).strip())
                    for point in raw_answer
                    if str(point).strip()
                ]
            else:
                scoring_points = [
                    clean_prefix(a)
                    for a in re.split(r'[\n;；]', str(raw_answer))
                    if a.strip()
                ]
            answer_data = str(scoring_points)
        else:
            if isinstance(raw_answer, list):
                answer_data = "；".join(str(a).strip() for a in raw_answer if str(a).strip())
            else:
                answer_data = str(raw_answer).strip()
        # 去除不合规的填空题
        if qtype=="填空题" and "___" not in ques:
            continue
        try:
            diff_value = float(qa.get("difficulty_factor", qa.get("difficulty", 0.5)))
            diff_value = max(0.0, min(1.0, diff_value))
        except:
            diff_value = 0.5
        qa_item = {
            "题目": ques,
            "题型": qtype,
            "答案": answer_data,
            "难度因子": diff_value,
            "行号": item.get("行号", -1),
            "来源字段": str(qa.get("source_field", item.get("title", item.get("table_title", "")))).strip(),
            "内容": row_to_text(item),
            "定位": get_position_str(item)
        }
        results.append(qa_item)
    return results


def get_position_str(item: dict) -> str:
    """
    根据 item 中的字段自动判断格式并生成定位字符串。
    :param item: 数据行字典
    :return: 格式化后的定位字符串
    """

    # 辅助函数：安全获取值，去除 None 和前后空格
    def get(key):
        return str(item.get(key, "") or "").strip()

    # ---------------------------------------------------------
    # 策略 1: 章节/标题模式 (Section / Heading)
    # 对应: f'{heading_num} {title}' 或 table 变体
    # ---------------------------------------------------------
    heading = get("heading_num") or get("table_index")
    title = get("title") or get("table_title")

    # 如果检测到由 heading 或 title，说明这是一行标题数据
    if heading or title:
        # 过滤空值并用空格拼接
        return " ".join(filter(None, [heading, title]))

    # ---------------------------------------------------------
    # 策略 2: SOP 详细步骤模式 (当前提供的 item 样例)
    # 对应: f"{阶段}-{步骤序号}-{作业点}-{field}"
    # ---------------------------------------------------------
    # 注意：字典里 key 包含换行符 '步骤\n序号'，这里做了兼容处理
    step_seq = get("步骤序号") or get("步骤\n序号")
    stage = get("阶段")
    work_point = get("作业点")

    if stage or step_seq or work_point:
        # 过滤掉空值，用 "-" 拼接
        parts = [stage, step_seq, work_point]
        return "-".join(filter(None, parts))

    # ---------------------------------------------------------
    # 策略 3: 标准作业卡模式
    # 对应: f"{标准作业卡名称}-{序号}-{field}"
    # ---------------------------------------------------------
    card_name = get("标准作业卡名称")
    seq_num = get("序号")

    if card_name or seq_num:
        parts = [card_name, seq_num]
        return "-".join(filter(None, parts))

    # ---------------------------------------------------------
    # 策略 4: 兜底模式 (Fallback)
    # 如果以上都没有，尝试用行号
    # ---------------------------------------------------------
    row_num = get("行号")
    if row_num:
        return f"行号_{row_num}"

    return "未知定位"


async def generate_background(item: dict, filename: str, client: OpenAI, lang: str="zh") -> tuple[str, int, int]:
    """
    为项目生成背景。
    """
    content = row_to_text(item)
    prompt = PromptRegistry.get(PromptKey.BACKSTORY_GENERATE_EXCEL_235B,Lang(lang),content=content)
    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=MAX_TOKENS_BG,
            extra_body=extra_body
        )
        prompt_tokens = response.usage.prompt_tokens if hasattr(response, "usage") and response.usage else 0
        completion_tokens = response.usage.completion_tokens if hasattr(response, "usage") and response.usage else 0
        response_json = json.loads(response.choices[0].message.content.strip())
        background = response_json.get("background", "")
        return background, prompt_tokens, completion_tokens
    except Exception as e:
        logger.error(f"生成背景失败: {e}")
        return "", 0, 0


def _process_excel_item(item: dict, background: str) -> List[Dict[str, Any]]:
    """
    处理 Excel 项目以生成 QA。
    """
    steps = extract_knowledge_point(item, 5)
    logger.info(f"完成知识点提取: {steps.__str__()[:100]}")

    # 排序归类
    essay_knowledge_point = []
    filling_knowledge_point = []
    for step in steps:
        if step['题型'] == '问答题':
            essay_knowledge_point.append(step)
        elif step['题型'] == '填空题':
            filling_knowledge_point.append(step)

    essay_list = build_essay_questions(essay_knowledge_point, item['内容'])
    logger.info(f"完成问答题生成: {essay_list.__str__()[:100]}")

    filling_list = build_gap_filling_question(filling_knowledge_point, item['内容'])
    logger.info(f"完成填空题生成: {filling_list.__str__()[:100]}")

    qa_list = []
    # 合并问答题和填空题，交替排列
    max_len = max(len(essay_list), len(filling_list))
    for i in range(max_len):
        if i < len(essay_list):
            essay_qa = essay_list[i]
            qa_item = {
                "题目": essay_qa["题目"],
                "题型": "问答题",
                "答案": str(essay_qa["答案"]),
                "难度因子": essay_qa.get("难度因子", 0.5),
                "行号": item.get("行号", -1),
                "来源字段": essay_qa.get("来源字段", ""),
                "内容": row_to_text(item),
                "定位": get_position_str(item),
                "背景": background
            }
            qa_list.append(qa_item)
        if i < len(filling_list):
            filling_qa = filling_list[i]
            qa_item = {
                "题目": filling_qa["题目"],
                "题型": "填空题",
                "答案": filling_qa["答案"],
                "难度因子": filling_qa.get("难度因子", 0.5),
                "行号": item.get("行号", -1),
                "来源字段": filling_qa.get("来源字段", ""),
                "内容": row_to_text(item),
                "定位": get_position_str(item),
                "背景": background
            }
            qa_list.append(qa_item)
    return qa_list


async def _process_item(item: dict, filename: str, client: OpenAI, user_prompt: str, min_pairs: int, total_items: int,
                        file_type: str, lang: str="zh",scope_type:str = "all") -> Tuple[List[Dict[str, Any]], int, int]:
    """
    处理单个项目以生成 QA。
    """
    background, prompt_tokens1, completion_tokens1 = await generate_background(item, filename, client, lang= lang)
    prompt = ""
    if scope_type == "all":
        prompt = await make_excel_qa_prompt(row=item, filename=filename, user_prompt=user_prompt, min_pairs=min_pairs, total_items=total_items, lang=lang,client=client)
    else :
        prompt = await make_excel_qa_constraint_prompt(item,client, user_prompt, lang, scope_type=scope_type)
    if prompt is None or prompt == "":
        return [], 0, 0
    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=MAX_TOKENS_QA,
            extra_body=extra_body
        )
        prompt_tokens = response.usage.prompt_tokens if hasattr(response, "usage") and response.usage else 0
        completion_tokens = response.usage.completion_tokens if hasattr(response, "usage") and response.usage else 0
        resp_text = response.choices[0].message.content.strip()
        if not resp_text:
            return [], prompt_tokens + prompt_tokens1, completion_tokens + completion_tokens1
        qa_list = parse_qa_response(resp_text, item, filename)
        for qa in qa_list:
            qa["背景"] = background
        return qa_list, prompt_tokens + prompt_tokens1, completion_tokens + completion_tokens1
    except Exception as e:
        logger.error(f"生成 QA 失败: {e}")
        return [], 0, 0


async def batch_generate_universal_qa(
        structured_rows: List[Dict[str, Any]],
        filename: str,
        client: OpenAI,
        user_prompt: str,
        sop_id: int,
        db_client,
        lang: str = "zh",
        scope_type:str = "all"
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    通用 QA 生成功能，根据文件类型处理每一行/部分。
    """
    file_type = get_file_type(filename)
    if file_type == 'unknown':
        raise ValueError(f"Unsupported file type for {filename}")

    all_qa = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_items = len(structured_rows)
    if total_items == 0:
        return [], 0, 0

    min_pairs_base = max(1, (TOTAL_ROUNDS + total_items - 1) // (2 * total_items))
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def process_item(item: dict) -> Tuple[List[Dict[str, Any]], int, int]:
        async with semaphore:
            return await _process_item(item, filename, client, user_prompt, min_pairs_base, total_items, file_type, lang, scope_type)

    tasks = [process_item(item) for item in structured_rows]
    results = await asyncio.gather(*tasks)
    for qa_list, pt, ct in results:
        all_qa.extend(qa_list)
        total_prompt_tokens += pt
        total_completion_tokens += ct

    db_client.update_percent_by_id(sop_id, "80%", lang=lang)

    logger.info("=" * 60)
    logger.info(f"总计生成题目: {len(all_qa)}")
    logger.info(f"Token使用: prompt={total_prompt_tokens}, completion={total_completion_tokens}")
    logger.info("=" * 60)
    return all_qa, total_prompt_tokens, total_completion_tokens
