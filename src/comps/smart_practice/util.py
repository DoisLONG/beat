# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import random
from datetime import datetime

from comps import CustomLogger

# 从 prompts 导入 get_prompt
from comps.smart_practice.prompts import get_prompt

logger = CustomLogger("smart-util")


# MODEL_USAGE_LUA = """
# if redis.call('exists', KEYS[1]) == 1 then
#   return redis.call('incr', KEYS[1])
# else
#   redis.call('set', KEYS[1], 1, 'EX', ARGV[1])
#   return 1
# end
# """
#
# def incr_model_minute_usage(redis_client, model: str, ttl_seconds: int = 120) -> tuple[int, str, str]:
#     """
#     返回(当前计数, 分钟Key, 可读分钟标签)
#     Key格式: model_usage:{model}:{YYYYMMDDHHMM}
#     """
#     now = datetime.utcnow()
#     minute_key_suffix = now.strftime("%Y%m%d%H%M")
#     minute_key = f"model_usage:{model}:{minute_key_suffix}"
#     count = redis_client.eval(MODEL_USAGE_LUA, 1, minute_key, ttl_seconds)
#     minute_label = now.strftime("%Y-%m-%d %H:%M")
#     return count, minute_key, minute_label
#
# LUA_MINUTE_TOKEN_SUM = """
# local t = redis.call('TIME')
# local sec = tonumber(t[1])
# local add = tonumber(ARGV[2])
# local exists = redis.call('EXISTS', KEYS[1])
# local new_total
# if exists == 1 then
#   new_total = redis.call('INCRBY', KEYS[1], add)
# else
#   redis.call('SET', KEYS[1], add, 'EX', ARGV[1])
#   new_total = add
# end
# return { t[1], KEYS[1], new_total }
# """
#
# _token_sum_sha = None
#
# def _ensure_token_sum_script(redis_client):
#     global _token_sum_sha
#     if not _token_sum_sha:
#         _token_sum_sha = redis_client.script_load(LUA_MINUTE_TOKEN_SUM)
#
# def add_minute_total_tokens(redis_client, model_name: str, total_tokens: int, ttl_seconds: int = 7200):
#     """
#     简单分钟级总 token 累加。
#     Args:
#         redis_client: Redis 连接
#         model_name: 模型名
#         total_tokens: 本次调用总 token
#         ttl_seconds: 分钟桶过期时间（默认 2h）
#     Returns:
#         dict: {minute_label, key, minute_total}
#     """
#     _ensure_token_sum_script(redis_client)
#     try:
#         add = int(total_tokens)
#     except Exception:
#         logger.warning("total_tokens 非数字，记 0")
#         add = 0
#     try:
#         prefix = f"token_usage:{model_name}:"
#         resp = redis_client.evalsha(_token_sum_sha, 0, ttl_seconds, prefix, add)
#         sec = int(resp[0])
#         key = resp[1]
#         minute_total = int(resp[2])
#         minute_label = datetime.utcfromtimestamp(sec).strftime("%Y-%m-%d %H:%M")
#         logger.info(f"[token_usage] model={model_name} minute={minute_label} +{add} agg_total={minute_total}")
#         return {"minute_label": minute_label, "key": key, "minute_total": minute_total}
#     except Exception as e:
#         logger.warning(f"分钟 token 统计失败: {e}")
#         return {"minute_label": "", "key": "", "minute_total": 0}
#


def format_wrong_question_natural(wrong_question: dict) -> str:
    """
    将单个错题对象转换为自然语言描述，便于嵌入提示词。

    wrong_question 字段示例：
    {
        "serial_number": 3,
        "question": "在作业前的步骤1，作业事项是____?",
        "answer": "佩戴劳动防护用品",
        "user_input_answer": "未佩戴防护用品",
        "row_ids": "4"
    }

    返回：
    - 自然语言文本
    """
    serial = wrong_question.get("serial_number", "")
    question_text = wrong_question.get("question", "")
    answer_text = wrong_question.get("answer", "")
    user_input = wrong_question.get("user_input_answer", "")
    # 题目分数、题目位置
    score = wrong_question.get("score", "")
    filename = wrong_question.get("filename", "")
    row_id = wrong_question.get("row_id", "")
    position = wrong_question.get("position", "")

    return (
        f"第{serial}题：{question_text}\n"
        f"正确答案：{answer_text}\n"
        f"用户回答：{user_input}\n"
        f"题目分数：{score}\n"
        f"题目位置：文件： {filename}，行号： {row_id}，题目单元格位置： {position}"
    )


def format_wrong_question_natural_continue(wrong_question: dict) -> str:
    """
    将单个错题对象转换为自然语言描述，便于嵌入提示词。

    wrong_question 字段示例：
    {
        "serial_number": 3,
        "question": "在作业前的步骤1，作业事项是____?",
        "answer": "佩戴劳动防护用品",
        "user_input_answer": "未佩戴防护用品",
        "row_ids": "4"
    }

    返回：
    - 自然语言文本
    """
    serial = wrong_question.get("serial_number", "")
    question_text = wrong_question.get("question", "")
    answer_text = wrong_question.get("answer", "")
    user_input = wrong_question.get("user_input_answer", "")
    content = wrong_question.get("content", "")

    return (
        f"第{serial}题：{question_text}\n"
        f"正确答案：{answer_text}\n"
        f"用户回答：{user_input}\n"
        f"问题背景：{content}\n"
    )


async def random_key_from_map(my_map, exclude_keys=None):
    """
    从字典 my_map 随机取一个 key，可排除 exclude_keys 列表中的 key
    :param my_map: dict, key -> value
    :param exclude_keys: list，需要排除的 key 列表，可为空或 None
    :return: 随机选出的 key，或者 None（如果没有可选 key）
    """
    if exclude_keys is None:
        exclude_keys = []

    # 剩余可选 key
    available_keys = [k for k in my_map.keys() if k not in exclude_keys]

    if not available_keys:
        return None
    return random.choice(available_keys)


from typing import List


async def get_system_prompt(important_param: dict, fail_question_list: List[dict], total_time: int,
                            question_bank: dict,session: dict) -> str:
    """
    根据当前阶段选择提示词模板：
    - current_time == 1 ：开始阶段
    - 1 < current_time < total_time ：中间答题阶段
    - current_time == total_time ：总结阶段
    - current_time > total_time ：错题解析阶段
    """
    current_time = important_param.get("current_time", 0)
    last_q = important_param.get("last_question", {})
    next_question = important_param.get("next_question", "")
    back_content = important_param.get("content", "")
    if current_time == 1:
        # 开始阶段
        return await build_prompt_start(next_question, current_time, session)
    elif 1 < current_time <= total_time:
        # 中间答题阶段
        return await build_prompt_middle(last_q, next_question, current_time, current_time - 1, session, back_content)
    elif current_time == total_time + 1:
        # 总结阶段
        wrong_questions = "\n".join([format_wrong_question_natural(q) for q in fail_question_list])
        # 获取总分数：只统计实际已判题的日志，避免把题库中的未作答题或追问题混入
        answer_logs = session.get("answer_logs", [])
        sum_score = round(sum(float(log.get("score", 0.0) or 0.0) for log in answer_logs), 2)
        return await build_prompt_summary(last_q, total_time, fail_question_list, wrong_questions, sum_score,
                                          current_time - 1, session)
    else:
        # 追问阶段
        return await build_prompt_wrong_analysis(
            "\n".join([format_wrong_question_natural_continue(q) for q in fail_question_list]),
            session,
            user_follow_up=last_q.get('user_input_answer'))


async def build_prompt_start(next_question: str, current_time: int, session: dict) -> str:
    return get_prompt(
        "BUILD_START",
        language=session.get("language"),
        next_question=next_question,
        current_time=current_time
    )


async def build_prompt_middle(last_q: dict, next_question: str, current_time: int, last_time: int, session: dict, back_content: str) -> str:
    """
    last_q 中包含：
    - question：题目
    - answer：标准答案
    - user_input_answer：用户答案
    - llm_reason：对错判定理由（可选）
    - is_correct：True/False
    """
    # is_correct_str = "正确" if last_q.get("is_correct", False) else "错误"
    is_correct_str = last_q.get("is_correct_str", "错误")
    reason = last_q.get("llm_reason", "")

    return get_prompt(
        "BUILD_MIDDLE",
        language=session.get("language"),
        last_time=last_time,
        back_content=back_content,
        last_question=last_q.get('question', ''),
        last_answer=last_q.get('answer', ''),
        last_user_input_answer=last_q.get('user_input_answer', ''),
        is_correct_str=is_correct_str,
        reason=reason,
        last_score=last_q.get('score', ''),
        current_time=current_time,
        next_question=next_question
    )


async def build_prompt_summary(last_q: dict, total_time_local: int, fail_question_list: list,
                               wrong_questions: str, sum_score: int, last_time: int, session: dict) -> str:
    is_correct_str = last_q.get("is_correct_str", "错误")
    reason = last_q.get("llm_reason", "")
    wrong_text = wrong_questions if len(fail_question_list) != 0 else '无'

    return get_prompt(
        "BUILD_SUMMARY",
        language=session.get("language"),
        last_time=last_time,
        last_question=last_q.get('question', ''),
        last_answer=last_q.get('answer', ''),
        last_user_input_answer=last_q.get('user_input_answer', ''),
        is_correct_str=is_correct_str,
        reason=reason,
        last_score=last_q.get('score', ''),
        total_time_local=total_time_local,
        sum_score=sum_score,
        wrong_text=wrong_text
    )


async def build_prompt_wrong_analysis(fail_question_str: str, session: dict, user_follow_up: str = "") -> str:
    if not fail_question_str or not fail_question_str.strip():
        return "当前没有错题，无需解析。"

    return get_prompt(
        "BUILD_WRONG_ANALYSIS",
        language=session.get("language"),
        fail_question_str=fail_question_str,
        user_follow_up=user_follow_up if user_follow_up else "（空）"
    )
