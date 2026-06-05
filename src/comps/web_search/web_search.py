# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os

from docarray import DocList
from docarray.documents import TextDoc
from typing import List, Union

from comps import register_microservice, register_statistics, ServiceType, opea_microservices, SearchedDoc, \
    MetadataTextDoc, CustomLogger
from comps.web_search.engines import multi_engine_search

logger = CustomLogger("web_search")
LOGFLAG = os.getenv("LOGFLAG", False)


@register_microservice(
    name="opea_service@web_search",
    service_type=ServiceType.WEB_RETRIEVER,
    endpoint="/v1/web_search",
    host="0.0.0.0",
    port=7050,
)
@register_statistics(names=["opea_service@web_search"])
async def web_search(input: Union[SearchedDoc, TextDoc]):
    # return {"messages": await multi_engine_search(input.text)}
    query = None
    if isinstance(input, TextDoc):
        query = input.text
    elif isinstance(input, SearchedDoc):
        query = input.initial_query
    results = await multi_engine_search(query)
    if LOGFLAG:
        logger.info(f"Search result with similarity score: {results}")
    if isinstance(input, TextDoc):
        return format_to_searched_doc(input, results)
    elif isinstance(input, SearchedDoc):
        return format_to_searched_doc(input, results)


def format_to_searched_doc(input: Union[TextDoc, SearchedDoc], results: List[dict]) -> SearchedDoc:
    query = None
    docs = []
    if isinstance(input, TextDoc):
        query = input.text
    elif isinstance(input, SearchedDoc):
        query = input.initial_query
        docs = input.retrieved_docs


    for r in results:
        metadata = {
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "type": "2"
        }

        # Construct document content（text）
        text_with_meta = ""
        if r.get("snippet"):
            text_with_meta += f"{r['snippet']}\n"

        docs.append(MetadataTextDoc(text=text_with_meta, metadata=metadata))

    # Encapsulation as DocList
    retrieved_docs = DocList[MetadataTextDoc](docs)

    return SearchedDoc(
        retrieved_docs=retrieved_docs,
        initial_query=query
    )

if __name__ == "__main__":
    opea_microservices["opea_service@web_search"].start()
