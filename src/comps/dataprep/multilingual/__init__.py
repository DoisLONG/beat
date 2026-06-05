# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
multilingual/__init__.py
对外暴露多语种能力的统一入口。
"""

from comps.dataprep.multilingual.context import DataprepContext, LanguageContext
from comps.dataprep.multilingual.language_resolver import (
    DEFAULT_LANG,
    SUPPORTED_LANGS,
    LanguageResolver,
)
from comps.dataprep.multilingual.route_factory import ResourceRouteFactory
from comps.dataprep.multilingual.route_policy import (
    LANG_COLLECTION_MAP,
    LANG_SOP_TABLE_MAP,
    FixedLangRoutePolicy,
    ResourceRoute,
    RoutePolicy,
    get_collection_name,
    get_sop_table,
)
from comps.dataprep.multilingual.sop_repository import SOPInfoRepository
from comps.dataprep.multilingual.qa_gateway import QAVectorGateway
from comps.dataprep.multilingual.task_context import TaskContext

__all__ = [
    # Context
    "LanguageContext",
    "DataprepContext",
    # Resolver
    "LanguageResolver",
    "SUPPORTED_LANGS",
    "DEFAULT_LANG",
    # Route
    "ResourceRoute",
    "RoutePolicy",
    "FixedLangRoutePolicy",
    "LANG_SOP_TABLE_MAP",
    "LANG_COLLECTION_MAP",
    "get_sop_table",
    "get_collection_name",
    "ResourceRouteFactory",
    # Repository / Gateway
    "SOPInfoRepository",
    "QAVectorGateway",
    # Task
    "TaskContext",
]
