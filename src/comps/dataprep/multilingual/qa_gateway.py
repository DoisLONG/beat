# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
qa_gateway.py
封装 Milvus 语种集合访问，屏蔽集合名细节。

业务层只面向 QAVectorGateway 编程，不直接感知 rag_milvus_zh/en/th 集合名。
"""

from __future__ import annotations

from typing import List

from langchain_core.documents import Document

from comps.dataprep.multilingual.context import DataprepContext
from comps.dataprep.multilingual.route_policy import get_collection_name
from comps.dataprep.common.milvus_utils import (
    check_milvus_has_file as _check_milvus_has_file,
    insert_into_milvus as _insert_into_milvus,
    delete_milvus_by_filename_and_position_id as _delete_milvus,
    ingest_qa_to_milvus as _ingest_qa_to_milvus,
)


class QAVectorGateway:
    """封装 Milvus 语种集合访问的网关。

    所有方法通过 DataprepContext.lang 自动路由到对应语种集合，
    调用方无需关心实际集合名。
    """

    async def exists_file(
        self,
        ctx: DataprepContext,
        file_name: str,
        position_id: str,
        embeddings,
    ) -> bool:
        """检查指定文件是否已存在于对应语种集合中。"""
        collection = get_collection_name(ctx.lang)
        return await _check_milvus_has_file(
            file_name=file_name,
            position_id=position_id,
            embeddings=embeddings,
            collection_name=collection,
        )

    async def ingest_documents(
        self,
        ctx: DataprepContext,
        documents: List[Document],
        embeddings,
    ) -> None:
        """将 Document 列表写入对应语种集合（用于 QA 保存/覆写场景）。"""
        collection = get_collection_name(ctx.lang)
        await _insert_into_milvus(documents, embeddings, lang=ctx.lang)

    def delete_by_sop_id(self, ctx: DataprepContext, sop_id: int) -> None:
        """删除对应语种集合中指定 sop_id 的所有向量记录。"""
        _delete_milvus(sop_id, lang=ctx.lang)

    def ingest_qa(
        self,
        ctx: DataprepContext,
        filename: str,
        qa_results: list,
        position_id: str,
        embeddings,
        sop_id: int,
    ) -> list:
        """将 QA 问答对写入对应语种集合，返回格式化后的 metadata 列表。"""
        collection = get_collection_name(ctx.lang)
        return _ingest_qa_to_milvus(
            file_name=filename,
            collection_name=collection,
            qa_results=qa_results,
            position_id=position_id,
            embeddings=embeddings,
            sop_id=sop_id,
        )
