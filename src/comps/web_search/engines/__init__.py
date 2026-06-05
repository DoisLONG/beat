#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os
from typing import List, Dict

from comps import CustomLogger
from comps.web_search.engines.duckduck_search import DuckDuckSearch
from comps.web_search.engines.bing_search import BingSearch
from comps.web_search.engines.google_search import GoogleSearch

logger = CustomLogger("web_search")
LOGFLAG = os.getenv("LOGFLAG", False)
SEARCH_ENGINE_ORDER = os.getenv("SEARCH_ENGINE_ORDER", "google,bing,duckduckgo")

# Map name to implementation class
ENGINE_MAP = {
    "google": GoogleSearch,
    "bing": BingSearch,
    "duckduckgo": DuckDuckSearch,
}

def get_search_providers() -> List:
    config_order = SEARCH_ENGINE_ORDER.split(",")
    configured = [name.strip().lower() for name in config_order]

    providers = []
    unknown_providers = []
    for name in configured:
        if name in ENGINE_MAP:
            providers.append(ENGINE_MAP[name]())
        else:
            unknown_providers.append(name)

    # Check for any omissions (implemented but not in the configuration)
    missing_in_config = [name for name in ENGINE_MAP if name not in configured]

    if LOGFLAG:
        if unknown_providers:
            logger.warning(f"Unknown providers in config and ignored: {unknown_providers}")
        if missing_in_config:
            logger.info(f"Providers not in config but implemented: {missing_in_config}")

    return providers

async def multi_engine_search(query: str, count: int = 5) -> List[Dict]:
    for provider in get_search_providers():
        try:
            result = await provider.search(query, count)
            if result:
                return result
        except Exception as e:
            if LOGFLAG:
                logger.warning(f"[WARNING] {provider.__class__.__name__} searchFailed:{e}")
            continue  # Skip the current and try the next engine
    if LOGFLAG:
        logger.error(f"All search engines have failed")
    return []
