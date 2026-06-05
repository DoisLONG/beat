# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import time
import traceback
import asyncio

from comps.oss_manager.minio_utils import download_minio_by_uri
from openai import OpenAI
from fastapi import HTTPException

from comps import CustomLogger
from comps.dataprep.celery_app import celery_app
from comps.dataprep.embeddings import embeddings
from comps.dataprep.mysql_client import MySQLClient
from comps.dataprep.loaders.loader import cleanup_tmp_dir, download_oss_to_temp
from comps.dataprep.loaders.selector import get_loader
from comps.dataprep.common.milvus_utils import ingest_qa_to_milvus, delete_milvus_by_filename_and_position_id
from comps.dataprep.common.schema import FileType
from comps.dataprep.sop_version_util import create_sop_version_filename
from comps.dataprep.service.universal_qa import batch_generate_universal_qa
from comps.dataprep.service.operation_manual_qa import batch_generate_operation_qa
from comps.dataprep.service.risk_generation_qa import batch_generate_risk_qa
from comps.dataprep.service.emergency_drill_qa import batch_generate_emergency_drill_qa
from comps.dataprep.config import (
    MYSQL_CONFIG,
    FILES_STORED_TYPE,
    DATA_LOADER_TYPE,
    COLLECTION_NAME,
    TOTAL_ROUNDS,
    get_client
)
from comps.dataprep.multilingual.route_policy import get_collection_name as get_lang_collection_name

logger = CustomLogger("dataprep-tasks", os.getenv("LOG_LEVEL", "INFO"))

def remove_duplicate_questions(qa_results):
    seen_questions = set()
    unique_qa_results = []
    for qa in qa_results:
        question = qa.get("题目")
        if question not in seen_questions:
            seen_questions.add(question)
            unique_qa_results.append(qa)
    return unique_qa_results

@celery_app.task(bind=True)
def extract_content_task(self, file_uri: str, filename: str, sop_id: int, file_type: str = "sop",
                         lang: str = "zh"):
    """负责从 OSS / Minio 读取文件并解析为结构化列表。

    Args:
        lang: 业务语种（由 JWT.lang 决定），决定回写哪张语种表
    """
    logger.info(f"开始解析任务: {filename}, URI: {file_uri}, lang: {lang}")
    db_client = MySQLClient(MYSQL_CONFIG)
    tmp_dir = None

    try:
        db_client.update_percent_by_id(sop_id, "20%", lang=lang)

        local_file_path = file_uri
        if FILES_STORED_TYPE == "oss":
            logger.info(f"从 OSS 下载文件: {file_uri}")
            tmp_dir, local_file_path = asyncio.run(download_oss_to_temp(file_uri, filename))
        elif FILES_STORED_TYPE == "minio":
            logger.info(f"从 minio 存储下载文件: {file_uri}")
            tmp_dir, local_file_path = asyncio.run(download_minio_by_uri(file_uri))
        else:
            logger.info(f"使用本地文件路径或minio存储路径: {file_uri}")

        file_ext = os.path.splitext(filename)[1].lstrip(".").lower()
        logger.info(f"开始进行内容提取，类型:{file_type},文件:{filename}")
        embeddings.ensure_latest()
        loader = asyncio.run(get_loader(file_type, file_ext, DATA_LOADER_TYPE))
        client = get_client()
        structured_rows, lang_detected = asyncio.run(
            loader.load_data(local_file_path, embeddings=embeddings, db_client=db_client,
                             sop_id=sop_id, client=client, lang=lang)
        )

        logger.debug(f"结构化数据提取成功，共 {len(structured_rows)} 行")

        # 请求语种与识别语种不一致时，记录 warning（不改变路由决策）
        if lang_detected and lang_detected != lang:
            logger.warning(
                f"[lang_mismatch] sop_id={sop_id}, filename={filename}, "
                f"请求语种={lang}, 识别语种={lang_detected}. "
                f"以请求语种 {lang} 为准落表，识别结果仅记录。"
            )

        sop_info_update_obj = {
            "lang": lang_detected or lang,   # lang 字段记录识别结果，用于审计
            "percent": "50%"
        }

        if not db_client.update_sop_info(sop_id=sop_id, data=sop_info_update_obj, lang=lang):
            return {"status": 500, "message": "SOP信息更新失败"}

        return {"structured_rows": structured_rows, "lang": lang, "lang_detected": lang_detected}
    except Exception as e:
        logger.error(f"解析任务失败: {traceback.format_exc()}")
        db_client.update_sops(sop_id=sop_id, task_status="FAILURE", remark=f"解析失败: {str(e)}", lang=lang)
        raise self.retry(exc=e, countdown=5, max_retries=3)
    finally:
        if tmp_dir:
            cleanup_tmp_dir(tmp_dir)

@celery_app.task(bind=True)
def process_excel_task(self, data_dict: dict, filename: str, position_id: str, user_prompt: str, file_type: str,
                       sop_id: int, exit_flag: bool = False, scope_type="all", lang: str = "zh"):
    """处理 Excel 文件 -> 生成 QA -> 入库。

    Args:
        lang: 业务语种（由 JWT.lang 决定），决定写入哪张语种表和哪个 Milvus 集合
    """
    db_client = MySQLClient(MYSQL_CONFIG)
    time.sleep(0.5)
    results = {"file": filename}
    try:
        if isinstance(data_dict, dict) and "structured_rows" in data_dict:
            structured_rows = data_dict["structured_rows"]
            # lang 参数（JWT.lang）是路由决策依据；data_dict 中的 lang 是识别结果，仅供参考
            lang_detected = data_dict.get("lang_detected") or data_dict.get("lang", lang)
        else:
            structured_rows = None
            lang_detected = lang

        if not structured_rows:
            results["error"] = "Excel 文件无有效数据"
            raise HTTPException(status_code=500, detail=f"Excel 文件无有效数据")

        logger.info(f"{filename} 成功结构化抽取，共 {len(structured_rows)} 条数据，路由语种: {lang}")
        embeddings.ensure_latest()
        client = get_client()

        qa_results = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        
        content_lang = lang_detected if lang_detected in ("zh", "en", "th") else lang

        if file_type == FileType.SOP:
            qa_results, total_prompt_tokens, total_completion_tokens = asyncio.run(
                batch_generate_universal_qa(structured_rows, filename, client, user_prompt, sop_id, db_client,
                                            content_lang, scope_type))
        elif file_type == FileType.RISK:
            qa_results, total_prompt_tokens, total_completion_tokens = asyncio.run(
                batch_generate_risk_qa(structured_rows, filename, client, user_prompt, sop_id, db_client, content_lang))
        elif file_type == FileType.OPERATION:
            qa_results, total_prompt_tokens, total_completion_tokens = asyncio.run(
                batch_generate_operation_qa(structured_rows, filename, client, user_prompt, sop_id, db_client, content_lang, scope_type))
        elif file_type == FileType.EMERGENCY_DRILL:
            qa_results, total_prompt_tokens, total_completion_tokens = asyncio.run(
                batch_generate_emergency_drill_qa(structured_rows, filename, client, user_prompt, sop_id, db_client,
                                                  content_lang))

        if len(qa_results) > 0:
            deduped_results = remove_duplicate_questions(qa_results)
            logger.info(f"去重后的数据----:{deduped_results}")
        else:
            deduped_results = qa_results
            
        logger.info(f"{filename} 模型生成完成")

        # 若文件已存在，先删除对应语种集合中的旧向量
        if exit_flag:
            delete_milvus_by_filename_and_position_id(sop_id, lang=lang)

        # 写入对应语种 Milvus 集合
        collection_name = get_lang_collection_name(lang)
        qa_content = ingest_qa_to_milvus(filename, collection_name, deduped_results, position_id, embeddings, sop_id)
        logger.info(f"{filename} 插入 Milvus 集合 {collection_name} 成功")

        results["qa_results"] = deduped_results
        tokens_usage = {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens
        }
        logger.info(f"{filename} 总token使用量: {tokens_usage}")

        result = create_sop_version_filename(qa_content, filename, sop_id=sop_id, lang=lang)
        db_client.update_sops(sop_id=sop_id, task_status="SUCCESS", lang=lang)

        if len(qa_results) >= TOTAL_ROUNDS:
            db_client.update_sop_info_num_flag(sop_id=sop_id, num_flag=1, lang=lang)
            
        db_client.update_percent_by_id(sop_id, "100%", lang=lang)

        return {
            "status": "success",
            "sop_id": sop_id,
            "filename": filename,
            "qa_count": len(deduped_results)
        }

    except Exception as e:
        error_msg = f"生成任务异常: {traceback.format_exc()}"
        logger.error(error_msg)
        db_client.update_sops(sop_id=sop_id, task_status="FAILURE", remark=f"{filename} 生成失败---{e}", lang=lang)
        raise self.retry(exc=e, countdown=10, max_retries=3)
