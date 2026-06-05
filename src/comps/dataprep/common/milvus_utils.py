# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import time
from typing import List
from langchain_core.documents import Document
from langchain_milvus.vectorstores import Milvus
from pymilvus import MilvusClient

from comps import CustomLogger
from comps.dataprep.mysql_client import MySQLClient
from comps.dataprep.config import (
    COLLECTION_NAME,
    MILVUS_HOST,
    MILVUS_PORT,
    MYSQL_CONFIG
)
from fastapi import HTTPException

logger = CustomLogger("dataprep-milvus-utils", os.getenv("LOG_LEVEL", "INFO"))

# 常量定义
MILVUS_URI = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
CONNECTION_ARGS = {"uri": MILVUS_URI}
INDEX_PARAMS = {"index_type": "FLAT", "metric_type": "L2", "params": {}}
PARTITION_FIELD_NAME = "filename"
UPLOAD_FOLDER = "./uploaded_files/"
BATCH_SIZE = 10
MILVUS_VARCHAR_MAX_LEN = int(os.getenv("MILVUS_VARCHAR_MAX_LEN", "65535"))
MILVUS_SAFE_VARCHAR_LEN = min(
    int(os.getenv("MILVUS_SAFE_VARCHAR_LEN", "60000")),
    MILVUS_VARCHAR_MAX_LEN,
)

# ——— 多语种集合路由（集合名白名单，防止注入）———
# zh 复用现有生产集合（由 COLLECTION_NAME 环境变量决定），历史向量数据零迁移。
# en / th 为新建语种集合。
_LANG_COLLECTION_MAP: dict[str, str] = {
    "zh": COLLECTION_NAME,
    "en": f"{COLLECTION_NAME}_en",
    "th": f"{COLLECTION_NAME}_th",
}
_FALLBACK_COLLECTION = COLLECTION_NAME


def get_lang_collection_name(lang: str) -> str:
    """根据语种获取 Milvus 集合名（白名单保护，防止集合名注入）。

    Args:
        lang: 业务语种，如 "zh" / "en" / "th"

    Returns:
        对应集合名；未知语种降级为 COLLECTION_NAME
    """
    return _LANG_COLLECTION_MAP.get(lang, _FALLBACK_COLLECTION)


def truncate_for_milvus(value: object, max_len: int = MILVUS_SAFE_VARCHAR_LEN) -> str:
    """Milvus varchar 字段安全截断，避免 metadata 超长导致入库失败。"""
    text = "" if value is None else str(value)
    if len(text) <= max_len:
        return text
    return text[:max_len]


async def insert_into_milvus(documents: List[Document], embeddings, lang: str = "zh"):
    """将 Document 列表写入对应语种的 Milvus 集合。

    Args:
        lang: 业务语种，决定写入哪个集合（COLLECTION_NAME / COLLECTION_NAME_en / COLLECTION_NAME_th）
    """
    collection_name = get_lang_collection_name(lang)
    try:
        batch_size = 10
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i: i + batch_size]
            Milvus.from_documents(
                batch_docs,
                embeddings,
                collection_name=collection_name,
                connection_args=CONNECTION_ARGS,
                partition_key_field=PARTITION_FIELD_NAME,
                index_params=INDEX_PARAMS,
            )
        logger.info(f"导入 {len(documents)} 条到集合 {collection_name}")
    except Exception as e:
        logger.error(f"存储问答对到 Milvus 失败: {e}")
        raise HTTPException(status_code=500, detail=f"Fail to store QA，because {str(e)}")

def delete_milvus_by_filename_and_position_id(sop_id: int, lang: str = "zh"):
    """根据 sop_id 删除对应语种集合中的向量记录。

    Args:
        lang: 业务语种，决定从哪个集合删除（COLLECTION_NAME / COLLECTION_NAME_en / COLLECTION_NAME_th）
    """
    collection_name = get_lang_collection_name(lang)
    try:
        client = MilvusClient(uri=MILVUS_URI)

        # 构造 expr 查询 metadata
        expr = f"sop_id == {sop_id}"
        logger.info(f"[ delete_milvus ] 删除 Milvus 记录: collection={collection_name}, expr={expr}")

        delete_result = client.delete(
            collection_name=collection_name,
            filter=expr
        )

        logger.info(f"[ delete_milvus ] 删除结果: {delete_result}")

    except Exception as e:
        logger.error(f"[ delete_milvus ] 删除 Milvus 记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"Fail to delete Milvus records for file sop_id={sop_id}.")

def ingest_qa_to_milvus(file_name: str, collection_name: str, qa_results: list, position_id: str, embeddings,sop_id:int):
    """将问答对导入Milvus，优化批量处理"""
    logger.info(f"[ ingest qa ] file name: {file_name}")

    s_time = time.time()
    insert_docs = []
    metadata_list = []  # 新增：用于存储所有metadata

    for idx, qa in enumerate(qa_results, start=1):
        raw_content = qa.get("背景") or qa.get("内容", "")
        milvus_content = truncate_for_milvus(raw_content)
        if len(milvus_content) < len(str(raw_content)):
            logger.warning(
                f"[ ingest qa ] truncate content for Milvus: file={file_name}, qa_index={idx}, "
                f"original_len={len(str(raw_content))}, stored_len={len(milvus_content)}"
            )

        metadata = {
            "filename": truncate_for_milvus(file_name),
            "answer": truncate_for_milvus(qa.get("答案", "")),
            "excel_row": qa.get("行号", -1),
            "location": truncate_for_milvus(qa.get("定位", "")),
            "content": milvus_content,
            "question_type": truncate_for_milvus(qa["题型"]),
            "difficulty_factor": qa.get("难度因子", 0),
            "position_id": truncate_for_milvus(position_id),
            "sop_id":sop_id
        }

        # 按照指定格式收集metadata
        formatted_metadata = {
            "row": qa.get("行号", -1),
            "position": qa.get("定位", ""),
            "question": qa["题目"],
            "answer": qa.get("答案", ""),
            "content": raw_content,
            "difficulty_factor": qa.get("难度因子", 0),
            "position_id": position_id,
            "type": qa["题型"],
            "sop_id":sop_id
        }
        metadata_list.append(formatted_metadata)  # 将格式化后的metadata添加到列表
        insert_docs.append(
            Document(
                page_content=truncate_for_milvus(qa["题目"]),
                metadata=metadata,
            )
        )

    # 优化批量导入，使用更小的批次
    batch_size = min(BATCH_SIZE, 10)  # 减小批次大小
    for i in range(0, len(insert_docs), batch_size):
        batch_docs = insert_docs[i: i + batch_size]

        try:
            _ = Milvus.from_documents(
                batch_docs,
                embeddings,
                collection_name=collection_name,
                connection_args=CONNECTION_ARGS,
                partition_key_field=PARTITION_FIELD_NAME,
                index_params=INDEX_PARAMS,
            )

            # 批次间稍作延迟，避免过载
            if i + batch_size < len(insert_docs):
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"[ ingest qa ] error: {e}")
            raise HTTPException(status_code=500, detail=f"Fail to store qa of file {file_name}.")

    e_time = time.time()
    logger.info(f"[ generate_qa ] ingest time:{e_time - s_time:.4f} seconds")
    logger.info(f"{file_name} 导入 {len(insert_docs)} 条")

    return metadata_list  # 返回格式化后的metadata列表


async def check_milvus_has_file(file_name: str, position_id: str, embeddings,
                                lang: str = "zh", collection_name: str = None,
                                k=1, timeout=100) -> bool:
    """检查文件是否存在于对应语种的存储中。

    先检查语种表中的 MySQL 记录，再检查语种集合中的 Milvus 记录。

    Args:
        lang: 业务语种，决定查哪张 MySQL 表和哪个 Milvus 集合
        collection_name: 可显式指定集合名（优先于 lang 推导）
    """
    # 确定实际使用的集合名
    actual_collection = collection_name if collection_name else get_lang_collection_name(lang)
    try:
        # 第一步：检查数据库中是否有该文件记录（查对应语种表）
        db_client = MySQLClient(MYSQL_CONFIG)
        db_record = db_client.query_sops_by_filename(file_name, position_id, lang=lang)

        if db_record:
            logger.info(f"[check_file] 数据库中找到文件记录: {file_name}, 状态: {db_record.get('task_status')}（{lang}表）")
            # 如果数据库中有记录且状态为成功，直接返回 True
            return True
        else:
            logger.info(f"[check_file] 数据库中未找到文件记录: {file_name}（{lang}表），继续检查 Milvus")

        # 第二步：检查 Milvus 中是否存在该文件的向量数据（查对应语种集合）
        client = Milvus(
            embedding_function=embeddings,
            collection_name=actual_collection,
            connection_args={
                "uri": MILVUS_URI,
                "db_name": "default",
            }
        )

        # 构造 expr 查询 metadata
        expr = f"filename == '{file_name}' and position_id == '{position_id}'"
        logger.debug(f"[check_file] 查询 Milvus: collection={actual_collection}, expr={expr}")

        results = client.similarity_search_with_score(
            query="*",
            k=k,
            expr=expr,
            timeout=timeout
        )
        milvus_exists = len(results) > 0
        if milvus_exists:
            logger.info(f"[check_file] Milvus 中找到 {len(results)} 条记录: {file_name}，进行删除")
            # 构建删除条件：匹配filename的元数据
            client.delete(expr=expr)
        else:
            logger.info(f"[check_file] Milvus 中未找到记录: {file_name}（{actual_collection}）")

        return False

    except Exception as e:
        # 精准的错误分类和报告
        error_msg = str(e).lower()

        if "connection" in error_msg or "connect" in error_msg:
            logger.error(f"[check_file] 连接失败 - 文件: {file_name}, 错误: 无法连接到 Milvus 或 MySQL 服务")
        elif "timeout" in error_msg:
            logger.error(f"[check_file] 超时错误 - 文件: {file_name}, 错误: 查询超时({timeout}s)")
        elif "collection" in error_msg and "not" in error_msg:
            logger.error(f"[check_file] 集合不存在 - 文件: {file_name}, 集合: {actual_collection}")
        elif "expr" in error_msg or "expression" in error_msg:
            logger.error(f"[check_file] 查询表达式错误 - 文件: {file_name}, 表达式: filename == '{file_name}'")
        elif "mysql" in error_msg:
            logger.error(f"[check_file] MySQL 查询失败 - 文件: {file_name}, 错误: {str(e)}")
        else:
            logger.error(f"[check_file] 未知错误 - 文件: {file_name}, 错误类型: {type(e).__name__}, 详情: {str(e)}")

        raise HTTPException(status_code=500, detail=f"{error_msg}")
