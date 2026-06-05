# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import atexit
import os
import logging
import signal
import threading
import traceback
import uuid

import redis
from datetime import datetime
import time
import tiktoken
from typing import AsyncGenerator, Dict, List, Union, Optional
from fastapi.responses import StreamingResponse
from langchain_community.embeddings import HuggingFaceHubEmbeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from openai import AsyncOpenAI
from fastapi import Request, Body, HTTPException
from comps import opea_microservices, CustomLogger, register_microservice, ServiceType, register_statistics
from comps.chathistory.user_logs_mongo_store import AnswerLogDocumentStore
from comps.cores.proto.docarray import TrainParams
from comps.smart_practice.core import update_redis_session, load_short_answer_bank, \
    load_fill_in_blank, get_redis_session, build_fail_metadata_time, prepare_question, get_position_by_filename, \
    finish_and_push_exams_info, select_questions, get_actual_total_time_by_exam_type, _resolve_data_lang
from comps.smart_practice.db_client import MySQLClient
from comps.smart_practice.config import (
    LOCAL_EMBEDDING_MODEL,
    TEI_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_MODEL,
    embedding_ctx_length,
    TIME_LIMIT,
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, TIME_REDIS_PREFIX, total_time,
    openai_api_key, llm_endpoint, model_name, MYSQL_CONFIG, BAILIAN_EMBEDDING_MODEL, BAILIAN_EMBEDDING_ENDPOINT,
    BAILIAN_EMBEDDING_API_KEY, LLM_EXTRA_BODY, get_llm_extra_body, get_cached_config_resolver, ModelConfigScope
)
from openai import OpenAI
from comps.account.auth import require_auth_dict

# ========== 全局配置 ==========
logger = CustomLogger("smart_practice", os.getenv("LOG_LEVEL", "INFO"))

session_ids: Dict[str, dict] = {}


def mark_answer_in_progress(session_id: str, session: dict, redis_client) -> None:
    """Mark the current session as processing an answer to avoid timeout race conditions."""
    session["answer_in_progress"] = True
    update_redis_session(session_id, session, redis_client)


async def complete_answer_processing(
        session_id: str,
        session: dict,
        redis_client,
        trigger_finish: bool = False
) -> None:
    """Clear in-flight flag and finish the exam if timeout requested it while the answer was processing."""
    pending_auto_submit = bool(session.get("pending_auto_submit"))
    session["answer_in_progress"] = False
    session["pending_auto_submit"] = False
    update_redis_session(session_id, session, redis_client)

    if trigger_finish or pending_auto_submit:
        await finish_and_push_exams_info(session["user_id"], session_id, redis_client)

class BailianEmbeddings(Embeddings):
    def __init__(self, api_key: str, model: str, base_url: str, dimensions: int = 256):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.dimensions = dimensions

    def embed_query(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions
        )
        return resp.data[0].embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        resp = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions
        )
        return [d.embedding for d in resp.data]

@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/v1/exams/start",
    host="0.0.0.0", port=9010)
@require_auth_dict()
@register_statistics(names=["opea_service@train_llm"])
async def stream_chat_with_history(
                                    request: Request,
                                   user_id: Union[str, int] = Body(..., embed=True),
                                   sop_id: int = Body(None, embed=True,description="填写了此参数，考试范围为单个sop"),
                                   position_id: str = Body(None, embed=True,description="填写了此参数，考试范围为岗位"),
                                   username: str = Body(None,description="用户名"),
                                   conversation_id : str = Body(None,description="dfxw端会话ID"),
                                   user: dict = None
                                   ) -> dict:
    """
    开始，根据用户传递的user_id和file_name进行session的初始化以及exams_id
    """
    # 参数验证：必须提供其中一个，但不能同时提供
    if (not position_id and not sop_id) or (position_id and sop_id):
        error_msg = "参数错误：必须提供 sop_id 或 position_id 其中一个，不能同时提供或都不提供"
        return {
            "status": 500,  # 使用400而不是500，因为这是客户端参数错误
            "message": error_msg,
            "results": None
        }
    session_id = str(uuid.uuid4())
    session = get_redis_session(session_id, redis_client)
    # data_lang: 业务数据路由语种，来自 JWT.lang；与 prompt 语种 session["language"] 完全独立
    data_lang = _resolve_data_lang((user or {}).get("lang"))
    session["data_lang"] = data_lang
    session["exam_id"] = session_id
    session["exam_type"] = "mix" if position_id else "single"
    session["position_id"] = position_id
    session["username"] = username
    session["conversation_id"] = conversation_id
    if sop_id is not None:
        mysql_client = MySQLClient(MYSQL_CONFIG)
        sop_info = mysql_client.query_sop_info_by_id(sop_id, lang=data_lang)
        file_name = sop_info.get("filename")
        session["filename"] = file_name
        session["position_id"] = sop_info.get("position_id")
        # 保留 smart 原 session["language"] 作为 prompt_lang，由 SOP 记录的 lang 决定
        session["language"] = sop_info.get("lang")
        session["sop_id"] = sop_id
        session["tenant_id"] = sop_info.get("tenant_id")
    session["user_id"] = user_id

    # 首先不管是进入到单文件还是岗位混合，先把这两个的总题数列出来，看有没有达到total_time,没有的话，用查询出来的总题数替换掉total_time继续走下面的逻辑
    new_total_time = get_actual_total_time_by_exam_type(session,session_id,embeddings)
    session["new_total_time"] = new_total_time
    # 获取当前类型下总题数
    # 不同类型题目合集：先各自取最多 total_time 道作为备选池
    fill_pool: Dict[str, Document] = load_fill_in_blank(session, session_id, new_total_time, embeddings)
    short_pool: Dict[str, Document] = load_short_answer_bank(session, session_id, new_total_time, embeddings)

    # 题库总量校验
    if len(fill_pool) + len(short_pool) < new_total_time:
        return {
            "status": 500,
            "message": f"启动考试失败，当前考试文档或者岗位对应的题目数量必须大于等于{new_total_time}",
            "results": None
        }

    # 二次筛选：填空优先取总数一半 5，不足用问答补；再用问答补到 total_time，不足再用填空补
    fill_in_list = list(fill_pool.values())
    short_answer_list = list(short_pool.values())
    fill_in_target = min(int(new_total_time/2), new_total_time)

    selected_docs = select_questions(
        fill_in_list=fill_in_list,
        short_answer_list=short_answer_list,
        total_count=new_total_time,
        fill_in_target=fill_in_target
    )

    # 构建最终题库（以 pk 为键）
    question_bank: Dict[str, Document] = {
        str(doc.metadata.get("pk")): doc for doc in selected_docs
    }

    session["question_bank"] = question_bank
    session["additional_question"] = []

    # 将更新后的会话数据写回Redis
    update_redis_session(session_id, session, redis_client)

    # Redis全局考试时间键
    redis_time_key = f"{TIME_REDIS_PREFIX}{session_id}"
    # 初始化考试时间（整个考试仅一次）
    redis_client.hset(redis_time_key, mapping={
        "start_time": datetime.now().astimezone().isoformat(),
        "time_limit": TIME_LIMIT  # 全局考试时长（秒）
    })
    # 设置过期时间为 1 天（86400 秒）
    redis_client.expire(redis_time_key, TIME_LIMIT)

    return {
        "status": 200,
        "message": "成功",
        "results": {
            "exams_id": session_id,
            "expire": TIME_LIMIT
        }
    }

@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/v1/exams/answer",
    host="0.0.0.0", port=9010)
@register_statistics(names=["opea_service@train_llm"])
async def answer(request: Request, input: TrainParams = Body(embed=True)) -> StreamingResponse:
    """流式输出，会话信息和考试时间均存储在Redis"""

    messages = input.messages
    session_id = input.session_id  # 考试会话唯一标识

    # Redis全局考试时间键
    redis_time_key = f"{TIME_REDIS_PREFIX}{session_id}"

    # 只读取考试时间，不再初始化
    time_data = redis_client.hgetall(redis_time_key)
    if not time_data or "start_time" not in time_data:
        async def stream_generator() -> AsyncGenerator[str, None]:
            yield "data: [考试已结束！]\n\n"
            yield "data: [TIMEOUT]\n\n"
            logger.info(f"Session {session_id} 考试全局超时")

        return StreamingResponse(
            stream_generator(),
            headers={"Content-Type": "text/event-stream; charset=utf-8"}
        )
    start_time = datetime.fromisoformat(time_data["start_time"])
    time_limit = int(time_data["time_limit"])

    # 计算全局剩余时间
    elapsed = (datetime.now().astimezone() - start_time).total_seconds()
    remaining_time = max(0, time_limit - elapsed)

    # 全局超时处理
    if remaining_time <= 0:
        async def stream_generator() -> AsyncGenerator[str, None]:
            yield "data: [考试时间已结束！]\n\n"
            timeout_meta = build_fail_metadata_time(
                {}, "", "",
                remaining_time, elapsed, time_limit,
                metadata_type="timeout"
            )
            yield f"data: {timeout_meta}\n\n"
            yield "data: [TIMEOUT]\n\n"
            logger.info(f"Session {session_id} 考试全局超时")
        return StreamingResponse(
                stream_generator(),
                headers={"Content-Type": "text/event-stream; charset=utf-8"}
            )

    # 未超时，判断逻辑
    # session从prepare_question返回，避免后续更新session时覆盖问题
    system_prompt, user_input, current_pk, current_time, flag, session = await prepare_question(messages, session_id,
                                                                                                embeddings,redis_client)
    mark_answer_in_progress(session_id, session, redis_client)
    chat_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": ""}
    ]

    # Resolve LLM config at runtime
    resolver = get_cached_config_resolver()
    resolved_llm = resolver.resolve(ModelConfigScope.SMART_PRACTICE_LLM)

    llm_client = AsyncOpenAI(
        api_key=resolved_llm.api_key.get_secret_value() if resolved_llm.api_key else "",
        base_url=resolved_llm.base_url,
    )
    # 在answer接口调用模型前加入：
    # try:
    #     current_count, minute_key, minute_label = incr_model_minute_usage(redis_client, model_name)
    #     logger.info(
    #         f"[model_usage] model={model_name} minute={minute_label} key={minute_key} 调用计数(含本次)={current_count}")
    # except Exception as e:
    #     logger.warning(f"[model_usage] 统计失败: {e}")

    try:
        chat_completion = await llm_client.chat.completions.create(
            model=resolved_llm.model,
            messages=chat_messages,
            extra_body=get_llm_extra_body(resolved_llm.model),
            temperature=0.1,
            stream=True
        )
    except Exception:
        if session.get("answer_in_progress"):
            await complete_answer_processing(session_id, session, redis_client)
        raise
    total_model_time = 0
    async def stream_generator() -> AsyncGenerator[str, None]:
        nonlocal total_model_time
        full_response = ""
        answer_completed = False
        # 获取tokenizer
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo") if model_name else tiktoken.get_encoding("cl100k_base")
        start_model_time = time.time()  # 模型调用开始时间
        # 从Redis获取全局时间
        time_data = redis_client.hgetall(redis_time_key)
        start_time = datetime.fromisoformat(time_data["start_time"])
        time_limit = int(time_data["time_limit"])

        buffer = ""
        try:
            async for chunk in chat_completion:
                # 客户端断开检测
                if await request.is_disconnected():
                    logger.info(f"Session {session_id} 客户端断开")
                    break

                if not chunk.choices:
                    continue

                delta = getattr(chunk.choices[0].delta, "content", None)
                if not delta:
                    continue

                # 记录首 token 时间
                if total_model_time == 0:
                    total_model_time += time.time() - start_model_time
                    logger.info(f"Session {session_id} 模型调用首个token时间: {total_model_time:.4f}s")

                full_response += delta
                buffer += delta

                # 逐行吐出
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    safe_line = line.replace("\n", "\\n")+"\\n"
                    yield f"data: {safe_line}\n"

            # 循环结束后
            if buffer:
                safe_line = buffer.replace("\n", "\\n")+"\\n"
                yield f"data: {safe_line}\n"
            yield f"data: \n\n"
            # 累加模型调用时间
            total_model_time += time.time() - start_model_time
            logger.info(f"Session {session_id} 模型调用总时间: {total_model_time:.4f} 秒")

            # # 计算当前时间点的全局时间
            elapsed = (datetime.now().astimezone() - start_time).total_seconds()

            yield "data: [DONE]\n\n"

            logging.info(f"Session {session_id} 题目 {current_pk} 完成")

            # 更新会话数据（并写回Redis）
            # 精确计算token数量
            prompt_text = "".join([msg["content"] for msg in chat_messages])
            prompt_tokens = len(encoding.encode(prompt_text))
            completion_tokens = len(encoding.encode(full_response))
            total_tokens = prompt_tokens + completion_tokens

            if "history_question_pks" not in session:
                session["history_question_pks"] = []
            session["history_question_pks"].append(current_pk)
            session["current_time"] = current_time + 1

            update_redis_session(session_id, session,redis_client)

            fail_meta = build_fail_metadata_time(
                session, current_time, flag,
                remaining_time, elapsed, time_limit,
                metadata_type="done"
            )
            yield f"data: {fail_meta}\n\n"
            yield "data: [METADATA DONE]\n\n"

            answer_completed = True
            await complete_answer_processing(
                session_id,
                session,
                redis_client,
                trigger_finish=current_time == session['new_total_time'] + 1
            )
        finally:
            if not answer_completed and session.get("answer_in_progress"):
                await complete_answer_processing(session_id, session, redis_client)

    return StreamingResponse(
        stream_generator(),
        headers={"Content-Type": "text/event-stream; charset=utf-8"}
    )


@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/v1/exams/finish",
    host="0.0.0.0", port=9010)
@register_statistics(names=["opea_service@train_llm"])
async def finsh_exams(
        user_id: Union[str, int] = Body(..., embed=True),
        exams_id: str = Body(..., embed=True)) -> dict:
    """
    清除考试中的相关数据，包括会话和全局时间，并且推送本轮考试信息到东方希望sop文件系统中
    """
    await finish_and_push_exams_info(user_id,exams_id,redis_client)

    return {
        "status": 200,
        "message": "success"
    }


@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/v1/user_log/query",
    host="0.0.0.0", port=9010)
async def query_user_log(user_id: Union[int, str] = Body(..., embed=True),
                         exams_id: str = Body(None, embed=True),
                         question: str = Body(None, embed=True)) -> dict:
    try:
        store = AnswerLogDocumentStore(user_id)
        await store.initialize_storage()
        logs = await store.query_user_logs(
            user_id=user_id,
            exams_id=exams_id,
            question=question,
            log_type="single"
        )
        return {"status": "200", "message": "success", "results": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/v1/user_log/full_process",
    host="0.0.0.0", port=9010)
async def query_full_process_log(user_id: Union[str, int] = Body(..., embed=True),
                                 exams_id: str = Body(None, embed=True)):
    try:
        store = AnswerLogDocumentStore(user_id)
        await store.initialize_storage()
        logs = await store.query_user_logs(
            user_id=user_id,
            exams_id=exams_id,
            log_type="full"
        )
        return {"status": "200", "message": "success", "results": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------- 东方希望对接适配接口 --------------------------------------------


@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/api/exams/start",
    host="0.0.0.0", port=9010)
async def retry_qa(user_id: str = Body(...,description="user_id"),
                   sop_id : int = Body(None,description="sop_id,如果填了sop_id，则范围为单个sop"),
                   position_id:str = Body(None,description="岗位ID，如果传了position_id,则范围为岗位范围"),
                   username: str = Body(...,description="用户名"),
                   conversation_id : str = Body(...,description="dfxw端会话ID"),
                ):

    """
        (东方希望)根据文档id，去更新这个文档对应的所有问答对
    """
    try:

        result = await stream_chat_with_history(user_id,sop_id,position_id, username, conversation_id)
        status = result.get("status", 500)
        msg = result.get("message", "")
        data = result.get("results")
        return make_response(
            data=data,
            msg=msg,
            is_success=(status == 200),
            http_status_code=status
        )
    except Exception as e:
        traceback.print_exc()
        return make_response(
            data=None,
            msg=f"调用异常: {str(e)}",
            is_success=False,
            http_status_code=500
        )



@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/api/exams/answer",
    host="0.0.0.0", port=9010)
@register_statistics(names=["opea_service@train_llm"])
async def answer_api(request: Request, input: TrainParams) -> StreamingResponse:
    """流式输出，会话信息和考试时间均存储在Redis"""

    messages = input.messages
    session_id = input.session_id  # 考试会话唯一标识

    # Redis全局考试时间键
    redis_time_key = f"{TIME_REDIS_PREFIX}{session_id}"

    # 只读取考试时间，不再初始化
    time_data = redis_client.hgetall(redis_time_key)
    if not time_data or "start_time" not in time_data:
        async def stream_generator() -> AsyncGenerator[str, None]:
            yield "data: [考试已结束！]\n\n"
            yield "data: [TIMEOUT]\n\n"
            logger.info(f"Session {session_id} 考试全局超时")
        return StreamingResponse(
            stream_generator(),
            headers={"Content-Type": "text/event-stream; charset=utf-8"}
        )
        # raise HTTPException(status_code=400, detail="考试已结束")
    start_time = datetime.fromisoformat(time_data["start_time"])
    time_limit = int(time_data["time_limit"])

    # 计算全局剩余时间
    elapsed = (datetime.now().astimezone() - start_time).total_seconds()
    remaining_time = max(0, time_limit - elapsed)

    # 全局超时处理
    if remaining_time <= 0:
        async def stream_generator() -> AsyncGenerator[str, None]:
            yield "data: [考试时间已结束！]\n\n"
            timeout_meta = build_fail_metadata_time(
                {}, "", "",
                remaining_time, elapsed, time_limit,
                metadata_type="timeout"
            )
            yield f"data: {timeout_meta}\n\n"
            yield "data: [TIMEOUT]\n\n"
            logger.info(f"Session {session_id} 考试全局超时")
        return StreamingResponse(
                stream_generator(),
                headers={"Content-Type": "text/event-stream; charset=utf-8"}
            )

    # 未超时，判断逻辑
    # session从prepare_question返回，避免后续更新session时覆盖问题
    system_prompt, user_input, current_pk, current_time, flag, session = await prepare_question(messages, session_id,
                                                                                                embeddings,redis_client)
    mark_answer_in_progress(session_id, session, redis_client)
    chat_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": ""}
    ]

    # Resolve LLM config at runtime
    resolver = get_cached_config_resolver()
    resolved_llm = resolver.resolve(ModelConfigScope.SMART_PRACTICE_LLM)

    llm_client = AsyncOpenAI(
        api_key=resolved_llm.api_key.get_secret_value() if resolved_llm.api_key else "",
        base_url=resolved_llm.base_url,
    )

    try:
        chat_completion = await llm_client.chat.completions.create(
            model=resolved_llm.model,
            messages=chat_messages,
            temperature=0.1,
            stream=True,
            extra_body=get_llm_extra_body(resolved_llm.model)
        )
    except Exception:
        if session.get("answer_in_progress"):
            await complete_answer_processing(session_id, session, redis_client)
        raise
    total_model_time = 0
    async def stream_generator() -> AsyncGenerator[str, None]:
        nonlocal total_model_time
        full_response = ""
        answer_completed = False
        # 获取tokenizer
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo") if model_name else tiktoken.get_encoding("cl100k_base")
        start_model_time = time.time()  # 模型调用开始时间
        # 从Redis获取全局时间
        time_data = redis_client.hgetall(redis_time_key)
        start_time = datetime.fromisoformat(time_data["start_time"])
        time_limit = int(time_data["time_limit"])

        buffer = ""
        try:
            async for chunk in chat_completion:
                if await request.is_disconnected():
                    logger.info(f"Session {session_id} 客户端断开")
                    break

                if not chunk.choices:
                    continue

                delta = getattr(chunk.choices[0].delta, "content", None)
                if not delta:
                    continue

                if total_model_time == 0:
                    total_model_time += time.time() - start_model_time
                    logger.info(f"Session {session_id} 模型调用首个token时间: {total_model_time:.4f}s")

                full_response += delta
                buffer += delta

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    safe_line = line.replace("\n", "\\n") + "\\n"
                    yield f"data: {safe_line}\n"

            if buffer:
                safe_line = buffer.replace("\n", "\\n") + "\\n"
                yield f"data: {safe_line}\n"
            yield f"data: \n\n"

            total_model_time += time.time() - start_model_time
            logger.info(f"Session {session_id} 模型调用总时间: {total_model_time:.4f} 秒")

            elapsed = (datetime.now().astimezone() - start_time).total_seconds()

            yield "data: [DONE]\n\n"

            logging.info(f"Session {session_id} 题目 {current_pk} 完成")

            if "history_question_pks" not in session:
                session["history_question_pks"] = []
            session["history_question_pks"].append(current_pk)
            session["current_time"] = current_time + 1
            update_redis_session(session_id, session,redis_client)

            fail_meta = build_fail_metadata_time(
                session, current_time, flag,
                remaining_time, elapsed, time_limit,
                metadata_type="done"
            )
            yield f"data: {fail_meta}\n\n"
            yield "data: [METADATA DONE]\n\n"

            answer_completed = True
            await complete_answer_processing(
                session_id,
                session,
                redis_client,
                trigger_finish=current_time == session['new_total_time'] + 1
            )
        finally:
            if not answer_completed and session.get("answer_in_progress"):
                await complete_answer_processing(session_id, session, redis_client)

    return StreamingResponse(
        stream_generator(),
        headers={"Content-Type": "text/event-stream; charset=utf-8"}
    )


@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/api/exams/syn/answer",
    host="0.0.0.0", port=9010)
@register_statistics(names=["opea_service@train_llm"])
async def answer_dfxw(request: Request, input: TrainParams):  # 去掉显式StreamingResponse类型以便返回JSON
    """阻塞式输出，会话信息和考试时间均存储在Redis"""

    messages = input.messages
    session_id = input.session_id

    # Redis全局考试时间键
    redis_time_key = f"{TIME_REDIS_PREFIX}{session_id}"
    # 从Redis获取全局时间
    time_data = redis_client.hgetall(redis_time_key)
    if not time_data or "start_time" not in time_data:
        return {
            "status": 200,
            "message": "考试已结束！"
        }
    start_time = datetime.fromisoformat(time_data["start_time"])
    time_limit = int(time_data["time_limit"])

    # 计算全局剩余时间
    elapsed = (datetime.now().astimezone() - start_time).total_seconds()
    remaining_time = max(0, time_limit - elapsed)

    # 全局超时处理
    if remaining_time <= 0:
        # 超时阻塞式直接返回
        timeout_meta = build_fail_metadata_time(
            {}, "", "",
            remaining_time, elapsed, time_limit,
            metadata_type="timeout"
        )
        logger.info(f"Session {session_id} 考试全局超时")
        return {
            "status": 200,
            "message": "考试已结束！",
            "results": {
                "metadata": timeout_meta,
                "state": "TIMEOUT"
            }
        }

    # 未超时，准备题目（保持原逻辑）
    system_prompt, user_input, current_pk, current_time, flag, session = await prepare_question(messages, session_id, embeddings, redis_client)
    mark_answer_in_progress(session_id, session, redis_client)
    chat_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": ""}
    ]

    # Resolve LLM config at runtime
    resolver = get_cached_config_resolver()
    resolved_llm = resolver.resolve(ModelConfigScope.SMART_PRACTICE_LLM)

    llm_client = AsyncOpenAI(
        api_key=resolved_llm.api_key.get_secret_value() if resolved_llm.api_key else "",
        base_url=resolved_llm.base_url,
    )

    # 阻塞式模型调用
    start_model_time = time.time()
    try:
        chat_completion = await llm_client.chat.completions.create(
            model=resolved_llm.model,
            messages=chat_messages,
            extra_body=get_llm_extra_body(resolved_llm.model),
            temperature=0.1
        )
        total_model_time = time.time() - start_model_time
        full_response = ""
        if chat_completion and chat_completion.choices:
            full_response = getattr(chat_completion.choices[0].message, "content", "") or ""
        logger.info(f"Session {session_id} 模型调用总时间: {total_model_time:.4f} 秒")

        elapsed = (datetime.now().astimezone() - start_time).total_seconds()
        logging.info(f"Session {session_id} 题目 {current_pk} 完成")

        if "history_question_pks" not in session:
            session["history_question_pks"] = []
        session["history_question_pks"].append(current_pk)
        session["current_time"] = current_time + 1
        update_redis_session(session_id, session, redis_client)

        fail_meta = build_fail_metadata_time(
            session, current_time, flag,
            remaining_time, elapsed, time_limit,
            metadata_type="done"
        )

        await complete_answer_processing(
            session_id,
            session,
            redis_client,
            trigger_finish=current_time == session['new_total_time'] + 1
        )
    except Exception:
        if session.get("answer_in_progress"):
            await complete_answer_processing(session_id, session, redis_client)
        raise

    # 阻塞式一次性返回结果与元数据
    return {
        "status": 200,
        "message": "成功",
        "results": {
            "answer": full_response,
            "metadata": fail_meta,
            "model_time_seconds": round(total_model_time, 4)
        }
    }


@register_microservice(
    name="opea_service@train_llm",
    service_type=ServiceType.TRAIN,
    endpoint="/api/exams/finish",
    host="0.0.0.0", port=9010)
async def retry_qa_api(user_id: str = Body(...,description="user_id"),
                   exams_id : str = Body(...,description="考试id，start接口返回")
                ):

    """
        (东方希望)根据文档id，去更新这个文档对应的所有问答对
    """
    try:
        result = await finsh_exams(user_id,exams_id)
        status = result.get("status", 500)
        msg = result.get("message", "")
        data = result.get("results")
        return make_response(
            data=data,
            msg=msg,
            is_success=(status == 200),
            http_status_code=status
        )
    except Exception as e:
        traceback.print_exc()
        return make_response(
            data=None,
            msg=f"调用异常: {str(e)}",
            is_success=False,
            http_status_code=500
        )



def make_response(data=None, msg="操作成功", is_success=True, http_status_code=200):
    return {
        "http_status_code": http_status_code,
        "is_success": is_success,
        "msg": msg,
        "data": data,
        "trace_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

def redis_expiry_listener():
    pubsub = redis_client.pubsub()
    pubsub.psubscribe(f"__keyevent@{REDIS_DB}__:expired")
    for message in pubsub.listen():
        if message['type'] == 'pmessage':
            expired_key = message['data']
            if str(expired_key).startswith(TIME_REDIS_PREFIX):
                session_id = str(expired_key)[len(TIME_REDIS_PREFIX):]
                session = get_redis_session(session_id,redis_client)
                logger.info(f"redis监听------考试时间到达，处理考试结束 | session_id={session_id} | user_id={session.get('user_id')}")
                # 推送考试结束通知等
                asyncio.run(finish_and_push_exams_info(session.get('user_id'),session_id,redis_client))


# 全局变量保存事件循环和线程
_listener_loop: Optional[asyncio.AbstractEventLoop] = None
_listener_thread: Optional[threading.Thread] = None
_listener_shutdown = False


async def async_redis_expiry_listener():
    """异步监听器：高性能、不阻塞"""
    global _listener_shutdown

    async_redis = redis.asyncio.Redis(
        host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True
    )
    pubsub = async_redis.pubsub()

    try:
        await pubsub.psubscribe(f"__keyevent@{REDIS_DB}__:expired")
        logger.info("Exam Timer Listener (Async) started.")

        async for message in pubsub.listen():
            # 检查关闭标志
            if _listener_shutdown:
                logger.info("Listener shutdown signal received")
                break

            if message['type'] == 'pmessage':
                expired_key = message['data']
                if expired_key.startswith(TIME_REDIS_PREFIX):
                    session_id = expired_key[len(TIME_REDIS_PREFIX):]
                    session = get_redis_session(session_id, redis_client)
                    user_id = session.get('user_id')
                    if user_id:
                        logger.info(f"考试时间到 -> 触发自动交卷 | session_id={session_id}")
                        if session.get("answer_in_progress"):
                            logger.info(f"考试时间到但当前仍在判题，延后自动交卷 | session_id={session_id}")
                            session["pending_auto_submit"] = True
                            update_redis_session(session_id, session, redis_client)
                        else:
                            asyncio.create_task(finish_and_push_exams_info(user_id, session_id, redis_client))
    except asyncio.CancelledError:
        logger.info("Listener task cancelled")
    except Exception as e:
        logger.error(f"Listener error: {e}")
    finally:
        # 如果正在关闭程序，跳过清理操作避免 "cannot schedule new futures" 错误
        if _listener_shutdown:
            logger.debug("Skipping cleanup during shutdown")
            return

        # 正常情况下执行清理
        try:
            await pubsub.unsubscribe()
        except Exception as e:
            logger.debug(f"Error unsubscribing: {e}")

        try:
            # 使用新的 aclose() 方法（替代弃用的 close()）
            if hasattr(async_redis, 'aclose'):
                await async_redis.aclose()
            else:
                await async_redis.close()
        except Exception as e:
            logger.debug(f"Error closing redis: {e}")


def start_expiry_listener():
    """在独立线程中启动异步事件循环，支持优雅关闭"""
    global _listener_loop, _listener_thread

    def _run():
        global _listener_loop
        _listener_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_listener_loop)
        try:
            _listener_loop.run_until_complete(async_redis_expiry_listener())
        except asyncio.CancelledError:
            logger.info("Listener task cancelled")
        except Exception as e:
            logger.error(f"Listener thread error: {e}")
        finally:
            _listener_loop.close()

    _listener_thread = threading.Thread(target=_run, daemon=False)
    _listener_thread.start()


def shutdown_listener():
    """优雅关闭监听器"""
    global _listener_loop, _listener_thread, _listener_shutdown
    _listener_shutdown = True

    if _listener_loop and _listener_loop.is_running():
        _listener_loop.call_soon_threadsafe(_listener_loop.stop)

    if _listener_thread:
        _listener_thread.join(timeout=10)
        logger.info("Listener thread stopped")

# 注册关闭回调
atexit.register(shutdown_listener)
signal.signal(signal.SIGTERM, lambda s, f: shutdown_listener())

# ========== 启动 ==========
if __name__ == "__main__":
    if OVMS_EMBEDDING_ENDPOINT:
        from langchain_openai import OpenAIEmbeddings

        logger.info(f"OVMS_EMBEDDING_ENDPOINT:{OVMS_EMBEDDING_ENDPOINT}")

        # create embeddings using OVMS endpoint service
        embeddings = OpenAIEmbeddings(
            model=OVMS_EMBEDDING_MODEL,
            api_key="unused",
            base_url=OVMS_EMBEDDING_ENDPOINT,
            tiktoken_enabled=False,
            embedding_ctx_length=embedding_ctx_length
        )
        logger.debug(f"embeddings:{embeddings}")
    elif TEI_EMBEDDING_ENDPOINT:
        # create embeddings using TEI endpoint service
        logger.info(f"[ retriever_milvus ] TEI_EMBEDDING_ENDPOINT:{TEI_EMBEDDING_ENDPOINT}")
        embeddings = HuggingFaceHubEmbeddings(
            model=f"{TEI_EMBEDDING_ENDPOINT}/embed",  # 你的 TEI endpoint
            huggingfacehub_api_token="dummy"  # 随便填个 token（本地不用校验）
        )
    else:
        # create embeddings using local embedding model
        # Resolve Embedding config at runtime
        resolver = get_cached_config_resolver()
        resolved_embedding = resolver.resolve(ModelConfigScope.EMBEDDING)

        logger.info(f"[ prepare_execl_milvus ] BAILIAN_EMBEDDING_MODEL:{resolved_embedding.model}")
        embeddings = BailianEmbeddings(
            api_key=resolved_embedding.api_key.get_secret_value() if resolved_embedding.api_key else "",
            model=resolved_embedding.model,
            base_url=resolved_embedding.base_url or "",
            dimensions=1024,
        )
    # 初始化Redis连接
    redis_client = redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        decode_responses=True  # 让返回的字符串是 str 而不是 bytes
    )
    # 只启动一次监听器
    start_expiry_listener()

    opea_microservices["opea_service@train_llm"].start()
