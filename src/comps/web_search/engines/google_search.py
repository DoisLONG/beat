# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os

from comps.web_search.engines.base import BaseSearch
from langchain_google_community import GoogleSearchAPIWrapper

from comps import CustomLogger

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CX = os.getenv("GOOGLE_CX", "")

logger = CustomLogger("google_search")
LOGFLAG = os.getenv("LOGFLAG", False)

class GoogleSearch(BaseSearch):
    async def search(self, query: str, count: int = 5) -> list[dict]:
        try:
            if not GOOGLE_API_KEY or not GOOGLE_CX:
                if LOGFLAG:
                    logger.error(f"GoogleSearch error: [Google config error] API key or cx not config")
                raise RuntimeError(f"GoogleSearch error: [Google config error] API key or cx not config")

            search_wrapper = GoogleSearchAPIWrapper(google_cse_id= GOOGLE_CX, google_api_key=GOOGLE_API_KEY)
            search_results = search_wrapper.results(query=query, num_results=count)

            if search_results and search_results[0] and search_results[0].get("Result") is not None:
                if LOGFLAG:
                    logger.error(f"GoogleSearch error: [Google config error] Bing no search results found")
                raise RuntimeError(f"GoogleSearch error: Bing no search results found")
            return search_results
        except Exception as e:
            if LOGFLAG:
                logger.error(f"GoogleSearch error: {e}")
            raise RuntimeError(f"GoogleSearch error: {e}")
