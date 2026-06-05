# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import time
from typing import Union

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from comps import (
    CustomLogger,
    EmbedDoc,
    ServiceType,
    TextDoc,
    opea_microservices,
    register_microservice,
    register_statistics,
    statistics_dict,
)
from comps.cores.proto.api_protocol import (
    ChatCompletionRequest,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingResponseData,
)

logger = CustomLogger("embedding_tei_langchain", os.getenv("LOG_LEVEL", "INFO"))

@register_microservice(
    name="opea_service@embedding_tei_langchain",
    service_type=ServiceType.EMBEDDING,
    endpoint="/v1/embeddings",
    host="0.0.0.0",
    port=6000,
)
@register_statistics(names=["opea_service@embedding_tei_langchain"])
def embedding(
    input: Union[TextDoc, EmbeddingRequest, ChatCompletionRequest]
) -> Union[EmbedDoc, EmbeddingResponse, ChatCompletionRequest]:
    start = time.time()
    logger.debug(f"input: {input}")

    if isinstance(input, TextDoc):
        embed_vector = embeddings.embed_query(input.text)
        res = EmbedDoc(text=input.text, embedding=embed_vector)
    else:
        embed_vector = embeddings.embed_query(input.input)
        if input.dimensions is not None:
            embed_vector = embed_vector[: input.dimensions]

        if isinstance(input, ChatCompletionRequest):
            input.embedding = embed_vector
            # keep
            res = input
        if isinstance(input, EmbeddingRequest):
            # for standard openai embedding format
            res = EmbeddingResponse(data=[EmbeddingResponseData(index=0, embedding=embed_vector)])

    statistics_dict["opea_service@embedding_tei_langchain"].append_latency(time.time() - start, None)

    logger.debug(f"results: {res}")
    return res

if __name__ == "__main__":
    TEI_EMBEDDING_ENDPOINT = os.getenv("TEI_EMBEDDING_ENDPOINT", "")
    OVMS_EMBEDDING_ENDPOINT = os.getenv("OVMS_EMBEDDING_ENDPOINT", "")
    OVMS_EMBEDDING_MODEL = os.getenv("OVMS_EMBEDDING_MODEL", "")
    embedding_ctx_length = os.getenv("embedding_ctx_length", 470)
    if OVMS_EMBEDDING_ENDPOINT:
        from langchain_openai import OpenAIEmbeddings
        # Create an instance of OpenAIEmbedding
        embeddings = OpenAIEmbeddings(
            model=OVMS_EMBEDDING_MODEL,
            api_key="unused",
            base_url=OVMS_EMBEDDING_ENDPOINT,
            tiktoken_enabled=False,
            embedding_ctx_length=embedding_ctx_length,
        )
        logger.debug(f"OVMS_EMBEDDING_MODEL:{embeddings}")

    elif TEI_EMBEDDING_ENDPOINT:
        # create embeddings using TEI endpoint service
        logger.info(f"[ prepare_doc_milvus ] TEI_EMBEDDING_ENDPOINT:{TEI_EMBEDDING_ENDPOINT}")
        embeddings = HuggingFaceEndpointEmbeddings(model=TEI_EMBEDDING_ENDPOINT)

    else:
        logger.info(f"No available embedding enpoint!")

    logger.info("TEI Gaudi Embedding initialized.")
    opea_microservices["opea_service@embedding_tei_langchain"].start()
