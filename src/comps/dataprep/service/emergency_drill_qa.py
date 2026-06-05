# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import re
import asyncio
import os
from typing import List, Dict, Tuple, Any
from openai import OpenAI
from comps import CustomLogger
from comps.dataprep.config import (
    DATAPREP_QA_CONCURRENCY_LIMIT,
    get_dataprep_llm_config,
    get_llm_extra_body,
)
from comps.dataprep.prompt.llm_prompts import get_emergency_drill_prompt, get_emergency_drill_background_prompt, get_emergency_drill_supplement_prompt

logger = CustomLogger("emergency_drill_qa", "INFO")

# 常量
DRILL_MIN_TABLE_CONTENT_LEN = 10
DRILL_MIN_SECTION_CONTENT_LEN = 60  # 新增：章节最低有效长度
MAX_TOKENS_QA = 4000
MAX_TOKENS_BG = 2000
CONCURRENCY_LIMIT = DATAPREP_QA_CONCURRENCY_LIMIT
MAX_QA_PER_SECTION = 6  # 每个章节最大生成题目数
MAX_QA_PER_TABLE = 4  # 每个表格最大生成题目数
# 新增全局题量与补充轮次
TOTAL_ROUNDS = int(os.getenv("TOTAL_ROUNDS", 10))  # 总题数目标（单题计）
MAX_SUPPLEMENT_ROUNDS = int(os.getenv("MAX_SUPPLEMENT_ROUNDS", 3))
QA_PARSE_PATTERN = re.compile(r"题目[:：](.*?)\n题型[:：](.*?)\n答案[:：](.*?)\n难度因子[:：](.*?)(?=\n题目|$)",
                              re.DOTALL | re.MULTILINE)


def section_to_text(section: dict) -> str:
    lines = []
    for k, v in section.items():
        if k in ("children",):
            continue
        if isinstance(v, dict):
            lines.append(f"{k}:")
            lines.append(section_to_text(v))
        elif isinstance(v, list):
            if len(v) == 0:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for i, item in enumerate(v):
                    lines.append(f"  [{i + 1}]")
                    if isinstance(item, (dict, list)):
                        lines.append(section_to_text(item))
                    else:
                        lines.append(f"    {item}")
        else:
            v_str = str(v).strip().replace("\n", " ")
            lines.append(f"{k}: {v_str}")
    return "\n".join(lines)


def make_emergency_drill_prompt(section: dict, filename: str, user_prompt: str = "", min_pairs: int = 1,
                                total_items: int = 1) -> str:

    # 使用 llm_prompts 中的函数生成提示词
    return get_emergency_drill_prompt(section, filename, section_to_text, user_prompt, min_pairs, total_items, TOTAL_ROUNDS)


def _clean_table_cells(table: Dict[str, Any]) -> str:
    cells = table.get('cells', [])
    cleaned = [re.sub(r'[\s\W]+', '', str(c)) for c in cells if c]
    return ''.join(cleaned)


def is_short_table(table: dict, min_length: int = DRILL_MIN_TABLE_CONTENT_LEN) -> bool:
    return len(_clean_table_cells(table)) < min_length


# 新增：低价值表格判定（仅有表头、序号、空单元格，不生成题目）
HEADER_KEYWORDS = {"序号", "整改项", "整改措施", "整改时间", "整改人", "整改情况"}


def is_low_value_table(table: dict) -> bool:
    if 'cells' not in table:
        return False
    title = table.get('table_title') or table.get('table_name') or ''
    raw_cells = [str(c).strip() for c in table.get('cells', []) if str(c).strip()]
    if not raw_cells:
        return True
    numeric_only = 0
    meaningful = []
    header_count = 0
    for c in raw_cells:
        if c in HEADER_KEYWORDS:
            header_count += 1
            continue
        if re.fullmatch(r'[0-9]+', c):
            numeric_only += 1
            continue
        if re.search(r'[\u4e00-\u9fa5A-Za-z]', c) and len(c) > 1 and c not in HEADER_KEYWORDS:
            meaningful.append(c)
    total_non_empty = len(raw_cells)
    if total_non_empty == 0:
        return True
    numeric_ratio = numeric_only / total_non_empty
    header_ratio = header_count / total_non_empty
    if (numeric_ratio + header_ratio) > 0.75 and len(meaningful) == 0:
        return True
    if numeric_ratio > 0.5 and len(meaningful) < 3:
        return True
    # if len(meaningful) < 2:
    #     return True
    return False


# 结构性空表：只有表头+递增序号(1..n) + 空白
def is_structurally_empty_table(table: dict) -> bool:
    if 'cells' not in table:
        return False
    raw = [str(c).strip() for c in table.get('cells', []) if str(c).strip()]
    if not raw:
        return True
    headers = [c for c in raw if c in HEADER_KEYWORDS]
    numbers = [c for c in raw if re.fullmatch(r'[0-9]+', c)]
    others = [c for c in raw if c not in HEADER_KEYWORDS and not re.fullmatch(r'[0-9]+', c)]
    if len(others) > 0:
        return False
    # 判断数字是否为1..k连续
    if numbers:
        try:
            nums = list(map(int, numbers))
            nums_sorted = sorted(nums)
            if nums_sorted == list(range(1, len(nums_sorted) + 1)):
                # 全是连续序号 + 纯表头 -> 结构空
                return True
        except Exception:
            pass
    # 只有表头
    if len(headers) == len(raw):
        return True
    return False


# 生成后针对内容再做一次结构空校验
EMPTY_CONTENT_KEYWORDS = HEADER_KEYWORDS


def is_structurally_empty_content(qa: dict) -> bool:
    content = qa.get("内容", "")
    # 去除cells行标签与索引
    pure = re.sub(r'cells:|\n\s*\[\d+\]\n?', '', content)
    # 去掉表头关键词与数字
    pure = re.sub(r'(序号|整改项|整改措施|整改时间|整改人|整改情况)', '', pure)
    pure = re.sub(r'\d+', '', pure)
    pure = re.sub(r'\s+', '', pure)
    return len(pure) == 0


def is_low_value_section(section: dict) -> bool:
    content = section.get("content", "")
    if not content:
        return True
    # 兼容文章型内容，避免re.sub报错
    try:
        cleaned = re.sub(r"[\s\p{P}]+", "", content)
    except re.error:
        cleaned = re.sub(r"[\s.,!?;:，。！？；：]+", "", content)
    cleaned = re.sub(r"\W", "", cleaned)
    if len(cleaned) < DRILL_MIN_SECTION_CONTENT_LEN:
        return True
    total_len = max(1, len(content))
    digits_ratio = len(re.findall(r"\d", content)) / total_len
    whitespace_ratio = len(re.findall(r"\s", content)) / total_len
    if digits_ratio > 0.35 or (digits_ratio + whitespace_ratio) > 0.75:
        return True
    # if re.search(r"(拍照|点评|电话|地址|联系人|评审人员|请指挥部领导)", content) and not re.search(r"(流程|措施|触发|风险|控制)", content):
    #     return True
    return False


def parse_emergency_drill_qa_response(text: str, section: dict, filename: str) -> list:
    """
    解析模型生成的应急预案演练问答对文本，提取题目、题型、答案、难度因子等字段。
    """
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    pattern = r"题目[:：](.*?)\n题型[:：](.*?)\n答案[:：](.*?)\n难度因子[:：](.*?)(?=\n题目|$)"
    matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
    results = []
    for (ques, qtype, ans, diff) in matches:
        ques, qtype, ans, diff = map(str.strip, [ques, qtype, ans, diff])
        ques = f"【{os.path.splitext(os.path.basename(filename))[0]}】{ques}"
        scoring_points = [a.strip() for a in re.split(r'[\n;；]', ans) if a.strip()]
        answer_data = str(scoring_points) if qtype == "问答题" else ans
        try:
            diff_value = float(re.findall(r"[0-9.]+", diff)[0])
            diff_value = max(0.0, min(1.0, diff_value))
        except:
            diff_value = 0.5
        qa_item = {
            "题目": ques,
            "题型": qtype,
            "答案": answer_data,
            "难度因子": diff_value,
            "来源字段": section.get("title", section.get("table_title", "")),
            "内容": section_to_text(section),
            "定位": f'{section.get("heading_num", section.get("table_index", ""))} {section.get("title", section.get("table_title", ""))}'
        }
        results.append(qa_item)
    return results


async def generate_emergency_drill_background(item: dict, filename: str, client: OpenAI) -> tuple[str, int, int]:
    """
    针对章节型或表格型应急预案演练数据，生成背景故事。
    :param item: 章节型（含content/title）或表格型（含cells/table_title）结构
    :param filename: 文件名
    :param client: OpenAI 客户端
    :return: 背景故事字符串
    """
    # 使用 llm_prompts 中的函数生成提示词
    prompt = get_emergency_drill_background_prompt(item, filename)
    if not prompt:
        return "", 0, 0
    try:
        llm_config = get_dataprep_llm_config()
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=MAX_TOKENS_BG,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False
                }
            }
        )
        if hasattr(response, "usage") and response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
        else:
            prompt_tokens = 0
            completion_tokens = 0
        background = response.choices[0].message.content.strip()
        return background, prompt_tokens, completion_tokens
    except Exception as e:
        logger.error(f"生成应急预案演练背景失败: {e}")
        return "", 0, 0


# 新增低价值问答模式与过滤函数
LOW_VALUE_Q_PATTERNS = [
    r"由______作指示",  # 机械填空
    r"负责人电话", r"医院电话", r"医院地址", r"急救电话",  # 联系方式类
    r"通讯联系", r"演练点评"  # 明显纯标题复述
]


def is_low_value_qa(qa: Dict[str, Any]) -> bool:
    q = qa.get("题目", "")
    a = qa.get("答案", "")
    # 1. 答案为纯数字或电话
    if a and len(a) > 0:
        digits = len(re.findall(r"\d", a))
        if digits / max(1, len(a)) > 0.7:
            return True
    # 2. 题干包含低价值关键词且答案极短（<=4）
    if any(pat in q for pat in ["由", "电话", "地址"]):
        if len(a.strip()) <= 4 and not re.search(r"(流程|措施|原因|影响|改进|评估)", q):
            return True
    # 3. 匹配预定义模式
    for pat in LOW_VALUE_Q_PATTERNS:
        if re.search(pat, q):
            return True
    # 4. 题目与来源字段高度重复（简单复述标题）
    src = qa.get("来源字段", "")
    if src and len(src) > 0:
        core_q = re.sub(r"[【】\d-]", "", q)
        if src in core_q and len(a.strip()) <= 8 and not re.search(r"(原理|流程|风险|改进|评估|关键|触发)", q):
            return True
    return False


async def _add_background_and_generate_qa(item: dict, filename: str, client: OpenAI, user_prompt: str, min_pairs: int,
                                          total_items: int) -> Tuple[List[Dict[str, Any]], int, int]:
    # 过滤逻辑保持
    if 'content' in item and is_low_value_section(item):
        logger.info(f"[SKIP] section title={item.get('title', '')} reason=low_value_section")
        return [], 0, 0
    if 'cells' in item:
        title = item.get('table_title') or item.get('table_name') or ''
        if is_short_table(item) or is_low_value_table(item) or is_structurally_empty_table(item):
            reason = []
            if is_short_table(item): reason.append('short_table')
            if is_low_value_table(item): reason.append('low_value_table')
            if is_structurally_empty_table(item): reason.append('struct_empty_table')
            logger.info(f"[SKIP] table title={title} reason={'|'.join(reason)}")
            return [], 0, 0
    background_content, prompt_tokens1, completion_tokens1 = await generate_emergency_drill_background(item, filename,
                                                                                                       client)
    prompt = make_emergency_drill_prompt(item, filename, user_prompt, min_pairs=min_pairs, total_items=total_items)
    try:
        llm_config = get_dataprep_llm_config()
        extra_body = get_llm_extra_body(llm_config.model)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=MAX_TOKENS_QA,
            extra_body=extra_body
        )
        prompt_tokens = response.usage.prompt_tokens if hasattr(response, "usage") and response.usage else 0
        completion_tokens = response.usage.completion_tokens if hasattr(response, "usage") and response.usage else 0
        resp_text = response.choices[0].message.content.strip()
        if not resp_text or resp_text.lower() in ("无", "没有", "空", "n/a"):
            logger.info(
                f"[SKIP] empty_model_return item_type={'section' if 'content' in item else 'table'} title={item.get('title') or item.get('table_title') or item.get('table_name', '')}")
            return [], 0, 0
        qa_list = parse_emergency_drill_qa_response(resp_text, item, filename)
        filtered_list = []
        for qa in qa_list:
            if is_low_value_qa(qa) or is_structurally_empty_content(qa):
                logger.debug(f"[FILTER_QA] drop_question='{qa.get('题目', '')[:40]}' reason=low_value_or_struct_empty")
                continue
            qa["背景"] = background_content
            filtered_list.append(qa)
        # 动态上限：至少保证 2*min_pairs
        base_limit = MAX_QA_PER_SECTION if 'content' in item else MAX_QA_PER_TABLE
        limit = max(base_limit, 2 * min_pairs)
        if len(filtered_list) > limit:
            logger.info(
                f"[TRUNCATE] item_type={'section' if 'content' in item else 'table'} title={item.get('title') or item.get('table_title') or item.get('table_name', '')} original={len(filtered_list)} keep={limit}")
            filtered_list = filtered_list[:limit]
        prompt_tokens += prompt_tokens1
        completion_tokens += completion_tokens1
        return filtered_list, prompt_tokens, completion_tokens
    except Exception as e:
        logger.error(f"生成 QA 失败: {e}")
        return [], 0, 0


async def batch_generate_emergency_drill_qa(structured_rows: List[dict], filename: str, client: OpenAI,
                                            user_prompt: str, sop_id: int, db_client, lang: str = "zh") -> Tuple[List[Dict[str, Any]], int, int]:
    all_qa: List[Dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    # 预过滤后总项目数用于分配 min_pairs
    items = []
    if structured_rows and isinstance(structured_rows[0], dict) and 'content' in structured_rows[0]:
        for sec in structured_rows:
            if is_low_value_section(sec):
                logger.info(f"[SKIP] section title={sec.get('title', '')} reason=低价值部分")
                continue
            items.append(sec)
    elif structured_rows and isinstance(structured_rows[0], dict) and 'cells' in structured_rows[0]:
        for t in structured_rows:
            title = t.get('table_title') or t.get('table_name') or ''
            reasons = []
            if is_short_table(t): reasons.append('short')
            if is_low_value_table(t): reasons.append('low_value')
            if is_structurally_empty_table(t): reasons.append('struct_empty')
            if reasons:
                logger.info(f"[SKIP] table title={title} reason={'|'.join(reasons)}")
                continue
            items.append(t)
    else:
        logger.info("未识别的数据结构，无法生成问答对")
        return [], 0, 0
    total_items = len(items)
    if total_items == 0:
        logger.info("无有效项目")
        return [], 0, 0
    # 每项最低组数（取 ceil(TOTAL_ROUNDS/(2*total_items))）
    min_pairs_base = max(1, (TOTAL_ROUNDS + 2 * total_items - 1) // (2 * total_items))

    async def process_item(item: dict) -> Tuple[List[Dict[str, Any]], int, int]:
        async with semaphore:
            return await _add_background_and_generate_qa(item, filename, client, user_prompt, min_pairs_base,
                                                         total_items)

    tasks = [process_item(it) for it in items]
    results = await asyncio.gather(*tasks)
    for qa_list, pt, ct in results:
        all_qa.extend(qa_list)
        total_prompt_tokens += pt
        total_completion_tokens += ct

    db_client.update_percent_by_id(sop_id, "80%", lang=lang)
    # 补充逻辑
    if len(all_qa) < TOTAL_ROUNDS:
        logger.info(f"总题量 {len(all_qa)} < 目标 TOTAL_ROUNDS={TOTAL_ROUNDS}，开始补充生成")
        supplement_round = 0
        existing_titles = {q['题目'] for q in all_qa}
        while len(all_qa) < TOTAL_ROUNDS and supplement_round < MAX_SUPPLEMENT_ROUNDS:
            need = TOTAL_ROUNDS - len(all_qa)
            logger.info(f"补充轮次 {supplement_round + 1}/{MAX_SUPPLEMENT_ROUNDS} 尚需 {need} 题")
            round_existing_titles = set(existing_titles)

            async def process_supplement(item: dict) -> List[Dict[str, Any]]:
                async with semaphore:
                    return await generate_emergency_drill_supplement(
                        item,
                        filename,
                        round_existing_titles,
                        need,
                        client,
                        user_prompt,
                    )

            supplement_results = await asyncio.gather(*(process_supplement(item) for item in items))
            for extra in supplement_results:
                if len(all_qa) >= TOTAL_ROUNDS:
                    break
                unique_extra = [qa for qa in extra if qa['题目'] not in existing_titles]
                selected_extra = unique_extra[: max(0, TOTAL_ROUNDS - len(all_qa))]
                for qa in selected_extra:
                    qa['背景'] = qa.get('背景', '')
                all_qa.extend(selected_extra)
                existing_titles.update({e['题目'] for e in selected_extra})
            supplement_round += 1
        if len(all_qa) < TOTAL_ROUNDS:
            logger.info(f"补充后仍未达到 TOTAL_ROUNDS，当前 {len(all_qa)}")
        else:
            logger.info(f"补充后达到目标题量 {len(all_qa)}")
    logger.info("=" * 60)
    logger.info(f"总计生成题目: {len(all_qa)}")
    logger.info(f"Token使用: prompt={total_prompt_tokens}, completion={total_completion_tokens}")
    logger.info("=" * 60)
    return all_qa, total_prompt_tokens, total_completion_tokens


async def generate_emergency_drill_supplement(item: dict, filename: str, existing_titles: set, need: int,
                                              client: OpenAI, user_prompt: str) -> List[Dict[str, Any]]:
    """补充生成应急演练问答，保持问答/填空交替并接近 TOTAL_ROUNDS"""
    if need <= 0:
        return []
    # 使用 llm_prompts 中的函数生成提示词
    prompt = get_emergency_drill_supplement_prompt(item, filename, existing_titles, need, section_to_text, user_prompt, TOTAL_ROUNDS)
    try:
        llm_config = get_dataprep_llm_config()
        extra_body = get_llm_extra_body(llm_config.model)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=1800,
            extra_body=extra_body
        )
        resp_text = response.choices[0].message.content.strip()
        qa_list = parse_emergency_drill_qa_response(resp_text, item, filename)
        filtered = [q for q in qa_list if
                    q['题目'] not in existing_titles and not is_low_value_qa(q) and not is_structurally_empty_content(
                        q)]
        return filtered
    except Exception as e:
        logger.info(f"补充失败: {e}")
        return []
