# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
sop_repository.py
封装语种相关的 sp_sop_info_* 表访问，屏蔽表名细节。

业务层只面向 SOPInfoRepository 编程，不直接感知 sp_sop_info_zh/en/th 表名。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from comps.dataprep.multilingual.context import DataprepContext
from comps.dataprep.mysql_client import MySQLClient


class SOPInfoRepository:
    """sp_sop_info_* 表的仓储封装。

    所有方法通过 DataprepContext.lang 自动路由到对应语种表，
    调用方无需关心实际表名。
    """

    def __init__(self, db: MySQLClient) -> None:
        self._db = db

    # ——— 写操作 ———

    def insert_sop(
        self,
        ctx: DataprepContext,
        *,
        title: str,
        filename: str,
        file_uri: str,
        position_id: str,
        file_type: str,
        tenant_id: int,
        start_time: str,
        end_time: str,
    ) -> int:
        """插入 SOP 记录到对应语种表，返回新记录 ID。"""
        return self._db.insert_sops(
            title=title,
            filename=filename,
            file_uri=file_uri,
            position_id=position_id,
            file_type=file_type,
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            lang=ctx.lang,
        )

    def update_status(
        self, ctx: DataprepContext, sop_id: int, task_id: str, task_status: str
    ) -> bool:
        """更新 task_id 和 task_status。"""
        return self._db.update_taskid_and_status(
            sop_id=sop_id, task_id=task_id, task_status=task_status, lang=ctx.lang
        )

    def update_percent(self, ctx: DataprepContext, sop_id: int, percent: str) -> bool:
        """更新进度百分比。"""
        return self._db.update_percent_by_id(sop_id, percent, lang=ctx.lang)

    def update_task_result(
        self, ctx: DataprepContext, sop_id: int, task_status: str, remark: str = "无"
    ) -> None:
        """更新 task_status（用于任务完成/失败回写）。"""
        return self._db.update_sops(
            sop_id=sop_id, task_status=task_status, remark=remark, lang=ctx.lang
        )

    def update_fields(
        self, ctx: DataprepContext, sop_id: int, data: Dict[str, Any]
    ) -> bool:
        """通用字段更新（传入字段名->值字典）。"""
        return self._db.update_sop_info(sop_id=sop_id, data=data, lang=ctx.lang)

    def update_num_flag(
        self, ctx: DataprepContext, sop_id: int, num_flag: int
    ) -> bool:
        """更新 num_flag 字段。"""
        return self._db.update_sop_info_num_flag(
            sop_id=sop_id, num_flag=num_flag, lang=ctx.lang
        )

    def update_title(
        self,
        ctx: DataprepContext,
        record_id: int,
        title: str,
        position_id: str | None = None,
    ) -> bool:
        """更新 title（可选同时更新 position_id）。"""
        return self._db.update_title_by_id(
            record_id, title, position_id, lang=ctx.lang
        )

    def delete_by_id(self, ctx: DataprepContext, sop_id: int) -> None:
        """删除指定语种表中的 SOP 记录。"""
        return self._db.delete_sops(sop_id=sop_id, lang=ctx.lang)

    # ——— 读操作 ———

    def get_by_id(self, ctx: DataprepContext, sop_id: int) -> Optional[Dict]:
        """按 ID 查询 SOP 记录（在对应语种表中查）。"""
        return self._db.query_sop_info_by_id(sop_id, lang=ctx.lang)

    def get_by_task_id(self, ctx: DataprepContext, task_id: str) -> Optional[Dict]:
        """按 task_id 查询 SOP 记录。"""
        return self._db.query_sops_by_task_id(task_id, lang=ctx.lang)

    def get_by_filename(
        self, ctx: DataprepContext, filename: str, position_id: str
    ) -> Optional[Dict]:
        """按文件名和岗位 ID 查询 SOP 记录。"""
        return self._db.query_sops_by_filename(filename, position_id, lang=ctx.lang)

    def get_id_by_filename_and_position(
        self,
        ctx: DataprepContext,
        filename: str,
        position_id: str,
        tenant_id: int,
    ) -> Optional[int]:
        """按文件名 + 岗位 + 租户查询 SOP ID。"""
        return self._db.query_sop_id_by_filename_and_position_id(
            filename, position_id, tenant_id, lang=ctx.lang
        )

    def list_paginated(
        self,
        ctx: DataprepContext,
        *,
        tenant_id: int,
        keyword: str = "",
        page: int = 1,
        page_size: int = 10,
        company_id: Optional[int] = None,
        department_id: Optional[int] = None,
        position_id: Optional[str] = None,
    ) -> Dict:
        """分页查询 SOP 列表（含租户筛选）。"""
        return self._db.query_sops_list_paginated(
            tenant_id=tenant_id,
            keyword=keyword,
            page=page,
            page_size=page_size,
            company_id=company_id,
            department_id=department_id,
            position_id=position_id,
            lang=ctx.lang,
        )

    def get_organization_tree(self, ctx: DataprepContext, user_id: int) -> List[Dict]:
        """查询组织架构树（仅包含对应语种表中有 SOP 的岗位）。"""
        return self._db.query_organization_tree(user_id, lang=ctx.lang)
