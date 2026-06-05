# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os

from comps import CustomLogger
from comps.web_search.engines.base import BaseSearch
from typing import List, Dict
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

logger = CustomLogger("duckduckgo_search")
LOGFLAG = os.getenv("LOGFLAG", False)

class DuckDuckSearch(BaseSearch):

    async def search(self, query: str, count: int = 5) -> List[Dict]:
        search_wrapper = DuckDuckGoSearchAPIWrapper(max_results=count)
        search_results = search_wrapper.results(query = query, max_results=count, source="text")

        if search_results and search_results[0] and search_results[0].get("Result") is not None:
            if LOGFLAG:
                logger.info(f"DuckDuckGoSearch error: {search_results[0].get('Result')}")
            raise RuntimeError(f"DuckDuckGoSearch error: {search_results[0].get('Result')}")
        return search_results
