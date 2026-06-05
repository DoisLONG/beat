# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
task_context.py
Celery 任务的可序列化上下文，显式携带语种，避免异步阶段丢失语种上下文。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class TaskContext:
    """Celery 任务上下文，必须在 main.py 发起任务前构造并序列化传入。

    Attributes:
        lang:        业务语种，决定落表和落集合，由 JWT.lang 确定
        tenant_id:   租户 ID
        sop_id:      SOP 记录 ID
        position_id: 岗位 ID
        filename:    文件名
    """
    lang: Literal["zh", "en", "th"]
    tenant_id: Optional[int]
    sop_id: int
    position_id: str
    filename: str
