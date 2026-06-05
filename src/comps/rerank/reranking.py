# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import heapq
import json
import os
import re
import time
from typing import Union

import requests

from comps import (
    CustomLogger,
    LLMParamsDoc,
    SearchedDoc,
    ServiceType,
    opea_microservices,
    register_microservice,
    register_statistics,
    statistics_dict,
)
from comps.cores.proto.api_protocol import (
    ChatCompletionRequest,
    RerankingRequest,
    RerankingResponse,
    RerankingResponseData,
)

logger = CustomLogger("reranking_gaudi", os.getenv("LOG_LEVEL", "INFO"))
BACKEND = os.getenv("EMBEDDING_RERANKER_BACKEND", "ovms").lower()  # 'tei' or 'ovms', default to 'ovms'
try:
    outstanding_score = int(os.getenv("OUTSTANDING_SCORE", "0"))
except ValueError:
    outstanding_score = 0

@register_microservice(
    name="opea_service@reranking_gaudi",
    service_type=ServiceType.RERANK,
    endpoint="/v1/reranking",
    host="0.0.0.0",
    port=8000,
    input_datatype=SearchedDoc,
    output_datatype=LLMParamsDoc,
)
@register_statistics(names=["opea_service@reranking_gaudi"])
def reranking(
    input: Union[SearchedDoc, RerankingRequest, ChatCompletionRequest]
) -> Union[LLMParamsDoc, RerankingResponse, ChatCompletionRequest]:
    logger.debug(f"input: {input}")

    start = time.time()
    reranking_results = []
    
    if input.retrieved_docs:
        docs = [doc.text for doc in input.retrieved_docs]
        if isinstance(input, SearchedDoc):
            query = input.initial_query
        else:
            query = input.input

        if BACKEND == "ovms":  # Check OVMS first since it's the default
            url = ovms_endpoint + "/rerank"
            data = {"model": ovms_model, "query": query, "documents": docs}
        else:  # tei
            url = tei_endpoint + "/rerank"
            data = {"query": query, "texts": docs}
            
        headers = {"Content-Type": "application/json"}

        logger.debug(f"url: {url}")
        logger.debug(f"data: {data}")
            
        response = requests.post(url, data=json.dumps(data), headers=headers)
        response_data = response.json()
        
        # Handle OVMS specific response structure
        if BACKEND == "ovms":
            response_data = response_data["results"]
            
        for best_response in response_data[: input.top_n]:
            index = best_response["index"]
            score = best_response["relevance_score"] if BACKEND == "ovms" else best_response["score"]
            if score > outstanding_score:
                reranking_results.append(
                    {
                        "text": input.retrieved_docs[index].text,
                        "metadata": input.retrieved_docs[index].metadata,
                        "score": score,
                    }
                )

    statistics_dict["opea_service@reranking_gaudi"].append_latency(time.time() - start, None)
    
    if isinstance(input, SearchedDoc):
        result = []
        for doc in reranking_results:
            if doc["text"] is None:
                # Skip documents with None text
                continue

            if doc["metadata"] is not None:
                # If has metadata, use dict format
                result.append({
                    "text": doc["text"],
                    "metadata": doc["metadata"]
                })
            else:
                # If no metadata, just append the text as string
                result.append(doc["text"])
        logger.debug(f"result: {result}")
        return LLMParamsDoc(query=input.initial_query, documents=result)
    else:
        reranking_docs = []
        for doc in reranking_results:
            reranking_docs.append(RerankingResponseData(text=doc["text"], score=doc["score"]))
        if isinstance(input, RerankingRequest):
            result = RerankingResponse(reranked_docs=reranking_docs)
            logger.debug(f"result: {result}")
            return result

        if isinstance(input, ChatCompletionRequest):
            input.reranked_docs = reranking_docs
            input.documents = [doc["text"] for doc in reranking_results]
            logger.debug(f"input: {input}")
            return input

if __name__ == "__main__":
    tei_endpoint = os.getenv("TEI_RERANKING_ENDPOINT", "http://localhost:8080")
    ovms_endpoint = os.getenv("OVMS_RERANKING_ENDPOINT", "http://localhost:8001")
    ovms_model = os.getenv("OVMS_RERANKING_MODEL", "BAAI/bge-reranker-large")
    
    logger.info(f"Using {BACKEND} backend")
    if BACKEND == "ovms":
        logger.info(f"OVMS endpoint: {ovms_endpoint}")
        logger.info(f"OVMS model: {ovms_model}")
    else:  # tei
        logger.info(f"TEI endpoint: {tei_endpoint}")
            
    opea_microservices["opea_service@reranking_gaudi"].start() 