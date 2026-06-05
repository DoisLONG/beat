# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import math
import os
import re
from collections import defaultdict

from openai import OpenAI

from comps import CustomLogger
from comps.dataprep.config import (
    DATAPREP_QA_CONCURRENCY_LIMIT,
    get_dataprep_llm_config,
    get_llm_extra_body,
)
from comps.dataprep.service.content_agent import get_client
from comps.dataprep.prompt.llm_prompts import get_risk_qa_prompt, get_risk_supplement_prompt

logger = CustomLogger("prepare_genera_util", "INFO")

TOTAL_ROUNDS = int(os.getenv("TOTAL_ROUNDS", 10))
CONCURRENCY_LIMIT = DATAPREP_QA_CONCURRENCY_LIMIT
# 定义常量
RISK_QA_FIELDS = [
    "事故案例收集",
    "风险因素描述",
    "风险控制措施-消除",
    "风险控制措施-消减或替代",
    "风险控制措施-工程防呆",
    "风险控制措施-管理控制",
    "风险控制措施-个人防护",
    "标准作业卡名称",
    "是否落实",
]
CONTROL_LEVELS = ["消除", "消减或替代", "工程防呆", "管理控制", "个人防护"]
INVALID_VALUES = ["", "/", None]

def merge_risk_json(data):
    # 第一级：按“序号 + 标准作业卡名称”聚合
    grouped_by_card = defaultdict(list)
    for item in data:
        key = (item["序号"], item["标准作业卡名称"])
        grouped_by_card[key].append(item)

    result = []
    for (seq, card_name), group in grouped_by_card.items():
        # 第二级：按事故案例分组
        grouped_by_accident = defaultdict(list)
        for g in group:
            grouped_by_accident[g["事故案例收集"]].append(g)

        accident_list = []
        for accident, items in grouped_by_accident.items():
            risk_desc = items[0]["风险因素描述"]
            controls = []
            for i in items:
                # 控制层级直接取“风险控制措施”的首行
                control_type = i["风险控制措施"].split("\n", 1)[0].strip()
                control_detail = i["风险控制措施"].split("\n", 1)[1].strip() if "\n" in i["风险控制措施"] else ""
                controls.append({
                    "控制层级": control_type,
                    "风险控制措施": control_detail,
                    "是否落实": i["是否落实"],
                    "行号": i["行号"]
                })
            accident_list.append({
                "事故案例收集": accident,
                "风险因素描述": risk_desc,
                "控制措施清单": controls
            })

        result.append({
            "序号": seq,
            "标准作业卡名称": card_name,
            "事故风险识别清单": accident_list
        })
    return result


# 压缩文本函数：将长描述分句，只保留核心信息
def compress_text(text: str, max_sentences: int = 5) -> str:
    import re
    sentences = re.split(r'[\n。；]', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    # 保留前 max_sentences + 后 max_sentences
    if len(sentences) <= 2 * max_sentences:
        return "\n".join(sentences)
    else:
        return "\n".join(sentences[:max_sentences] + sentences[-max_sentences:])


# 分批生成内容（保证每批 token 可控）
def split_batches(row: dict, batch_size: int = 2000) -> list:
    """
    batch_size: 估算字符长度，每 batch 包含约 batch_size 字符
    """
    compressed_fields = []
    # 顶层字段
    for field in ["标准作业卡名称", "序号"]:
        value = row.get(field, "")
        if value in INVALID_VALUES or not value:
            continue
        compressed_fields.append(f"{field}: {compress_text(str(value))}")

    # 事故风险识别清单里的字段
    for accident in row.get("事故风险识别清单", []):
        for field in ["事故案例收集", "风险因素描述"]:
            value = accident.get(field, "")
            if value in INVALID_VALUES or not value:
                continue
            compressed_fields.append(f"{field}: {compress_text(str(value))}")
        # 控制措施清单是 list
        for control in accident.get("控制措施清单", []):
            for field in ["控制层级", "风险控制措施", "是否落实"]:
                value = control.get(field, "")
                if value in INVALID_VALUES or not value:
                    continue
                compressed_fields.append(f"{field}: {compress_text(str(value))}")

    # 拼接成单条长文本
    full_text = "\n".join(compressed_fields)

    # 按 batch_size 分割
    batches = []
    chars = len(full_text)
    n_batches = math.ceil(chars / batch_size)
    for i in range(n_batches):
        start = i * batch_size
        end = (i + 1) * batch_size
        batch_text = full_text[start:end]
        batches.append(batch_text)

    return batches


# =================== 风险识别文件 问答对生成 Prompt ===================
def make_multi_qa_prompt_risk(row, filename: str, user_prompt: str = "", min_pairs: int = 1, total_rows: int = 1) -> list:
    """增加 total_rows 参数，用于在 Prompt 中给出全局目标 TOTAL_ROUNDS 说明"""
    name = os.path.splitext(os.path.basename(filename))[0]
    batches = split_batches(row, batch_size=2000)
    prompts = []
    for batch_idx, batch_text in enumerate(batches):
        prompt = get_risk_qa_prompt(
            batch_text=batch_text,
            filename=filename,
            batch_idx=batch_idx,
            total_batches=len(batches),
            user_prompt=user_prompt,
            min_pairs=min_pairs,
            total_rows=total_rows,
            TOTAL_ROUNDS=TOTAL_ROUNDS
        )
        prompts.append(prompt)
    return prompts


def parse_multi_risk_qa_response(text: str, row: dict, filename: str) -> list:
    """
    解析 LLM 返回的问答对
    修正版：
    - 不按字段去重，每道题都保留
    - 字段匹配宽松，支持“风险控制措施-XXX”
    - 问答题按行解析答案
    - 填空题直接取模型输出
    """
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # 正则匹配题目块
    pattern = r"题目[:：](.*?)\n题型[:：](.*?)\n答案[:：](.*?)\n难度因子[:：](.*?)\n来源字段[:：](.*?)(?=\n题目|$)"
    matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)

    results = []
    for idx, (ques, qtype_in_ans, ans, diff, field) in enumerate(matches):
        ques = ques.strip()
        ans = ans.strip()
        qtype = qtype_in_ans.strip()
        diff = diff.strip()
        field = field.strip()

        ques = f"【{os.path.splitext(os.path.basename(filename))[0]}】{ques}"
        # 宽松字段匹配
        if not field:
            field = "未知字段"

        # 问答题处理
        if qtype == "问答题":
            # 按行解析答案，不限制数量
            scoring_points = [p.strip() for p in re.split(r'[\n;；]', ans) if p.strip()]
            # 去重
            unique_points = []
            seen = set()
            for p in scoring_points:
                if p not in seen:
                    seen.add(p)
                    unique_points.append(p)
            answer_data = str(unique_points)

        else:  # 填空题
            answer_data = ans

        # 难度因子
        try:
            diff_value = float(re.findall(r"[0-9.]+", diff)[0])
            diff_value = max(0.0, min(1.0, diff_value))
        except:
            diff_value = 0.5

        # 定位信息
        position = f"{row.get('标准作业卡名称', '')}-{row.get('序号', '')}-{field}"
        qa_item = {
            "行号": row.get("序号", ""),
            "题目": ques,
            "题型": qtype,
            "答案": answer_data,
            "难度因子": diff_value,
            "定位": position,
            "内容": row_to_text(row),
            "来源字段": field
        }

        results.append(qa_item)

    return results


def row_to_text(row: dict) -> str:
    lines = []
    for k, v in row.items():
        if isinstance(v, list):
            for idx, item in enumerate(v):
                lines.append(f"{k}[{idx+1}]: {row_to_text(item) if isinstance(item, dict) else str(item)}")
        elif isinstance(v, dict):
            lines.append(f"{k}: {row_to_text(v)}")
        else:
            lines.append(f"{k}: {str(v)}")
    return "\n".join(lines)


MAX_SUPPLEMENT_ROUNDS = 3

def generate_risk_supplement(row: dict, filename: str, existing_questions: set, need_questions: int, client: OpenAI, user_prompt: str = "") -> list:
    """补充生成风险识别问答，确保总题量达到最低 TOTAL_ROUNDS。
    need_questions 为剩余需要的单题数量（含问答+填空总数）。
    仍要求问答与填空数量相等并交替；若素材不足则输出可配对的最大数量。"""
    if need_questions <= 0:
        return []
    # 计算需要的最少配对组数（每组2题）
    need_pairs = max(1, math.ceil(need_questions / 2))
    name = os.path.splitext(os.path.basename(filename))[0]
    base_text = row_to_text(row)
    prompt = get_risk_supplement_prompt(
        filename=filename,
        row_text=base_text,
        existing_questions_count=len(existing_questions),
        existing_questions_text="\n".join(sorted(existing_questions)),
        need_questions=need_questions,
        user_prompt=user_prompt,
        TOTAL_ROUNDS=TOTAL_ROUNDS
    )
    llm_config = get_dataprep_llm_config()
    model_name = llm_config.model
    extra_body = get_llm_extra_body(model_name)
    try:
        response = asyncio.run(asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=2500,
            extra_body=extra_body
        ))
        text = response.choices[0].message.content
        new_list = parse_multi_risk_qa_response(text, row, filename)
        # 去重过滤
        filtered = [q for q in new_list if q.get("题目") not in existing_questions]
        # 简单交替与平衡
        qa_q = [x for x in filtered if x.get("题型") == "问答题"]
        qa_f = [x for x in filtered if x.get("题型") == "填空题"]
        n = min(len(qa_q), len(qa_f))
        if n == 0:
            return []
        merged = []
        for i in range(n):
            merged.append(qa_q[i]); merged.append(qa_f[i])
        return merged
    except Exception as e:
        logger.info(f"补充生成失败: {e}")
        return []

async def batch_generate_risk_qa(structured_rows: list, filename: str, client: OpenAI, user_prompt: str,sop_id:int,db_client, lang: str = "zh") -> tuple:
    row_data_list = merge_risk_json(structured_rows)
    try:
        min_pairs = max(1, math.ceil((TOTAL_ROUNDS if isinstance(TOTAL_ROUNDS, int) else 0) / max(1, len(row_data_list))))
    except Exception:
        min_pairs = 1
    all_qa = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    baseline_per_row = 4
    target_total = max(TOTAL_ROUNDS if isinstance(TOTAL_ROUNDS, int) else 0, len(row_data_list) * baseline_per_row)
    logger.info(f"目标总题数(>=TOTAL_ROUNDS)：{target_total} | 每行最低组数M={min_pairs}")
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def process_row(row: dict) -> tuple[list, int, int]:
        logger.info(f"  处理序号: {row['序号']}")
        risk_prompts = make_multi_qa_prompt_risk(row, filename, user_prompt, min_pairs, total_rows=len(row_data_list))
        llm_config = get_dataprep_llm_config()
        model_name = llm_config.model
        extra_body = get_llm_extra_body(model_name)
        row_all_qa = []
        row_prompt_tokens = 0
        row_completion_tokens = 0
        for risk_prompt in risk_prompts:
            try:
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=model_name,
                    messages=[{"role": "user", "content": risk_prompt}],
                    temperature=0.2,
                    max_tokens=4000,
                    extra_body=extra_body
                )
                if hasattr(response, 'usage') and response.usage:
                    row_prompt_tokens += response.usage.prompt_tokens
                    row_completion_tokens += response.usage.completion_tokens
                resp_text = response.choices[0].message.content
                qa_list = parse_multi_risk_qa_response(resp_text, row, filename)
                row_all_qa.extend(qa_list)
                logger.info(f"  ✓ 当前序号生成了 {len(qa_list)} 道题目")
            except Exception as e:
                logger.info(f"  ✗ 处理失败: {str(e)}")
                continue
        return row_all_qa, row_prompt_tokens, row_completion_tokens

    async def run_row(row: dict) -> tuple[list, int, int]:
        async with semaphore:
            return await process_row(row)

    results = await asyncio.gather(*(run_row(row) for row in row_data_list))
    for row_all_qa, row_prompt_tokens, row_completion_tokens in results:
        all_qa.extend(row_all_qa)
        total_prompt_tokens += row_prompt_tokens
        total_completion_tokens += row_completion_tokens

    db_client.update_percent_by_id(sop_id, "80%", lang=lang)
    if len(all_qa) < TOTAL_ROUNDS:
        logger.info(f"总题量 {len(all_qa)} 低于期望 TOTAL_ROUNDS={TOTAL_ROUNDS}")
    else:
        logger.info(f"总题量 {len(all_qa)} 已满足或超过 TOTAL_ROUNDS={TOTAL_ROUNDS}")
    logger.info(f"\n{'=' * 50}")
    logger.info(f"总计生成: {len(all_qa)} 道题目 (目标 {target_total})")
    logger.info(f"Token 使用: prompt={total_prompt_tokens}, completion={total_completion_tokens}")
    logger.info(f"{'=' * 50}\n")
    # 若不足 TOTAL_ROUNDS 进行补充
    if len(all_qa) < TOTAL_ROUNDS:
        existing_titles = {q['题目'] for q in all_qa}
        supplement_round = 0
        while len(all_qa) < TOTAL_ROUNDS and supplement_round < MAX_SUPPLEMENT_ROUNDS:
            supplement_round += 1
            need = TOTAL_ROUNDS - len(all_qa)
            logger.info(f"补充轮次 {supplement_round}/{MAX_SUPPLEMENT_ROUNDS}，尚缺 {need} 题")
            for row in row_data_list:
                if len(all_qa) >= TOTAL_ROUNDS:
                    break
                extra = generate_risk_supplement(row, filename, existing_titles, TOTAL_ROUNDS - len(all_qa), client, user_prompt)
                for q in extra:
                    if q['题目'] not in existing_titles:
                        all_qa.append(q)
                        existing_titles.add(q['题目'])
            logger.info(f"补充后题量: {len(all_qa)}")
    if len(all_qa) < TOTAL_ROUNDS:
        logger.info(f"总题量 {len(all_qa)} 仍低于期望 TOTAL_ROUNDS={TOTAL_ROUNDS}")
    else:
        logger.info(f"总题量 {len(all_qa)} 已满足或超过 TOTAL_ROUNDS={TOTAL_ROUNDS}")
    logger.info(f"补充生成完成\n")
    return all_qa, total_prompt_tokens, total_completion_tokens
