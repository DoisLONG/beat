# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import os
import re
import time
import traceback
from typing import Any, Optional, List, Dict
import random
from fastapi import HTTPException
from langchain_core.documents import Document
from comps import CustomLogger
from comps.smart_practice.config import MILVUS_COLLECTION_NAME, MILVUS_URI, openai_api_key, llm_endpoint, model_name, \
    total_time, SESSION_REDIS_PREFIX, TIME_REDIS_PREFIX, MYSQL_CONFIG, LLM_EXTRA_BODY, TOP_PUSH_URL, \
    get_llm_extra_body, get_cached_config_resolver, ModelConfigScope
from comps.chathistory.user_logs_mongo_store import AnswerLogDocumentStore
from datetime import datetime
from langchain_milvus import Milvus
from openai import AsyncOpenAI

from comps.smart_practice.db_client import MySQLClient
from comps.smart_practice.models.exam_record import ExamRecordCreate
from comps.smart_practice.util import random_key_from_map, get_system_prompt, format_wrong_question_natural
from comps.smart_practice.service.dfxw_service import submit_exam_result
import aiohttp

# 从 prompts 导入 PROMPTS 和 get_prompt
from comps.smart_practice.prompts import get_prompt, get_decision_text

# ==============================
# 多语种路由（data_lang）
# ==============================
SUPPORTED_LANGS = {"zh", "en", "th"}
DEFAULT_LANG = "zh"


def _resolve_data_lang(lang) -> str:
    """归一化 data_lang，非法或缺失统一降级为 zh。

    `data_lang` 控制业务数据路由（MySQL 表名、Milvus 集合名、考试记录写入）。
    与 prompt_lang（session["language"]）完全独立，禁止互相覆盖。
    """
    if not lang:
        return DEFAULT_LANG
    lang = str(lang).lower()
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def _get_collection_name(data_lang) -> str:
    """按 data_lang 解析 Milvus 集合名。

    与 dataprep 写入 QA 向量集合的命名规则保持一致：
      - zh -> MILVUS_COLLECTION_NAME
      - en -> MILVUS_COLLECTION_NAME_en
      - th -> MILVUS_COLLECTION_NAME_th
    """
    data_lang = _resolve_data_lang(data_lang)
    if data_lang == DEFAULT_LANG:
        return MILVUS_COLLECTION_NAME
    return f"{MILVUS_COLLECTION_NAME}_{data_lang}"


def _get_session_data_lang(session: dict) -> str:
    """从 session 安全读取 data_lang，缺失或非法降级为 zh。

    重要：不要 fallback 到 session["language"]，那是 prompt_lang。
    """
    if not session:
        return DEFAULT_LANG
    return _resolve_data_lang(session.get("data_lang"))


def _get_session_prompt_lang(session: dict):
    """从 session 安全读取 prompt_lang（smart 原 session["language"]）。"""
    if not session:
        return None
    return session.get("language")

DECISION_MAP = {
    "0": "错误",
    "1": "部分正确",
    "2": "正确",
}

FILE_TYPE_CATEGORY_MAP = {
    "sop": "1",
    "operation": "2",
    "risk": "3",
    "emergency_drill": "4",
}

EXAM_CATEGORY_MAP = {
    "sop": "SOP",
    "operation": "操作规程",
    "risk": "风险识别",
    "emergency_drill": "应急演练",
}

logger = CustomLogger("smart_practice_core", os.getenv("LOG_LEVEL", "INFO"))


def get_actual_total_time_by_exam_type(session, session_id, embeddings):
    """
    根据考试类型，获取对应的题库中的总题目数
    """
    data_lang = _get_session_data_lang(session)
    expr = f'position_id == "{session["position_id"]}"' if session[
                                                             "exam_type"] == "mix" else f'sop_id == {session["sop_id"]} '
    retriever_response = similarity_search_with_score(
        query=session_id,
        embedding_function=embeddings,
        collection_name=_get_collection_name(data_lang),
        k=100,
        expr=expr
    )
    return total_time if total_time <= len(retriever_response) else len(retriever_response)


def load_fill_in_blank(session: dict, session_id: str, number: int, embeddings) -> dict:
    """加载题库（如果已存在则复用）"""
    if session["question_bank"]:
        return session["question_bank"]
    data_lang = _get_session_data_lang(session)
    exam_type = session["exam_type"]
    # 准备循环调用列表
    function_call_params = {}
    if exam_type=="mix":
        # 如果是混合出题，那边为了加强随机出题的效果，mysql数据库中获取这个岗位下的全部sop列表
        function_call_params = allocate_questions_to_sops(position_id=session['position_id'], number=number, data_lang=data_lang)
    else:
        function_call_params[session["sop_id"]] = number
    return retrieve_questions_by_sops(session_id=session_id,sop_allocations=function_call_params,question_type="填空题",embeddings=embeddings, data_lang=data_lang)

def select_questions(fill_in_list, short_answer_list, total_count=10, fill_in_target=5):
    # 题目总数判断
    if len(fill_in_list) + len(short_answer_list) < total_count:
        raise ValueError(f"题库总题数不足{total_count}题")

    # 先取填空题
    fill_in_selected = fill_in_list[:fill_in_target]
    need_fill = fill_in_target - len(fill_in_selected)
    # 不足5题用问答补
    if need_fill > 0:
        short_answer_selected = short_answer_list[:need_fill]
    else:
        short_answer_selected = []

    # 剩余问答题
    remain_short_answer = short_answer_list[len(short_answer_selected):]
    # 再补问答题到10题
    total_selected = fill_in_selected + short_answer_selected
    need_more = total_count - len(total_selected)
    more_short_answer = remain_short_answer[:need_more]
    total_selected += more_short_answer

    # 如果问答题还不够，再用填空题补
    if len(total_selected) < total_count:
        remain_fill_in = fill_in_list[len(fill_in_selected):]
        total_selected += remain_fill_in[:total_count - len(total_selected)]

    return total_selected

def load_short_answer_bank(session: dict, session_id: str, number: int,embeddings) -> dict:
    """加载题库（如果已存在则复用）"""
    if session["question_bank"]:
        return session["question_bank"]
    data_lang = _get_session_data_lang(session)
    exam_type = session["exam_type"]
    # 准备循环调用列表
    function_call_params = {}
    if exam_type == "mix":
        # 如果是混合出题，那边为了加强随机出题的效果，mysql数据库中获取这个岗位下的全部sop列表
        function_call_params = allocate_questions_to_sops(position_id=session['position_id'], number=number, data_lang=data_lang)
    else:
        function_call_params[session["sop_id"]] = number
    return retrieve_questions_by_sops(session_id=session_id,sop_allocations=function_call_params,question_type="问答题",embeddings=embeddings, data_lang=data_lang)


async def save_user_answer_log(user_id: str, exams_id: str, question: str, standard_answer: str, user_answer: str,
                               score: float, decision_result: str,excel_row=str,
                               question_type=str, exam_time=str,
                               data_lang: Optional[str] = None,
                               prompt_lang: Optional[str] = None):
    log_data = {
        "user_id": user_id,
        "exams_id": exams_id,
        "question": question,
        "question_type": question_type,
        "standard_answer": standard_answer,
        "user_answer": user_answer,
        "answer_time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "exam_time": exam_time,
        "score": score,
        "decision_result": decision_result,
        "excel_row": excel_row,
        "data_lang": _resolve_data_lang(data_lang),
        "prompt_lang": prompt_lang,
    }
    store = AnswerLogDocumentStore(user_id)
    await store.initialize_storage()
    await store.save_user_log(log_data)
    logger.info("单论答题日志写入成功")


async def save_full_process_log(user_id, exams_id, answer_logs, start_time, end_time,
                                data_lang: Optional[str] = None,
                                prompt_lang: Optional[str] = None):
    log_data = {
        "user_id": user_id,
        "exams_id": exams_id,
        "logs": answer_logs,  # 全流程日志列表
        "start_time": start_time,
        "end_time": end_time,
        "data_lang": _resolve_data_lang(data_lang),
        "prompt_lang": prompt_lang,
    }
    store = AnswerLogDocumentStore(user_id)
    await store.initialize_storage()
    await store.save_user_log(log_data)
    logger.info("整体答题日志写入成功")


def similarity_search_with_score(query: str,
                                 embedding_function: Any,
                                 collection_name: str,
                                 k: int = 4,
                                 expr: Optional[str] = None,
                                 timeout: Optional[float] = None,
                                 db_name: Optional[str] = None) -> List[Any]:
    """
    与 similarity_search 类似，但返回的是 (文档, 相似度分数) 的元组列表。

    Returns:
        List of (doc, score) tuples
    """
    try:
        client = Milvus(
            embedding_function=embedding_function,
            collection_name=collection_name,
            connection_args={
                "uri": MILVUS_URI,
                "db_name": "default",
            }
        )
        logger.debug(f"Executing similarity_search_with_score on {collection_name}")
        return client.similarity_search_with_score(query=query, k=k, expr=expr, timeout=timeout)
    except Exception as e:
        logger.error(f"Milvus similarity_search_with_score failed,search:{traceback.format_exc()}")
        return []


# ========== 判题逻辑 ==========
async def judge_answer_with_llm(question_text: str, standard_answer: str, user_answer: str, question_background: str,
                                question_type: str, question_score,session) -> dict:
    """调用大模型判定答案是否正确"""
    start_time = time.time()  # 记录开始时间
    prompt = ""
    if question_type == "填空题":
        prompt = get_prompt(
            "JUDGE_FILL_IN_BLANK",
            language=session.get("language"),
            question_score=question_score,
            question_text=question_text,
            standard_answer=standard_answer,
            user_answer=user_answer
        )
    elif question_type == "问答题":
        prompt = get_prompt(
            "JUDGE_SHORT_ANSWER",
            language=session.get("language"),
            question_text=question_text,
            standard_answer=standard_answer,
            user_answer=user_answer,
            question_score=question_score
        )

    # Resolve LLM config at runtime
    resolver = get_cached_config_resolver()
    resolved_llm = resolver.resolve(ModelConfigScope.SMART_PRACTICE_LLM)

    llm_client = AsyncOpenAI(
        api_key=resolved_llm.api_key.get_secret_value() if resolved_llm.api_key else "",
        base_url=resolved_llm.base_url,
    )
    token_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }

    try:
        response = await llm_client.chat.completions.create(
            model=resolved_llm.model,
            messages=[{"role": "user", "content": prompt}],
            extra_body=get_llm_extra_body(resolved_llm.model),
            temperature=0.1
        )

        if hasattr(response, 'usage') and response.usage:
            token_usage["prompt_tokens"] = response.usage.prompt_tokens
            token_usage["completion_tokens"] = response.usage.completion_tokens
            token_usage["total_tokens"] = response.usage.total_tokens
        logger.info(f"LLM 判题使用token: {token_usage}")

        text = response.choices[0].message.content.strip()
        logger.info(f"judge_answer_with_llm 调用结果: {text}")
        # 去除可能存在的 markdown 代码块标记
        if text.startswith("```"):
            text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE | re.IGNORECASE).strip()

        try:
            # 直接解析 JSON
            result = json.loads(text)
            elapsed_time = time.time() - start_time
            logger.info(f"judge_answer_with_llm 调用耗时: {elapsed_time:.4f} 秒")
            return result, token_usage
        except json.JSONDecodeError:
            # 解析失败时的正则兜底
            match = re.search(r"\{.*\}", text, re.DOTALL)
            elapsed_time = time.time() - start_time
            logger.info(f"judge_answer_with_llm 调用耗时: {elapsed_time:.4f} 秒")
            return json.loads(match.group(0)) if match else {"is_correct": False, "reason": "解析失败"}, token_usage
    except Exception as e:
        elapsed_time = time.time() - start_time  # 计算耗时
        logger.info(f"judge_answer_with_llm 调用耗时: {elapsed_time:.4f} 秒")
        return {"is_correct": False, "reason": f"判题调用失败：{str(e)}"}


def dict_to_document(doc_dict: dict) -> Document:
    """将存储的Document字典转为Document实例（带容错）"""
    # 字段缺失时用默认值（空字符串/空字典），避免报错
    page_content = doc_dict.get("page_content", "")
    metadata = doc_dict.get("metadata", {})
    return Document(page_content=page_content, metadata=metadata)


# ========== 出题逻辑 ==========
async def prepare_question(messages: List[dict[str, Any]], session_id: str, embeddings, redis_client,
                           add_mode_min_ratio: float = 0.6, add_mode_max_questions: int = 5):
    """准备下一题，返回 system_prompt, user_input, current_question_pk, current_time, flag"""
    session = get_redis_session(session_id, redis_client=redis_client)
    new_total_time = session["new_total_time"]
    question_bank = session["question_bank"]
    current_time = session["current_time"]
    user_input = messages[-1].get("content")

    # # 优先随机填空题，填空题出完后再随机问答题
    fill_in_blank_questions = {k: v for k, v in question_bank.items() if v.metadata.get("question_type") == "填空题"}
    short_answer_questions = {k: v for k, v in question_bank.items() if v.metadata.get("question_type") == "问答题"}

    if len(session["history_question_pks"]) < len(fill_in_blank_questions):
        # 随机填空题
        current_pk = await random_key_from_map(fill_in_blank_questions, session["history_question_pks"])
    else:
        # 填空题出完后随机问答题
        current_pk = await random_key_from_map(short_answer_questions, session["history_question_pks"])

    current_doc = question_bank.get(current_pk)

    important_param = {
        "last_question": {
            "excel_name": "",
            "row_number": "",
            "content": "",
            "question": "",
            "answer": "",
            "user_input_answer": "",
        },
        "current_time": current_time,
        "next_question": ""
    }
    flag = False
    n = new_total_time  # 题目数
    total_score = 100  # 总分
    score_common = total_score // n
    score_last = total_score - score_common * (n - 1)

    if current_time == 1:
        # 第一次交互：直接出题
        session["start_time"] = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        important_param["next_question"] = current_doc.page_content
    elif current_time <= new_total_time + 1:
        # 通过追问题目列表判断是否处于追问模式
        is_addition_mode = len(session.get("additional_question", [])) > 0
        # 处理中交互
        pre_pk = session["history_question_pks"][-1]
        pre_doc = question_bank.get(pre_pk)
        important_param["last_question"].update({
            "excel_name": pre_doc.metadata.get("filename"),
            "row_number": pre_doc.metadata.get("excel_row"),
            "content": pre_doc.metadata.get("content"),
            "question": pre_doc.page_content,
            "answer": pre_doc.metadata.get("answer"),
            "user_input_answer": user_input,
        })

        # 判题
        standard_answer = pre_doc.metadata.get("answer", "").strip()
        question_type = pre_doc.metadata.get("question_type", "填空题")
        user_answer = user_input.strip()

        llm_result = {}
        token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        if current_time != new_total_time + 1:
            max_score = score_common
        else:
            max_score = score_last

        if user_answer != standard_answer:
            llm_result, token_usage = await judge_answer_with_llm(pre_doc.page_content, standard_answer, user_answer,
                                                                  pre_doc.metadata.get("content", ""), question_type,
                                                                  max_score,session)
            # add_minute_total_tokens(redis_client,model_name,token_usage["total_tokens"])

            score = round(float(llm_result.get("score", 0.0)), 2)
            max_score = float(max_score)
            decision = "0" if score == 0.0 else ("1" if score < max_score else "2")
            flag = score != max_score
        else:
            score = float(max_score)
            decision = "2"

        # 累计token使用量到会话中
        if "token_usage" not in session:
            session["token_usage"] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        session["token_usage"]["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
        session["token_usage"]["completion_tokens"] += token_usage.get("completion_tokens", 0)
        session["token_usage"]["total_tokens"] += token_usage.get("total_tokens", 0)
        important_param["next_question"] = current_doc.page_content if current_doc else ""  # 位置要变
        if flag:
            # 回答错误，记录错题，进入追问模式
            session["fail_question_list"].append({
                "serial_number": current_time - 1,
                "question": pre_doc.page_content,
                "answer": standard_answer,
                "user_input_answer": user_answer,
                "row_id": pre_doc.metadata.get("excel_row"),
                "filename": pre_doc.metadata.get("filename"),
                "content": pre_doc.metadata.get("content"),
                "position": pre_doc.metadata.get("location"),
                "llm_reason": llm_result.get("reason", ""),
                "is_correct": llm_result.get("is_correct", False),
                "is_correct_str": get_decision_text(decision, session.get("language")),
                "matched_points": llm_result.get("matched_points", []),
                "missed_points": llm_result.get("missed_points", []),
                "score": llm_result.get("score", 0),
            })
            is_addition_mode = True

        if is_addition_mode:
            # 处于追问模式，将当前题加入追问题目列表（避免重复加入）
            if pre_pk not in session["additional_question"]:
                session["additional_question"].append(pre_pk)
            # 判断是否满足退出追问模式条件
            stats = session.get("additional_stats", [0, 0])  # [正确， 错误]
            if stats is None or len(stats) != 2:
                stats = [0, 0]
            correct = stats[0] if flag else stats[0] + 1
            incorrect = stats[1] + 1 if flag else stats[1]
            attempts = correct + incorrect - 1
            logger.info(f"追问模式状态：答对 {correct}，答错 {incorrect}，尝试次数 {attempts}")
            if attempts > 0 and (attempts >= add_mode_max_questions or correct / attempts >= add_mode_min_ratio):
                # 满足退出条件，清空追问模式
                logger.info(f"退出追问模式：尝试次数 {attempts}，答对率 {correct / attempts:.2f}")
                session["additional_question"] = []
                is_addition_mode = False
                session["additional_stats"] = None
            else:
                # 继续追问模式，更新状态
                session["additional_stats"] = [correct, incorrect]
                logger.info(f"继续保持追问模式")

        if is_addition_mode:
            # 仍在追问模式下，基于错题检索相似题目
            additional_questions = [session["question_bank"][pk].page_content
                                    for pk in session.get("additional_question", [])
                                    if pk in session.get("question_bank", {})]
            additional_questions += [session["question_bank"][pk].metadata.get("answer")
                                     for pk in session.get("additional_question", [])
                                     if pk in session.get("question_bank", {})]

            query = "\n".join(additional_questions)

            # 进行切断处理，embedding模型最长支持512
            query = truncate_text(query)
            current_doc,token_usage = await retriever_question_by_fail_question(pre_doc, query, session, embeddings=embeddings)
            if current_doc:
                important_param["next_question"] = current_doc.page_content
                current_pk = str(current_doc.metadata.get("pk"))
                if current_pk is not None and current_pk not in session["question_bank"]:
                    current_doc.metadata.setdefault("score", 0.0)
                    session["question_bank"][current_pk] = current_doc
                    session["additional_question"].append(current_pk)
        else:
            # 非追问模式，清空追问题目列表
            session["additional_question"] = []
        important_param["last_question"]["is_correct"] = llm_result.get("is_correct", True)
        important_param["last_question"]["is_correct_str"] = get_decision_text(decision, session.get("language"))
        important_param["last_question"]["reason"] = llm_result.get("reason", "")
        important_param["last_question"]["score"] = score
        pre_doc.metadata["score"] = score

        # 将milvus插入操作改为后台执行，不阻塞主方法
        asyncio.create_task(save_user_answer_log(
            user_id=session["user_id"],
            exams_id=session_id,
            question=pre_doc.page_content,
            question_type=question_type,
            standard_answer=standard_answer,
            user_answer=user_input,
            score=float(score),
            exam_time=session.get("start_time"),
            decision_result=get_decision_text(decision, session.get("language")),
            excel_row=pre_doc.metadata.get("excel_row"),
            data_lang=_get_session_data_lang(session),
            prompt_lang=_get_session_prompt_lang(session),
        ))

        if "answer_logs" not in session:
            session["answer_logs"] = []
        session["answer_logs"].append({
            "question_number": current_time - 1,
            "question": pre_doc.page_content,
            "user_answer": user_answer,
            "standard_answer": standard_answer,
            "score": float(score),
            "decision_result": decision,
            "excel_row": pre_doc.metadata.get("excel_row"),
            "answer_time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        })

        if current_time == new_total_time + 1:
            asyncio.create_task(save_full_process_log(
                user_id=session["user_id"],
                exams_id=session_id,
                answer_logs=session["answer_logs"],
                start_time=session.get("start_time"),
                end_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                data_lang=_get_session_data_lang(session),
                prompt_lang=_get_session_prompt_lang(session),
            ))
    else:
        raise HTTPException(status_code=200, detail="答题已结束")

    system_prompt = await get_system_prompt(important_param, session["fail_question_list"], new_total_time,
                                            session["question_bank"],session)
    # 将更新后的会话数据写回Redis
    update_redis_session(session_id, session,redis_client)
    return system_prompt, user_input, current_pk, current_time, flag, session


# ========== 流式输出逻辑 ==========

async def format_point_by_query(
        query: str,
        max_points: int = 3,
        delimiter: str = "\n"
) -> str:
    """
    输入: 错题题干合并文本
    输出: 由知识点组成的字符串，使用 delimiter 分隔；无序号、无解释
    """
    if not query or not query.strip():
        return ""

    clean_text = re.sub(r"\s+", " ", query).strip()

    prompt = get_prompt(
        "FORMAT_POINTS",
        max_points=max_points,
        delimiter=delimiter,
        clean_text=clean_text
    )

    # Resolve LLM config at runtime
    resolver = get_cached_config_resolver()
    resolved_llm = resolver.resolve(ModelConfigScope.SMART_PRACTICE_LLM)

    llm_client = AsyncOpenAI(
        api_key=resolved_llm.api_key.get_secret_value() if resolved_llm.api_key else "",
        base_url=resolved_llm.base_url,
    )

    try:
        resp = await llm_client.chat.completions.create(
            model=resolved_llm.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            extra_body=get_llm_extra_body(resolved_llm.model)
        )
        raw = resp.choices[0].message.content.strip()
    except Exception:
        return ""

    # 规范化拆分
    lines = [l.strip() for l in re.split(r"[\n;；]", raw) if l.strip()]
    points: List[str] = []
    seen = set()
    for p in lines:
        # 去掉可能的序号前缀
        p = re.sub(r"^[\d一二三四五六七八九十][\.\)\s-]*", "", p).strip()
        if not (2 <= len(p) <= 30):
            continue
        low = p.lower()
        if low in seen:
            continue
        seen.add(low)
        points.append(p)
        if len(points) >= max_points:
            break

    return delimiter.join(points)


# ========== 辅助函数 ==========
async def retriever_question_by_fail_question(
        pre_doc: Document,
        query_point: str,
        session: dict,
        embeddings,
        top_k: int = 10,
        max_gap: float = 1,
):
    """
    追问模式：基于错题检索“同一 SOP 内、略高难度”的相似题。

    关键约束：
    - 只在【当前错题所在 SOP】内检索，不再跨岗位 / 跨 SOP。
    - 返回 (Document | None, token_usage)
    """

    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def get_level(d: Document) -> float:
        v = d.metadata.get("difficulty_factor", 0)
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    # ------- 准备排除列表：历史题目 + 当前错题 -------
    history_pks = session.get("history_question_pks", [])
    exclude_pks = {p for p in (_to_int(x) for x in history_pks) if p is not None}
    pre_pk = pre_doc.metadata.get("pk")
    if pre_pk is not None:
        exclude_pks.add(pre_pk)

    # ------- 追问范围：强制限定同一 SOP（可选再叠加岗位） -------
    sop_id = _to_int(pre_doc.metadata.get("sop_id"))
    position_id = pre_doc.metadata.get("position_id") or session.get("position_id")

    expr_parts = []
    if sop_id is not None:
        expr_parts.append(f"sop_id == {sop_id}")
    # 双保险：如果有岗位信息，也一起约束（防止极端脏数据）
    if position_id:
        expr_parts.append(f'position_id == "{position_id}"')

    # 如果都拿不到，就兜底用原来的逻辑（理论上不会走到这里）
    if not expr_parts:
        exam_type = session.get("exam_type", "single")
        if exam_type == "single":
            expr_parts.append(f'sop_id == {session.get("sop_id")}')
        else:
            expr_parts.append(f'position_id == "{session.get("position_id")}"')

    # 排除已经出过的题
    if exclude_pks:
        exclude_literal = ",".join(str(p) for p in exclude_pks)
        expr_parts.append(f"pk not in [{exclude_literal}]")

    expr = " and ".join(expr_parts)
    logger.info(f"[retriever_question_by_fail_question] expr = {expr}")

    # ------- 从 Milvus 检索候选题 -------
    retriever_response = similarity_search_with_score(
        query=query_point,
        embedding_function=embeddings,
        collection_name=_get_collection_name(_get_session_data_lang(session)),
        k=top_k,
        expr=expr
    )

    # 统一的 token 统计结构（主要来自重排阶段）
    token_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }

    if not retriever_response:
        return None, token_usage

    candidates = [doc for (doc, _score) in retriever_response]
    if not candidates:
        return None, token_usage

    # ------- 可选：用 LLM 做一次重排，提升语义相关度 -------
    try:
        reranked, rerank_usage = await llm_rerank(
            query=query_point,
            candidates=candidates,
            session=session,
            top_n=5
        )
        if rerank_usage:
            token_usage = rerank_usage
        if reranked:
            candidates = reranked
    except Exception as e:
        logger.warning(f"llm_rerank 失败，使用原始召回结果: {e}")

    current_level = get_level(pre_doc)

    # ------- 找“略高难度”的题，形成一个 window -------
    window = []
    for d in candidates:
        lvl = get_level(d)
        if lvl > current_level:
            diff = lvl - current_level
            if diff <= max_gap:
                window.append((diff, lvl, d))

    if window:
        # 难度差越小越好，其次难度值越低
        window.sort(key=lambda x: (x[0], x[1]))
        return window[0][2], token_usage

    # 兜底：返回最相似的第一题
    return candidates[0], token_usage


async def llm_rerank(
        query: str,
        candidates: List[Document],
        session: dict,
        top_n: int = 5
):
    token_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }
    if not query or not candidates:
        return [],token_usage
    # Resolve LLM config at runtime
    resolver = get_cached_config_resolver()
    resolved_llm = resolver.resolve(ModelConfigScope.SMART_PRACTICE_LLM)

    llm_client = AsyncOpenAI(
        api_key=resolved_llm.api_key.get_secret_value() if resolved_llm.api_key else "",
        base_url=resolved_llm.base_url,
    )
    items = []
    for i, d in enumerate(candidates):
        text = re.sub(r"\s+", " ", d.page_content).strip()[:300]
        items.append(f"[{i}] {text}")

    prompt = get_prompt(
        "LLM_RERANK",
        language=session.get("language"),
        query=query,
        items=chr(10).join(items)
    )

    resp = await llm_client.chat.completions.create(
        model=resolved_llm.model,
        messages=[{"role": "user", "content": prompt}],
        extra_body=get_llm_extra_body(resolved_llm.model),
        temperature=0
    )

    if hasattr(resp, 'usage') and resp.usage:
        token_usage["prompt_tokens"] = resp.usage.prompt_tokens
        token_usage["completion_tokens"] = resp.usage.completion_tokens
        token_usage["total_tokens"] = resp.usage.total_tokens
    logger.info(f"LLM 判题使用token: {token_usage}")

    raw = resp.choices[0].message.content.strip()
    ranking = []
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            seq = data.get("ranking", [])
            for v in seq:
                if isinstance(v, int) and 0 <= v < len(candidates):
                    ranking.append(v)
        except json.JSONDecodeError:
            pass
    if not ranking:
        return candidates[:top_n],token_usage
    ordered = []
    seen = set()
    for idx in ranking:
        if idx not in seen:
            seen.add(idx)
            ordered.append(candidates[idx])
        if len(ordered) >= top_n:
            break
    if len(ordered) < top_n:
        for d in candidates:
            if d not in ordered and len(ordered) < top_n:
                ordered.append(d)
    return ordered,token_usage


# def build_fail_metadata(session: dict, current_time: int, flag: bool) -> str:
#     """构建前端错题高亮信息"""
#     if 1 < current_time < total_time and flag:
#         fail = session["fail_question_list"][-1]
#         fail_node = [{"metadata": {
#             "trainType": "node",
#             "rowId": fail.get("row_id"),
#             "filename": fail.get("filename"),
#             "position": fail.get("position")
#         }}]
#     else:
#         fail_node = [{"metadata": {"trainType": "none"}}]
#
#     return json.dumps({"documents": fail_node}, ensure_ascii=False)


def get_redis_session(session_id: str,redis_client) -> dict:
    """
    从Redis获取或初始化会话（与get_session逻辑完全对齐）
    返回结构：{"question_bank": {}, "current_time": 1, "history_question_pks": [], "fail_question_list": []}
    """
    # 1. 定义Redis中会话的Key（与原逻辑一致）
    session_key = f"{SESSION_REDIS_PREFIX}{session_id}"

    # 2. 从Redis哈希结构获取所有会话字段
    session_data = redis_client.hgetall(session_key)

    # 3. 反序列化Redis存储的字符串数据，还原Python原生类型
    deserialized = {}
    for key, value in session_data.items():
        # Redis返回的key是bytes类型，需先转成字符串（避免键名异常）
        key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        try:
            # 解析JSON：还原列表（history_question_pks等）、字典（question_bank）等类型

            if (key == 'question_bank'):
                target_doc_dict = json.loads(value)
                for key, value in target_doc_dict.items():
                    target_doc_dict[key] = Document(
                        page_content=value["page_content"],  # 提取存储的内容
                        metadata=value["metadata"]  # 提取存储的元数据
                    )
                deserialized[key_str] = target_doc_dict
            else:
                deserialized[key_str] = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # 非JSON格式数据（如未来扩展的简单字符串字段）直接存储
            deserialized[key_str] = value.decode("utf-8") if isinstance(value, bytes) else value

    # 4. 核心逻辑：会话不存在时，初始化默认结构（与get_session完全一致）
    if not deserialized:
        # 初始化默认会话结构（键名、初始值与get_session完全匹配）
        default_session = {
            "question_bank": {},  # 题库（空字典）
            "current_time": 1,  # 当前交互次数（初始为1）
            "history_question_pks": [],  # 历史题目PK列表（空列表）
            "fail_question_list": []  # 错题列表（空列表）
        }
        # 将默认结构存入Redis（哈希类型），并设置过期时间（24小时=86400秒）
        # 注意：需将Python类型转成JSON字符串存储，保证下次读取能正确反序列化
        for k, v in default_session.items():
            redis_client.hset(session_key, k, json.dumps(v))
        return default_session  # 返回默认结构

    # 5. 补全逻辑：若Redis中会话字段不完整（极端场景，如手动修改过Redis数据），补全默认值
    # 确保返回的会话字典包含所有必要键，避免后续代码报KeyError
    required_keys = {
        "question_bank": {},
        "current_time": 1,
        "history_question_pks": [],
        "fail_question_list": []
    }
    for req_key, req_default in required_keys.items():
        if req_key not in deserialized:
            deserialized[req_key] = req_default
            # 同步补全到Redis，避免下次读取仍缺失
            redis_client.hset(session_key, req_key, json.dumps(req_default))

    return deserialized


def _convert_non_serializable(obj: Any) -> Any:
    """递归转换非JSON可序列化对象（重点处理嵌套的LangChain Document）"""
    # 1. 精准处理langchain_core的Document类型
    if isinstance(obj, Document):
        return {
            "__type__": "LangChainDocument",  # 标记类型，方便后续反序列化（可选）
            "page_content": obj.page_content,  # Document核心内容
            "metadata": obj.metadata  # Document元数据（如来源、时间等）
        }
    # 2. 处理列表：递归转换每个元素（比如列表中的Document）
    elif isinstance(obj, list):
        return [_convert_non_serializable(item) for item in obj]
    # 3. 处理字典：递归转换每个值（比如question_bank字典中的Document）
    elif isinstance(obj, dict):
        return {k: _convert_non_serializable(v) for k, v in obj.items()}
    # 4. 基础可序列化类型（直接返回，无需处理）
    elif isinstance(obj, (int, float, bool, str, tuple, type(None))):
        return obj
    # 5. 其他未知类型：转为字符串兜底（避免序列化失败）
    else:
        return str(obj)


def delete_redis_session(session_id: str,redis_client) -> bool:
    """
    从Redis中删除指定的会话（包括会话数据和全局时间键）

    Args:
        session_id: 会话ID

    Returns:
        bool: 删除操作是否成功（True表示没有异常，无论键是否存在；False表示删除过程出错）
    """
    session_key = f"{SESSION_REDIS_PREFIX}{session_id}"
    global_time_key = f"{TIME_REDIS_PREFIX}{session_id}"
    try:
        # 一次性删除多个 key，不存在的 key 会被忽略
        redis_client.delete(session_key, global_time_key)
        return True
    except Exception as e:
        print(f"删除会话失败: {str(e)}")
        return False


def update_redis_session(session_id: str, session_data: Dict,redis_client) -> None:
    """更新Redis中的会话数据（已适配LangChain嵌套Document）"""
    session_key = f"{SESSION_REDIS_PREFIX}{session_id}"
    serialized = {}

    for key, value in session_data.items():
        # 先递归转换所有嵌套的非序列化对象（包括question_bank里的Document）
        converted_value = _convert_non_serializable(value)
        # 再JSON序列化（此时converted_value已完全可序列化）
        serialized[key] = json.dumps(converted_value)

    # 写入Redis并延长过期时间
    redis_client.hset(session_key, mapping=serialized)


def build_fail_metadata_time(
        session: Dict, current_time: int, flag: bool,
        remaining_time: int, elapsed_time: int, time_limit: int,
        metadata_type: str
) -> str:
    new_total_time = session['new_total_time']
    """统一元数据处理，携带全局时间信息"""
    time_info = {
        "remaining_time": int(remaining_time),
        "elapsed_time": int(elapsed_time),
        "time_limit": time_limit,
        "type": metadata_type
    }

    if metadata_type == "done":
        if 1 < current_time < new_total_time and flag:
            # 从会话中获取错题信息（已从Redis加载）
            fail = session.get("fail_question_list", [])[-1] if session.get("fail_question_list") else {}
            content = [{"metadata": {
                "trainType": "node",
                "rowId": fail.get("row_id"),
                "filename": fail.get("filename"),
                "position": fail.get("position"),
                "time_info": time_info
            }}]
        else:
            content = [{"metadata": {
                "trainType": "none",
                "time_info": time_info
            }}]
        return json.dumps({"documents": content}, ensure_ascii=False)

    else:
        content = [{"metadata": {
            "time_info": time_info
        }}]
        return json.dumps({"documents": content}, ensure_ascii=False)


async def get_position_by_filename(filename: str, embeddings, data_lang: str = DEFAULT_LANG):
    """
    根据文件名称，获取对应的岗位，并且根据岗位获取这个岗位对应的filenames
    """
    position_response = None
    try:
        # 第一步：根据文件名查询对应的岗位ID
        position_response = similarity_search_with_score(
            query=filename,  # 使用文件名作为查询
            embedding_function=embeddings,
            collection_name=_get_collection_name(data_lang),
            k=1,  # 只需要一个结果来获取岗位信息
            expr=f'filename == "{filename}"'
        )
    except Exception as e:
        logger.error("获取岗位信息失败: {}".format(str(e)))
        raise RuntimeError("获取岗位信息失败")
    doc = position_response[0][0]
    position_id = doc.metadata.get("position_id")
    return position_id


def truncate_text(text, max_tokens=300):
    """截断文本到最大token数量"""
    # 简单的字符级截断，也可以使用tokenizer进行更精确的截断
    # 假设平均每个token约4个字符（这是一个粗略估计）
    max_chars = max_tokens
    if len(text) > max_chars:
        return text[:max_chars]
    return text


async def summarize_exam_performance(total_questions: int, complete_rate: str, accumulated_score: float, total_score: int,
                                     wrong_questions_text: str, answer_logs: List[dict]) -> str:
    """基于整体考试数据生成总结提示词并调用大模型返回总结。
    输出包含：总体表现、错题分析、改进建议。
    """
    try:
        prompt = get_prompt(
            "SUMMARIZE_EXAM",
            total_questions=total_questions,
            complete_rate=complete_rate,
            accumulated_score=accumulated_score,
            total_score=total_score,
            wrong_questions_text=wrong_questions_text if wrong_questions_text else '无'
        )

        # Resolve LLM config at runtime
        resolver = get_cached_config_resolver()
        resolved_llm = resolver.resolve(ModelConfigScope.SMART_PRACTICE_LLM)

        llm_client = AsyncOpenAI(
            api_key=resolved_llm.api_key.get_secret_value() if resolved_llm.api_key else "",
            base_url=resolved_llm.base_url,
        )

        resp = await llm_client.chat.completions.create(
            model=resolved_llm.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            extra_body=get_llm_extra_body(resolved_llm.model)
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"summarize_exam_performance 调用失败: {e}")
        return "考试总结生成失败，稍后重试。"


async def trigger_leaderboard_recalculate(sop_id: int, tenant_id: int, data_lang: str = "zh") -> None:
    """
    调用 Dashboard 服务的排行榜重算接口，更新 sp_sop_leaderboard。
    仅对单 SOP 考试（exam_type != 'mix'）有效。
    失败不影响主流程。
    """
    if not sop_id:
        return
    try:
        headers = {"Content-Type": "application/json"}
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                TOP_PUSH_URL,
                json={"sop_id": sop_id, "tenant_id": tenant_id, "data_lang": data_lang},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                body = await resp.json()
                if resp.status == 200:
                    logger.info(
                        f"SOP {sop_id}/{data_lang} 排行榜重算成功，"
                        f"影响 {body.get('data', {}).get('affected_rows', '?')} 条"
                    )
                else:
                    logger.warning(
                        f"SOP {sop_id}/{data_lang} 排行榜重算返回非200: status={resp.status}, body={body}"
                    )
    except Exception as e:
        logger.error(f"触发排行榜重算失败 sop_id={sop_id} lang={data_lang}: {e}")


async def finish_and_push_exams_info(user: str, exam_id: str, redis_client):
    """完成考试：统计成绩并调用第三方接口推送考试结果，然后清理会话。"""
    # 读取会话，不要先删除，避免丢失数据
    session = get_redis_session(exam_id, redis_client)
    # 已答题目列表
    answered_questions = session.get("answer_logs", [])
    new_total_time = session.get("new_total_time", 0)

    if not answered_questions:
        logger.info(f"考试结束 | session_id={exam_id} | 结果：用户未答题，不进行入库和三方推送。")
        delete_redis_session(exam_id, redis_client)
        return

    # 1. 使用 Redis 分布式锁/标志位防止重复处理
    lock_key = f"lock:finish_exam:{exam_id}"
    # 尝试设置锁，有效期 60 秒（足够处理完推送逻辑）
    if not redis_client.set(lock_key, "processing", nx=True, ex=60):
        logger.info(f"考试 {exam_id} 已经在处理中，跳过本次触发。")
        return

    try:
        data_lang = _get_session_data_lang(session)
        total_score_defined = 100  # 总分固定
        # 统计分数：只累计实际已判题的答题日志，避免把未作答题或追问题库中的题混入总分
        accumulated_score = 0.0
        correct_count = 0
        partial_count = 0
        max_single_score = total_score_defined / new_total_time if new_total_time > 0 else 0

        for answer_log in answered_questions:
            s = float(answer_log.get("score", 0.0) or 0.0)
            accumulated_score += s
            if max_single_score > 0:
                if s >= max_single_score:  # 满分视为正确
                    correct_count += 1
                elif 0 < s < max_single_score:
                    partial_count += 1
        accumulated_score = round(accumulated_score, 2)

        # 总题数
        total_questions = new_total_time

        logger.info(
            f"考试 {exam_id} 统计结果：总题数 {total_questions}，已答题数 {len(answered_questions)}，得分 {accumulated_score}")

        # 完成率：
        complete_rate_float = len(answered_questions) / total_questions if total_questions else 0
        complete_rate = f"{complete_rate_float:.2f}"  # 转为字符串形式

        #
        fail_list = session.get("fail_question_list", [])
        wrong_questions_text = "\n".join([format_wrong_question_natural(q) for q in fail_list]) if fail_list else "无"

        # 总结 调用模型总结本次考试表现
        # summary = await summarize_exam_performance(total_questions, complete_rate, accumulated_score, total_score_defined,
        #                                            wrong_questions_text, answer_logs)
        detail = wrong_questions_text
        # detail = summary  # 作为对话明细推送

        user_name = session.get("username", "")
        exam_type = session.get("exam_type")
        conversation_id = session.get("conversation_id", "")
        question_bank: Dict[str, Document] = session.get("question_bank", {})
        if exam_type != "mix" and question_bank:
            # 通过第一题sop_id获取sop_info中的file_type作为category
            sop_id = session.get("sop_id")
            mysql_client = MySQLClient(MYSQL_CONFIG)
            sop_info = mysql_client.query_sop_info_by_id(sop_id, lang=data_lang)
            file_type = sop_info.get("file_type", "sop")
            exam_category = EXAM_CATEGORY_MAP.get(file_type)
            category = FILE_TYPE_CATEGORY_MAP.get(file_type)
            file_name = session.get("filename")
        else:
            category = "5"  # 混合考试统一类别5
            exam_category = "混合出题"
            file_name = session.get("position_id")

        # 新增考试记录
        exam_record = ExamRecordCreate(
            id=exam_id,
            user_id=user,
            position_id=session.get("position_id") or "",
            start_time=(datetime.strptime(session.get("start_time"), "%Y-%m-%d %H:%M:%S") if session.get(
                "start_time") else None),
            end_time=datetime.now(),
            exam_category=exam_category,
            filename=file_name,
            conversation_id=conversation_id,
            summary=detail,
            total_score=total_score_defined,
            accumulated_score=accumulated_score,
            total_questions=total_questions,
            answered_questions=len(answered_questions),
            sop_id=session.get("sop_id") if exam_type != "mix" else None,
            tenant_id=session.get("tenant_id")
        )

        exam_record_data = exam_record.model_dump()
        db_client = MySQLClient(MYSQL_CONFIG)

        create_exam_flag = await db_client.insert_exam_record(exam_record_data, lang=data_lang)

        if not create_exam_flag:
            logger.error(f"考试 {exam_id} 已记录，不再重复推送结果。")
            delete_redis_session(exam_id, redis_client)
            return

        # 触发排行榜重算（仅单 SOP 考试，异步非阻塞）
        if exam_type != "mix" and session.get("sop_id"):
            await trigger_leaderboard_recalculate(
                sop_id=int(session.get("sop_id")),
                tenant_id=int(session.get("tenant_id")),
                data_lang=data_lang,
            )

        # 推送：submit_exam_result 是同步方法，使用线程避免阻塞事件循环
        try:
            # push_resp = await submit_exam_result(
            #     conversation_id,  # conversationId
            #     detail,  # detail
            #     int(round(accumulated_score)),  # score 转整形（第三方接口要求整数）
            #     total_score_defined,  # totalScore
            #     complete_rate,  # completeRate
            #     user,  # userId
            #     user_name,  # userName
            #     category,  # category
            #     file_name  # fileName
            # )
            logger.info(f"模拟考试结果推送成功: ")
        except Exception as e:
            logger.error(f"考试结果推送失败: {e}")

        # 清理会话
        delete_redis_session(exam_id, redis_client)
    except Exception as e:
        logger.error(f"处理结束考试异常: {traceback.format_exc()}")
        # 如果失败，可以考虑删除锁以便重试，或者保留锁由管理员处理
        redis_client.delete(lock_key)


def allocate_questions_to_sops(position_id: str, number: int, data_lang: str = DEFAULT_LANG) -> Dict[int, int]:
    """
    根据岗位ID分配题目到各个SOP

    Args:
        position_id: 岗位ID
        number: 需要分配的题目总数
        data_lang: 业务数据语种，用于路由 sp_sop_info* 表

    Returns:
        Dict[int, int]: {sop_id: 题目数量} 的映射字典

    Raises:
        ValueError: 当岗位下没有SOP信息时抛出
    """
    db_client = MySQLClient(MYSQL_CONFIG)
    sop_infos = db_client.query_sop_infos_by_position_id(position_id, lang=data_lang)

    if not sop_infos:
        raise ValueError(f"岗位 {position_id} 未找到SOP信息")

    function_call_params = {}
    sop_count = len(sop_infos)

    if sop_count == number:
        # SOP数量等于题目数：每个SOP分配1题
        function_call_params.update({
            sop_info.get("sop_id"): 1
            for sop_info in sop_infos
        })
    elif sop_count > number:
        # SOP数量大于题目数：随机选择number个SOP，各分配1题
        selected_sops = random.sample(sop_infos, number)
        function_call_params.update({
            sop_info.get("sop_id"): 1
            for sop_info in selected_sops
        })
    else:
        # SOP数量小于题目数：平均分配并处理余数
        base_count = number // sop_count
        remainder = number % sop_count

        for i, sop_info in enumerate(sop_infos):
            # 前remainder个SOP多分配1题
            count = base_count + (1 if i < remainder else 0)
            function_call_params[sop_info.get("id")] = count

    return function_call_params


def retrieve_questions_by_sops(
        session_id: str,
        sop_allocations: Dict[int, int],
        question_type: str,
        embeddings,
        data_lang: str = DEFAULT_LANG
) -> Dict[str, Document]:
    """
    根据SOP分配情况批量检索题目

    Args:
        session_id: 会话ID(用于检索query)
        sop_allocations: {sop_id: 题目数量} 的分配字典
        question_type: 题目类型("填空题" 或 "问答题")
        embeddings: 嵌入函数
        data_lang: 业务数据语种，用于路由 Milvus 集合

    Returns:
        Dict[str, Document]: {pk: Document} 的题库字典
    """
    retriever_response_list = []
    collection_name = _get_collection_name(data_lang)

    for sop_id, num in sop_allocations.items():
        expr = f'sop_id == {sop_id} and question_type == "{question_type}"'
        retriever_response = similarity_search_with_score(
            query=session_id,
            embedding_function=embeddings,
            collection_name=collection_name,
            k=num,
            expr=expr
        )
        retriever_response_list.append(retriever_response)

    question_bank = {}
    for retriever_response in retriever_response_list:
        for doc_tuple in retriever_response:
            doc = doc_tuple[0]
            doc.metadata["score"] = 0.0
            question_bank[doc.metadata["pk"]] = doc

    return question_bank
