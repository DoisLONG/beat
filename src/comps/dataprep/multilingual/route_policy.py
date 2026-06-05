# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
route_policy.py
语种到资源名的映射规则，以及核心路由数据结构。

所有表名/集合名的生成都必须经过此模块，
禁止在业务代码中手动拼接 sp_sop_info_en / rag_milvus_en 等字符串。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from comps.dataprep.multilingual.context import LanguageContext
from comps.dataprep.config import COLLECTION_NAME

# ——— 路由映射表（唯一的语种-资源名配置来源）———
# zh 直接复用原有旧表/旧集合，历史数据零迁移；en/th 为新建语种表/集合

LANG_SOP_TABLE_MAP: dict[str, str] = {
    "zh": "sp_sop_info",
    "en": "sp_sop_info_en",
    "th": "sp_sop_info_th",
}

LANG_COLLECTION_MAP: dict[str, str] = {
    "zh": COLLECTION_NAME,
    "en": f"{COLLECTION_NAME}_en",
    "th": f"{COLLECTION_NAME}_th",
}

# 兜底语种（当 lang 不在映射表中时使用）
_FALLBACK_LANG = "zh"


@dataclass(frozen=True)
class ResourceRoute:
    """描述当前语种对应的实际数据源位置。

    Attributes:
        sop_table:         MySQL SOP 表名，如 sp_sop_info_zh
        milvus_collection: Milvus 集合名，如 rag_milvus_zh
    """
    sop_table: str
    milvus_collection: str


class RoutePolicy(Protocol):
    """语种路由策略协议。"""

    def resolve(self, language: LanguageContext) -> ResourceRoute:
        ...


class FixedLangRoutePolicy:
    """固定语种路由策略：zh / en / th 各自对应独立的表和集合。"""

    def resolve(self, language: LanguageContext) -> ResourceRoute:
        lang = language.lang
        table = LANG_SOP_TABLE_MAP.get(lang, LANG_SOP_TABLE_MAP[_FALLBACK_LANG])
        collection = LANG_COLLECTION_MAP.get(lang, LANG_COLLECTION_MAP[_FALLBACK_LANG])
        return ResourceRoute(sop_table=table, milvus_collection=collection)


# ——— 工具函数（供 MySQLClient / milvus_utils 内部调用）———

def get_sop_table(lang: str) -> str:
    """根据语种获取 SOP 表名（供 MySQLClient 内部使用，不得绕过此函数手动拼表名）。

    Args:
        lang: 业务语种，如 "zh" / "en" / "th"

    Returns:
        对应的表名，如 "sp_sop_info"（zh）/"sp_sop_info_en"/"sp_sop_info_th"；
        未知语种降级为 "sp_sop_info"
    """
    return LANG_SOP_TABLE_MAP.get(lang, LANG_SOP_TABLE_MAP[_FALLBACK_LANG])


def get_collection_name(lang: str) -> str:
    """根据语种获取 Milvus 集合名（供 milvus_utils 内部使用，不得绕过此函数手动拼集合名）。

    Args:
        lang: 业务语种，如 "zh" / "en" / "th"

    Returns:
        对应的集合名；zh 返回环境变量 COLLECTION_NAME，
        en/th 返回 COLLECTION_NAME + _en/_th；未知语种降级为 COLLECTION_NAME
    """
    return LANG_COLLECTION_MAP.get(lang, LANG_COLLECTION_MAP[_FALLBACK_LANG])
