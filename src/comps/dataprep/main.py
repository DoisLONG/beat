# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import time
import traceback
from datetime import datetime
from typing import List, Optional, Union, Dict

from fastapi import Body, Request, File, UploadFile, Form, Path, HTTPException
from langchain_milvus.vectorstores import Milvus
from langchain_core.documents import Document

from comps import CustomLogger, opea_microservices, register_microservice
from comps.account.auth import require_auth_dict, verify_token
from comps.dataprep.celery_app import celery_app
from comps.dataprep.common.milvus_utils import (
    check_milvus_has_file,
    insert_into_milvus,
    get_lang_collection_name,
)
from comps.dataprep.common.schema import make_response
from comps.dataprep.config import (
    MILVUS_HOST,
    MILVUS_PORT,
    MYSQL_CONFIG,
    FILES_STORED_TYPE,
)
from comps.dataprep.embeddings import embeddings
from comps.dataprep.mysql_client import MySQLClient
from comps.dataprep.prompt import auto_load_prompts
from comps.dataprep.tasks import extract_content_task, process_excel_task
from comps.dataprep.utils import create_upload_folder, save_upload_file
from comps.oss_manager.minio_utils import save_upload_file_minio
from comps.dataprep.sop_version_util import create_sop_version
from celery import chain
from comps.oss_manager import oss_manager, minio_utils

logger = CustomLogger("dataprep-main", os.getenv("LOG_LEVEL", "INFO"))

SUPPORTED_LANGS = {"zh", "en", "th"}

MILVUS_URI = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
CONNECTION_ARGS = {"uri": MILVUS_URI}
UPLOAD_FOLDER = "./uploaded_files"


def _normalize_lang(lang: Optional[str]) -> str:
    if lang in SUPPORTED_LANGS:
        return lang
    return "zh"


def _resolve_request_lang(request: Request, user: Optional[Dict] = None) -> str:
    if isinstance(user, dict):
        return _normalize_lang(user.get("lang"))

    auth_header = request.headers.get("Authorization") or ""
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            token_data = verify_token(token)
            return _normalize_lang(getattr(token_data, "lang", None))
        except Exception:
            logger.warning("resolve lang from JWT failed, fallback to zh")
    return "zh"

# ----------------------------------------------------------------------------------------------------------------------
# API Endpoints
# ----------------------------------------------------------------------------------------------------------------------

@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/task_status",
    host="0.0.0.0",
    port=6010,
)
async def get_task_status(request: Request, task_id: str = Body(..., embed=True)):
    lang = _resolve_request_lang(request)
    # 初始化 MySQLClient 单例
    db_client = MySQLClient(MYSQL_CONFIG)
    result = db_client.query_sops_by_task_id(task_id, lang=lang)
    if not result:
        return {"status": 404, "message": "任务不存在"}
    if result["task_status"] == "SUCCESS":
        return {"status": 200, "message": "任务完成",
                "results": {"task_id": task_id, "state": "SUCCESS", "result": "SUCCESS", "percent": "100%"},
                "lang": lang}
    elif result["task_status"] == "PENDING":
        return {"status": 200, "message": "任务等待中",
                "results": {"task_id": task_id, "state": "PENDING", "percent": result["percent"]},
                "lang": lang}
    else:
        return {"status": 200, "message": "任务失败",
                "results": {"task_id": task_id, "state": "FAILURE", "percent": "100%",
                            "error": result.get("remark", "未知原因")},
                "lang": lang}


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/generate_qa",
    host="0.0.0.0",
    port=6010,
)
@require_auth_dict()  # 添加认证装饰器
async def generate_qa(
        request: Request,  # 添加request参数
        files: Optional[Union[UploadFile, List[UploadFile]]] = File(...),
        file_type: str = Form("sop", description="文件类型(sop/risk/operation/emergency_drill)"),
        position_id: str = Form(..., description="岗位ID（必传"),
        strategy:str = Form(default="all",description="选择策略，all，step、error、data"),
        start_time:str = Form(...,description="开始时间，格式为YYYY-MM-DD"),
        end_time:str = Form(...,description="结束时间，格式为YYYY-MM-DD"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    """生成QA问答对（包含租户验证）"""
    lang = _resolve_request_lang(request, user)

    # 验证用户认证
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    # 获取租户ID
    tenant_id = user.get('tenant_id')
    if not tenant_id:
        return {"status": 400, "message": "用户未关联租户", "results": None}

    # 基础参数验证
    if not position_id:
        return {"status": 400, "message": "岗位ID不能为空", "results": None}

    if (
            not files
            or (isinstance(files, list) and all((not f.filename) or (getattr(f, "size", 0) == 0) for f in files))
            or (isinstance(files, UploadFile) and ((not files.filename) or (getattr(files, "size", 0) == 0)))
    ):
        return {"status": 400, "message": "上传文件不能为空", "results": None}

    file_list = files if isinstance(files, list) else [files]
    logger.info(f"[{datetime.now()}] 租户【{tenant_id}】调用接口/v1/dataprep/generate_qa，岗位为{position_id}，语种={lang}")

    try:
        # 初始化 MySQLClient 单例
        db_client = MySQLClient(MYSQL_CONFIG)

        # 验证租户是否存在且有效
        tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
        if not tenant or tenant.get('status') != 1:
            return {"status": 400, "message": f"租户ID【{tenant_id}】不存在或已停用", "results": None}

        task_ids = []
        sop_ids = []

        for file in file_list:
            # 1. 按照存储类型完成上传，并确定实际存储文件名和 URI
            filename = file.filename
            if FILES_STORED_TYPE == "minio":
                _, _, file_uri = await save_upload_file_minio(file, position_id)
            elif FILES_STORED_TYPE == "oss":
                _, _, file_uri = await oss_manager.oss_upload(file, position_id)
            else:
                # 本地存储逻辑
                file_uri = await save_upload_file(file, UPLOAD_FOLDER)

            # 2. 按语种查重（MySQL 语种表 + Milvus 语种集合）
            embeddings.ensure_latest()
            exit_flag = await check_milvus_has_file(
                file_name=filename, position_id=position_id, embeddings=embeddings, lang=lang
            )

            # 保证 position_info 的查询逻辑正确
            position_info = db_client.query_position_by_id(int(position_id), lang=lang)
            current_tenant_id = position_info.get("tenant_id") if position_info else tenant_id

            if not exit_flag:
                # 插入 SOP 记录到对应语种表
                sop_id = db_client.insert_sops(
                    title=os.path.splitext(file.filename)[0],
                    filename=file.filename,
                    file_uri=file_uri,
                    position_id=position_id,
                    file_type=file_type,
                    tenant_id=current_tenant_id,
                    start_time=start_time,
                    end_time=end_time,
                    lang=lang,
                )
            else:
                sop_id = db_client.query_sop_id_by_filename_and_position_id(
                    file.filename, position_id, current_tenant_id, lang=lang
                )

            sop_ids.append(sop_id)
            db_client.update_percent_by_id(sop_id, "0%", lang=lang)
            db_client.update_percent_by_id(sop_id, "10%", lang=lang)

            # 3. 发起 Celery 任务链，显式传入 lang
            task_extract = extract_content_task.s(
                file_uri=file_uri,
                filename=filename,
                sop_id=sop_id,
                file_type=file_type,
                lang=lang,
            )
            task_generate = process_excel_task.s(
                filename=filename,
                position_id=position_id,
                user_prompt="",
                file_type=file_type,
                sop_id=sop_id,
                exit_flag=exit_flag,
                scope_type=strategy,
                lang=lang,
            )

            workflow = chain(task_extract | task_generate)
            result = workflow.apply_async()
            task_ids.append(result.id)

            db_client.update_taskid_and_status(sop_id=sop_id, task_id=result.id, task_status="PENDING", lang=lang)

        return {"status": 200, "message": "成功", "results": {"task_ids": task_ids, "sop_ids": sop_ids}, "lang": lang}
    except HTTPException as e:
        logger.error(f"处理失败: {traceback.format_exc()}---{e.detail}")
        return {"status": e.status_code, "message": f"处理失败: {e.detail}"}
    except Exception as e:
        logger.error(f"处理失败: {traceback.format_exc()}---{e}")
        return {"status": 500, "message": f"处理失败: {e}"}


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/sop/type/add",
    host="0.0.0.0",
    port=6010,
)
async def add_sop_type(
        sop_type_name: str = Body(..., embed=True, description="SOP类型名称")
):
    # 初始化MySQL客户端
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        existing = db_client.query_sop_existing(sop_type_name=sop_type_name)
        if existing:
            return {
                "status": 400,
                "message": f"SOP类型已存在: {sop_type_name}",
                "results": None
            }
        db_client.insert_sop_type(sop_type_name)

        return {
            "status": 200,
            "message": "SOP类型新增成功",
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"新增失败: {str(e)}",
            "results": None
        }


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/sop/type/query_all",
    host="0.0.0.0",
    port=6010,
)
async def query_all_sop_type():
    # 初始化MySQL客户端
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        results = db_client.query_all_sop_type()

        return {
            "status": 200,
            "message": "查询所有SOP类型成功",
            "results": {
                "total": len(results),  # 总记录数
                "list": results  # 所有类型列表，包含sop_type_id和sop_type_name
            }
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"查询所有SOP类型失败: {str(e)}",
            "results": None
        }


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/sop/type/delete",
    host="0.0.0.0",
    port=6010,
)
async def delete_sop_type(
        sop_type_id: int = Body(..., embed=True, description="SOP类型ID（必传，用于指定删除的类型）")
):
    # 初始化MySQL客户端
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 先校验该类型是否存在
        existing = db_client.query_sop_existing_id(sop_type_id=sop_type_id)
        if not existing:
            return {
                "status": 404,
                "message": f"未找到ID为{sop_type_id}的SOP类型，无法删除",
                "results": None
            }

        db_client.delete_sop_type(sop_type_id=sop_type_id)

        return {
            "status": 200,
            "message": f"ID为{sop_type_id}的SOP类型删除成功",
            "results": {
                "deleted_sop_type_id": sop_type_id
            }
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"删除SOP类型失败: {str(e)}",
            "results": None
        }


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/sop/type/update",
    host="0.0.0.0",
    port=6010,
)
async def update_sop_type(
        sop_type_id: int = Body(..., embed=True, description="SOP类型ID（必传，用于指定修改的类型）"),
        new_sop_type_name: str = Body(..., embed=True, description="新的SOP类型名称（必传）")
):
    # 初始化MySQL客户端
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 先校验该类型是否存在
        existing = db_client.query_sop_existing_id(sop_type_id=sop_type_id)
        if not existing:
            return {
                "status": 404,
                "message": f"未找到ID为{sop_type_id}的SOP类型，无法修改",
                "results": None
            }

        # 2. 校验新名称是否已被其他类型使用（排除当前ID）
        duplicate = db_client.check_duplicate_sop_type(new_sop_type_name=new_sop_type_name, sop_type_id=sop_type_id)
        if duplicate:
            return {
                "status": 400,
                "message": f"SOP类型名称'{new_sop_type_name}'已存在，请更换名称",
                "results": None
            }

        # 3. 执行更新操作
        db_client.update_sop_type(new_sop_type_name=new_sop_type_name, sop_type_id=sop_type_id)

        # 4. 返回更新后的信息
        return {
            "status": 200,
            "message": f"ID为{sop_type_id}的SOP类型修改成功"
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"修改SOP类型失败: {str(e)}",
            "results": None
        }


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/qa/retry",
    host="0.0.0.0",
    port=6010,
)
@require_auth_dict()
async def retry_generate_qa(
        request: Request,
        id: int = Body(..., embed=True, description="sop_id"),
        file_type: str = Body("sop", embed=True, description="文件类型(sop/risk/operation/emergency_drill)"),
        position_id: str = Body(..., embed=True, description="岗位id"),
        strategy: str = Form(default="all", description="选择策略，all，step、error、data"),
        user: Dict = None,
):
    lang = _resolve_request_lang(request, user)

    # 基础参数验证
    if not id:
        return {"status": 400, "message": "SOP_ID不能为空", "results": None}
    try:
        # 初始化 MySQLClient 单例
        db_client = MySQLClient(MYSQL_CONFIG)
        # 根据 sop_id 在对应语种表中获取 SOP 信息
        sop_info = db_client.query_sop_info_by_id(id, lang=lang)
        if not sop_info:
            return {"status": 404, "message": f"SOP ID {id} 在语种 {lang} 中不存在", "results": None}

        filename = sop_info.get("filename")
        file_uri = sop_info.get("file_uri")

        # 先删除对应语种集合中的旧 QA 向量
        collection_name = get_lang_collection_name(lang)
        client = Milvus(
            embedding_function=embeddings,
            collection_name=collection_name,
            connection_args={"uri": MILVUS_URI}
        )
        client.delete(expr=f"sop_id == {id}")

        task_ids = []
        sop_ids = []
        db_client.update_percent_by_id(id, "0%", lang=lang)

        if not file_uri:
            if FILES_STORED_TYPE == "minio":
                file_uri = await minio_utils.get_uri_by_filename(filename, position_id)
            elif FILES_STORED_TYPE == "oss":
                file_uri = await oss_manager.get_uri_by_filename(filename, position_id)
            else:
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file_uri = file_path
                if not os.path.exists(file_path):
                    return {"status": 400, "message": f"文件【{filename}】不存在，无法重试", "results": None}

        db_client.update_percent_by_id(id, "10%", lang=lang)

        # 执行解析流程，显式传入 lang
        task_extract = extract_content_task.s(
            file_uri=file_uri,
            filename=filename,
            sop_id=id,
            file_type=file_type,
            lang=lang,
        )
        task_generate = process_excel_task.s(
            filename=filename,
            position_id=position_id,
            user_prompt="",
            file_type=file_type,
            sop_id=id,
            exit_flag=True,
            scope_type=strategy,
            lang=lang,
        )

        workflow = chain(task_extract | task_generate)
        result = workflow.apply_async()
        task_ids.append(result.id)

        db_client.update_taskid_and_status(sop_id=id, task_id=result.id, task_status="PENDING", lang=lang)
        return {"status": 200, "message": "成功", "results": {"task_ids": task_ids, "sop_ids": sop_ids}, "lang": lang}
    except HTTPException as e:
        logger.error(f"处理失败: {traceback.format_exc()}---{e.detail}")
        return {"status": e.status_code, "message": f"处理失败: {e.detail}"}
    except Exception as e:
        logger.error(f"处理失败: {traceback.format_exc()}---{e}")
        return {"status": 500, "message": f"处理失败: {e}"}

@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/sops",
    host="0.0.0.0",
    port=6010,
)
@require_auth_dict()  # 添加认证装饰器
async def excels(
        request: Request,  # 添加request参数以获取用户信息
        page: int = Body(1, embed=True),
        page_size: int = Body(10, embed=True),
        keyword: str = Body("", embed=True),
        company_id: int = Body(None, embed=True),
        department_id: int = Body(None, embed=True),
        position_id: str = Body(None, embed=True),
        user: Dict = None  # 从装饰器注入的用户信息
):
    """分页查询SOP列表（包含租户筛选）"""
    lang = _resolve_request_lang(request, user)

    # 验证用户认证
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    # 获取租户ID
    tenant_id = user.get('tenant_id')
    if not tenant_id:
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    try:
        # 初始化 MySQLClient 单例
        db_client = MySQLClient(MYSQL_CONFIG)

        # 验证租户是否存在且有效
        tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
        if not tenant or tenant.get('status') != 1:
            return {
                "status": 400,
                "message": f"租户ID【{tenant_id}】不存在或已停用",
                "results": None
            }

        # 执行查询（传递租户ID 和语种）
        result = db_client.query_sops_list_paginated(
            tenant_id=tenant_id,
            keyword=keyword,
            page=page,
            page_size=page_size,
            company_id=company_id,
            department_id=department_id,
            position_id=user.get("position_id") if user else None,
            lang=lang,
        )

        # 添加租户信息到返回结果
        result["tenant_id"] = tenant_id
        result["message"] = "查询成功"
        result["lang"] = lang

        return {
            "status": 200,
            "message": "成功",
            "results": result
        }
    except Exception as e:
        logger.error(f"查询SOP列表失败: {traceback.format_exc()}---{e}")
        return {
            "status": 500,
            "message": f"查询失败: {str(e)}",
            "results": None
        }


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/qa/list",
    host="0.0.0.0",
    port=6010,
)
async def qa_list(request: Request, id: int = Body(..., embed=True, description="sop_id")):
    lang = _resolve_request_lang(request)
    collection_name = get_lang_collection_name(lang)

    client = Milvus(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args=CONNECTION_ARGS
    )
    documents = client.similarity_search_with_score(
        query="1", embedding_function=embeddings, k=1000, expr=f'sop_id == {id}'
    )
    results = []
    if documents:
        # 封装返回体
        results = [
            {"id": str(document[0].metadata.get("pk")),
             "row": document[0].metadata.get("excel_row"),
             "position": document[0].metadata.get("location"),
             "question": document[0].page_content,
             "answer": document[0].metadata.get("answer"),
             "content": document[0].metadata.get("content"),
             "type": document[0].metadata.get("question_type"),
             "difficulty_factor": document[0].metadata.get("difficulty_factor"),
             "position_id": document[0].metadata.get("position_id"),
             } for document in documents]
    return {"status": 200, "message": "成功", "results": results, "lang": lang}

@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/qa/save",
    host="0.0.0.0",
    port=6010,
)
async def update(request: Request,
                 records: List[dict] = Body(..., embed=True),
                 sop_info_id: int = Body(None, embed=True, description="sop_info_id")):
    lang = _resolve_request_lang(request)

    db_client = MySQLClient(MYSQL_CONFIG)
    sop_info = db_client.query_sop_info_by_id(sop_info_id, lang=lang)
    if not sop_info:
        return {"status": 404, "message": "SOP 不存在"}
    filename = sop_info.get("filename")
    # 必要字段校验
    required_fields = ["answer", "content", "question"]
    for record in records:
        missing_fields = [field for field in required_fields if not record.get(field)]
        if missing_fields:
            return {"status": 500, "message": f"记录中缺少必要字段: {', '.join(missing_fields)}", "record": record}

    # 删除对应语种集合中的旧 QA
    collection_name = get_lang_collection_name(lang)
    client = Milvus(embedding_function=embeddings, collection_name=collection_name, connection_args=CONNECTION_ARGS)
    client.delete(expr=f"sop_id == {sop_info_id}")

    # 重建 Document 列表
    documents = []
    for record in records:
        metadata = {
            "filename": filename,
            "excel_row": record.get("row", " "),
            "location": record.get("position", "手动输入无位置定位信息"),
            "answer": record.get("answer"),
            "content": record.get("content"),
            "question_type": record.get("type", "未知类型"),
            "difficulty_factor": record.get("difficulty_factor", 0),
            "position_id": record.get("position_id", 0),
            "sop_id": sop_info_id
        }
        documents.append(Document(page_content=record.get("question"), metadata=metadata))

    # 写入对应语种集合
    await insert_into_milvus(documents, embeddings=embeddings, lang=lang)
    await create_sop_version(sop_info_id, records, lang=lang)
    return {"status": 200, "message": "成功", "result": "修改成功", "lang": lang}

@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/delete_sop",
    host="0.0.0.0",
    port=6010,
)
async def delete_qa(
        request: Request,
        sop_record_id: int = Body(..., embed=True, description="sop_record_id"),
):
    lang = _resolve_request_lang(request)

    # 初始化 MySQLClient 单例
    db_client = MySQLClient(MYSQL_CONFIG)
    filename = None
    try:
        sop_record = db_client.query_sop_info_by_id(sop_record_id, lang=lang)
        if not sop_record:
            return {"status": 404, "message": f"SOP {sop_record_id} 在语种 {lang} 中不存在"}
        filename = sop_record.get('filename')
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        task_status = sop_record.get("task_status")
        if task_status == "PENDING":
            return {
                "status": 400,
                "message": f"SOP '{sop_record.get('filename')}' 任务尚未完成，无法删除"
            }

        # 删除对应语种集合中的 QA 向量
        collection_name = get_lang_collection_name(lang)
        client = Milvus(
            embeddings,
            collection_name=collection_name,
            connection_args=CONNECTION_ARGS
        )
        all_collections = client._milvus_client.list_collections()

        # 检查集合是否存在
        if collection_name not in all_collections:
            return {
                "status": 404,
                "message": f"集合 '{collection_name}' 不存在，请检查集合名称是否正确"
            }

        # 执行 Milvus 删除
        delete_filter = f"sop_id == {sop_record_id}"
        s_time = time.time()
        result = client.delete(expr=delete_filter)
        e_time = time.time()

        # 删除本地文件
        if os.path.exists(file_path):
            os.remove(file_path)

        logger.info(
            f"[ delete_qa ] 删除 {collection_name} 中 {filename} 的数据完成，"
            f"耗时: {e_time - s_time:.4f} seconds"
        )

        # 删除语种表中的 SOP 记录
        db_client.delete_sops(sop_id=sop_record_id, lang=lang)

        # 删除版本中和此sop_id相关的记录
        db_client.delete_sop_version(sop_id=sop_record_id, lang=lang)

        return {
            "status": 200,
            "message": "成功",
            "result": {
                "id": sop_record_id,
                "filename": filename
            },
            "lang": lang
        }
    except HTTPException as he:
        logger.error(f"操作错误: {he.detail}")
        return {
            "status": 500,
            "message": f"删除失败---{he.detail}"
        }
    except Exception as e:
        logger.error(
            f"删除 {filename} 的数据失败: {traceback.format_exc()}---{str(e)}"
        )
        return {
            "status": 500,
            "message": f"删除{filename} 的数据失败"
        }


@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/sops/record/update",
    host="0.0.0.0",
    port=6010,
)
async def update_sop_title(
        request: Request,
        record_id: int = Body(..., embed=True),
        title: str = Body(..., embed=True),
        position_id: Union[int, str] = Body(None, embed=True)
):
    lang = _resolve_request_lang(request)

    # 初始化 MySQLClient 单例
    db_client = MySQLClient(MYSQL_CONFIG)

    # 调用更新方法（操作对应语种表）
    success = db_client.update_title_by_id(record_id, title, position_id, lang=lang)

    if success:
        return {"status": 200, "message": "更新成功", "results": {"record_id": record_id, "title": title}, "lang": lang}
    else:
        return {"status": 404, "message": "更新失败，记录不存在或更新异常", "results": None}

@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/v1/dataprep/organization/{user_id}",
    host="0.0.0.0",
    port=6010,
    methods=['get']
)
async def get_organization_tree(request: Request, user_id: Union[int, str] = Path(..., description="用户ID")):
    """获取当前用户的组织架构树(仅包含在对应语种表 sop_info 中存在的岗位)"""
    lang = _resolve_request_lang(request)

    try:
        # 将用户ID转换为整数
        try:
            user_id_int = int(user_id)
        except ValueError:
            return {
                "status": 400,
                "message": "用户ID必须是有效的整数",
                "results": []
            }

        db_client = MySQLClient(MYSQL_CONFIG)
        tree = db_client.query_organization_tree(user_id_int, lang=lang)

        return {
            "status": 200,
            "message": "查询成功",
            "results": tree,
            "lang": lang
        }
    except Exception as e:
        logger.error(f"获取组织架构树失败: {e}")
        return {
            "status": 500,
            "message": f"查询失败: {str(e)}",
            "results": []
        }

@register_microservice(
    name="opea_service@prepare_execl_milvus",
    endpoint="/api/sop/upload",
    host="0.0.0.0",
    port=6010,
)
@require_auth_dict()  # 添加认证装饰器
async def sop_generate_qa(
        request: Request,
        files: Optional[Union[UploadFile, List[UploadFile]]] = File(...),
        file_type: str = Form("sop", description="文件类型(sop/risk/operation/emergency_drill)"),
        position: str = Form(..., description="岗位ID（必传"),
        strategy: str = Form("all", description="选择策略，all，step、error、data"),
        user: Dict = None,
):
    """
    (东方希望)在指定的文件类型和岗位下，进行文件/文件列表的上传
    返回：
        文档id：sop_id
        问答对生成任务id：task_id
    """
    file_list = files if isinstance(files, list) else [files]
    file_names = [f.filename for f in file_list]
    logger.info(f"[{datetime.now()}] 调用接口/api/sop/upload，参数为：files={file_names}, 岗位为{position}")
    try:
        # 调用内部逻辑（request 传入以确保语种一致）
        result = await generate_qa(request=request, files=files, file_type=file_type, position_id=position, user=user)
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
    name="opea_service@prepare_execl_milvus",
    endpoint="/api/sop/status/{id}",
    host="0.0.0.0",
    port=6010,
    methods=["get"]
)
async def get_sop_task_status(request: Request, id: int = Path(description="sop_id")):
    """
        (东方希望)根据文档id，去获取当前生成任务的状态
    """
    try:
        lang = _resolve_request_lang(request)
        db_client = MySQLClient(MYSQL_CONFIG)
        sop_info = db_client.query_sop_info_by_id(id, lang=lang)
        result = await get_task_status(request, sop_info.get("task_id"))
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
    name="opea_service@prepare_execl_milvus",
    endpoint="/api/sop/search/{id}",
    host="0.0.0.0",
    port=6010,
    methods=["get"]
)
async def search_sop(request: Request, id: int = Path(..., description="sop_id")):
    """
        (东方希望)根据文档id，去获取当前生成任务的状态
    """
    try:
        result = await qa_list(request, id)
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
    name="opea_service@prepare_execl_milvus",
    endpoint="/api/sop/edit_qa",
    host="0.0.0.0",
    port=6010,
)
async def edit_sop(request: Request, id: int = Body(..., description="sop_id"), records: List = Body(..., description="问答对列表")):
    """
        (东方希望)根据文档id，去更新这个文档对应的所有问答对
    """
    try:
        result = await update(request=request, records=records, sop_info_id=id)
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
    name="opea_service@prepare_execl_milvus",
    endpoint="/api/sop/delete_SOP/{id}",
    host="0.0.0.0",
    port=6010,
    methods=["delete"]
)
async def delete_sop(request: Request, id: int = Path(..., description="sop_id")):
    """
        (东方希望)根据文档id，去删除这个文档对应的所有问答对以及文档记录本身
    """
    try:
        result = await delete_qa(request, id)
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
    name="opea_service@prepare_execl_milvus",
    endpoint="/api/sop/retry_qa",
    host="0.0.0.0",
    port=6010,
)
@require_auth_dict()
async def retry_qa(
        request: Request,
        id: int = Body(..., description="sop_id"),
        file_type: str = Body("sop", description="文件类型(sop/risk/operation/emergency_drill)"),
        position_id: str = Body(..., description="岗位类型ID（必传"),
        user_prompt: str = Body("", description="用户输入生成要求"),
        user: Dict = None,
):
    """
        (东方希望)根据文档id，去更新这个文档对应的所有问答对
    """
    try:
        result = await retry_generate_qa(
            request=request,
            id=id,
            file_type=file_type,
            position_id=position_id,
            strategy=user_prompt,
            user=user,
        )
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


# ----------------------------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    create_upload_folder(UPLOAD_FOLDER)
    opea_microservices["opea_service@prepare_execl_milvus"].start()
    # 注意：Worker 应该单独启动，或者在这里启动
    # celery_app.worker_main(argv=["worker", "--loglevel=info"])
    # 保持原有启动方式
    auto_load_prompts()
    celery_app.start(argv=["worker", f"--loglevel={os.getenv('LOG_LEVEL', 'INFO').lower()}"])
