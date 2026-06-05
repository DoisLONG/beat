# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

from pymilvus import MilvusClient, MilvusException
from sqlalchemy import text
from sqlalchemy.orm import Session

from comps import CustomLogger
from comps.dashboard.config.base_config import MILVUS_HOST, MILVUS_PORT
from comps.dashboard.utils import (
    resolve_lang,
    sop_info_table,
    material_table,
    milvus_collection_name,
)

logger = CustomLogger("dashboard-resource-summary-service", os.getenv("LOG_LEVEL", "INFO"))
MILVUS_URI = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_qa")


class ResourceSummaryService:
    def __init__(self, db: Session, tenant_id: int, data_lang: str = "zh"):
        self.db = db
        self.tenant_id = tenant_id
        self.data_lang = resolve_lang(data_lang)

    def _get_milvus_question_count(self) -> int:
        sop_table = sop_info_table(self.data_lang)
        sop_rows = self.db.execute(
            text(
                f"SELECT id FROM {sop_table} "
                f"WHERE tenant_id = :tenant_id AND task_status = 'SUCCESS'"
            ),
            {"tenant_id": self.tenant_id},
        ).fetchall()
        sop_ids = [row.id for row in sop_rows if row.id is not None]
        if not sop_ids:
            return 0

        collection_name = milvus_collection_name(COLLECTION_NAME, self.data_lang)
        client = MilvusClient(uri=MILVUS_URI)
        total_count = 0
        for sop_id in sop_ids:
            result = client.query(
                collection_name=collection_name,
                filter=f"sop_id == {sop_id}",
                output_fields=["sop_id"],
            )
            total_count += len(result)
        return total_count

    def get_summary(self) -> dict[str, int]:
        """获取资源总览计数（按 data_lang 路由所有内容表/Milvus 集合）"""
        try:
            sop_table = sop_info_table(self.data_lang)
            mat_table = material_table(self.data_lang)

            # 1. 试题库试题
            try:
                sop_count = self._get_milvus_question_count()
            except MilvusException as exc:
                if "can't find collection" in str(exc).lower() or "collection not found" in str(exc).lower():
                    logger.warning(
                        f"Milvus collection 不存在，按0处理 (lang={self.data_lang}): {exc}"
                    )
                    sop_count = 0
                else:
                    raise

            # 2. 素材库素材
            material_count = self.db.execute(
                text(f"SELECT COUNT(*) FROM {mat_table} WHERE tenant_id = :tenant_id"),
                {"tenant_id": self.tenant_id},
            ).scalar_one_or_none() or 0

            # 3. 已完成的SOP数量（task_status = 'SUCCESS'）
            exercise_count = self.db.execute(
                text(
                    f"SELECT COUNT(*) FROM {sop_table} "
                    f"WHERE tenant_id = :tenant_id AND task_status = 'SUCCESS'"
                ),
                {"tenant_id": self.tenant_id},
            ).scalar_one_or_none() or 0

            # 4. 机器人数量 (写死)
            robot_count = 1

            return {
                "sop_count": int(sop_count),
                "material_count": int(material_count),
                "exercise_count": int(exercise_count),
                "robot_count": robot_count,
            }
        except Exception as e:
            logger.error(f"查询资源总览数据失败: {e}")
            # 向上抛出异常，由API层统一处理
            raise
