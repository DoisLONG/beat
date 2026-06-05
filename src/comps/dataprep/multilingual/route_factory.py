# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
route_factory.py
根据 LanguageContext 生成 ResourceRoute 的工厂。

统一出口，保证业务层拿到的是同一份路由结果。
"""

from __future__ import annotations

from comps.dataprep.multilingual.context import LanguageContext
from comps.dataprep.multilingual.route_policy import (
    FixedLangRoutePolicy,
    ResourceRoute,
    RoutePolicy,
)

_default_policy = FixedLangRoutePolicy()


class ResourceRouteFactory:
    """根据 LanguageContext 生成 ResourceRoute。

    用法：
        factory = ResourceRouteFactory.default()
        route = factory.create(language_ctx)
        table = route.sop_table
        collection = route.milvus_collection
    """

    def __init__(self, policy: RoutePolicy | None = None) -> None:
        self._policy = policy or _default_policy

    def create(self, language: LanguageContext) -> ResourceRoute:
        return self._policy.resolve(language)

    @classmethod
    def default(cls) -> ResourceRouteFactory:
        return cls(_default_policy)
