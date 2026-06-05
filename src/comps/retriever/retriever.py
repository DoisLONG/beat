# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import argparse
import os
import time
from typing import List, Optional

from config import (
    COLLECTION_NAME,
    LOCAL_EMBEDDING_MODEL,
    MILVUS_HOST,
    MILVUS_PORT,
    MOSEC_EMBEDDING_ENDPOINT,
    MOSEC_EMBEDDING_MODEL,
    TEI_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_MODEL,
    embedding_ctx_length
)
from langchain_community.embeddings import HuggingFaceBgeEmbeddings, HuggingFaceHubEmbeddings, OpenAIEmbeddings
from langchain_milvus.vectorstores import Milvus

from comps import (
    CustomLogger,
    EmbedDoc,
    SearchedDoc,
    ServiceType,
    MetadataTextDoc,
    opea_microservices,
    register_microservice,
    register_statistics,
    statistics_dict,
)

logger = CustomLogger("retriever_milvus", os.getenv("LOG_LEVEL", "INFO"))

MILVUS_URI = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
index_params = {"index_type": "FLAT", "metric_type": "IP", "params": {}}

class MosecEmbeddings(OpenAIEmbeddings):
    def _get_len_safe_embeddings(
        self, texts: List[str], *, engine: str, chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        _chunk_size = chunk_size or self.chunk_size
        batched_embeddings: List[List[float]] = []
        response = self.client.create(input=texts, **self._invocation_params)
        if not isinstance(response, dict):
            response = response.model_dump()
        batched_embeddings.extend(r["embedding"] for r in response["data"])

        _cached_empty_embedding: Optional[List[float]] = None

        def empty_embedding() -> List[float]:
            nonlocal _cached_empty_embedding
            if _cached_empty_embedding is None:
                average_embedded = self.client.create(input="", **self._invocation_params)
                if not isinstance(average_embedded, dict):
                    average_embedded = average_embedded.model_dump()
                _cached_empty_embedding = average_embedded["data"][0]["embedding"]
            return _cached_empty_embedding

        return [e if e is not None else empty_embedding() for e in batched_embeddings]


@register_microservice(
    name="opea_service@retriever_milvus",
    service_type=ServiceType.RETRIEVER,
    endpoint="/v1/retrieval",
    host="0.0.0.0",
    port=7000,
)
@register_statistics(names=["opea_service@retriever_milvus"])
async def retrieve(input: EmbedDoc) -> SearchedDoc:

    log_info = {
        'text': input.text,
        'search_type': input.search_type,
        'k': input.k,
        'distance_threshold': input.distance_threshold,
        'fetch_k': input.fetch_k,
        'lambda_mult': input.lambda_mult,
        'score_threshold': input.score_threshold,
        'constraints': input.constraints,
        'collection_name': input.collection_name
    }
    logger.info(f"Input parameters: {log_info}")

    collection_name = input.collection_name if input.collection_name is not None else COLLECTION_NAME

    vector_db = Milvus(
        embeddings,
        connection_args={"uri": MILVUS_URI},
        collection_name=collection_name,
        index_params=index_params,
    )
    start = time.time()
    if input.search_type == "similarity":
        search_res = await vector_db.asimilarity_search_by_vector(embedding=input.embedding, k=input.k)
    elif input.search_type == "similarity_distance_threshold":
        if input.distance_threshold is None:
            raise ValueError("distance_threshold must be provided for " + "similarity_distance_threshold retriever")
        search_res = await vector_db.asimilarity_search_by_vector(
            embedding=input.embedding, k=input.k, distance_threshold=input.distance_threshold
        )
    elif input.search_type == "similarity_score_threshold":
        docs_and_similarities = await vector_db.asimilarity_search_with_relevance_scores(
            query=input.text, k=input.k, score_threshold=input.score_threshold
        )

        for doc, similarity in docs_and_similarities:
            logger.debug(f"Search result with similarity score: content={doc.page_content}, metadata={doc.metadata}, similarity={similarity}")

        search_res = [doc for doc, _ in docs_and_similarities]
    elif input.search_type == "mmr":
        search_res = await vector_db.amax_marginal_relevance_search(
            query=input.text, k=input.k, fetch_k=input.fetch_k, lambda_mult=input.lambda_mult
        )
    searched_docs = []
    for r in search_res:
        searched_docs.append(MetadataTextDoc(text=r.page_content, metadata=r.metadata))
    result = SearchedDoc(retrieved_docs=searched_docs, initial_query=input.text)
    statistics_dict["opea_service@retriever_milvus"].append_latency(time.time() - start, None)

    logger.debug(f"Search result - Initial Query: {result.initial_query}")
    logger.debug(f"Search result - Retrieved Docs: {result.retrieved_docs}")
    return result


if __name__ == "__main__":
    # Create vectorstore
    if OVMS_EMBEDDING_ENDPOINT:
        from langchain_openai import OpenAIEmbeddings

        logger.info(f"OVMS_EMBEDDING_ENDPOINT:{OVMS_EMBEDDING_ENDPOINT}")

        # create embeddings using OVMS endpoint service
        embeddings = OpenAIEmbeddings(
            model=OVMS_EMBEDDING_MODEL,
            api_key="unused",
            base_url=OVMS_EMBEDDING_ENDPOINT,
            tiktoken_enabled=False,
            embedding_ctx_length=embedding_ctx_length
        )
        logger.debug(f"embeddings:{embeddings}")
    elif TEI_EMBEDDING_ENDPOINT:
        # create embeddings using TEI endpoint service
        logger.info(f"[ retriever_milvus ] TEI_EMBEDDING_ENDPOINT:{TEI_EMBEDDING_ENDPOINT}")
        embeddings = HuggingFaceHubEmbeddings(model=TEI_EMBEDDING_ENDPOINT)
    elif MOSEC_EMBEDDING_ENDPOINT:
        # create embeddings using Mosec endpoint service
        logger.info(f"[ retriever_milvus ] MOSEC_EMBEDDING_ENDPOINT:{MOSEC_EMBEDDING_ENDPOINT}")
        embeddings = MosecEmbeddings(model=MOSEC_EMBEDDING_MODEL)
    else:
        # create embeddings using local embedding model
        logger.info(f"[ retriever_milvus ] LOCAL_EMBEDDING_MODEL:{LOCAL_EMBEDDING_MODEL}")
        embeddings = HuggingFaceBgeEmbeddings(model_name=LOCAL_EMBEDDING_MODEL)

    opea_microservices["opea_service@retriever_milvus"].start()