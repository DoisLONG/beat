# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
context.py
承载一次请求或一次任务处理的统一上下文对象。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class LanguageContext:
    """一次请求的语种上下文，不可变。

    Attributes:
        raw_accept_language: 原始 Accept-Language 请求头字符串
        lang: 标准化后的业务语种，仅为 zh / en / th 之一
    """
    raw_accept_language: str
    lang: Literal["zh", "en", "th"]


@dataclass(frozen=True)
class DataprepContext:
    """一次业务调用的完整上下文，供日志、任务、数据访问统一使用。

    Attributes:
        language:    语种上下文
        tenant_id:   租户 ID
        user_id:     用户 ID（可选）
        position_id: 岗位 ID（可选）
        request_id:  请求追踪 ID（可选）
    """
    language: LanguageContext
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    position_id: Optional[str] = None
    request_id: Optional[str] = None

    @property
    def lang(self) -> Literal["zh", "en", "th"]:
        """快捷访问语种码。"""
        return self.language.lang
