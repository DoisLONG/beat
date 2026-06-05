# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from langchain_community.utilities import BingSearchAPIWrapper

from comps.web_search.engines.base import BaseSearch
import os

from comps import CustomLogger

logger = CustomLogger("bing_search")
LOGFLAG = os.getenv("LOGFLAG", False)

BING_API_KEY = os.getenv("BING_API_KEY", "")
BING_ENDPOINT = os.getenv("BING_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")


class BingSearch(BaseSearch):
    async def search(self, query: str, count: int = 5) -> list[dict]:
        try:
            search_wrapper = BingSearchAPIWrapper(bing_subscription_key = BING_API_KEY, bing_search_url = BING_ENDPOINT)
            search_results = search_wrapper.results(query = query, num_results = count)
            if search_results and search_results[0] and search_results[0].get("Result") is not None:
                if LOGFLAG:
                    logger.info(f"BingSearch error: Bing no search results found")
                raise RuntimeError(f"BingSearch error: Bing no search results found")
            return search_results
        except Exception as e:
            if LOGFLAG:
                logger.error(f"BingSearch error: {e}")
            raise RuntimeError(f"BingSearch error: {e}")
