# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import dotenv
dotenv.load_dotenv()

from opea_cores import CustomLogger

# MILVUS configuration
_MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
_MILVUS_PORT = int(os.getenv("MILVUS_PORT", 19530))
CONNECTION_ARGS = {
    "uri": f"http://{_MILVUS_HOST}:{_MILVUS_PORT}"
}

logger = CustomLogger("retriever-new", os.getenv("LOG_LEVEL", "INFO"))

KBS_INFO_DIR = os.environ.get('KBS_INFO_DIR', '/tmp/kbs-info')
if not os.path.exists(KBS_INFO_DIR):
    os.makedirs(KBS_INFO_DIR)

def init_embedding_function():
    # OVMS or TEI
    EMBEDDING_RERANKER_BACKEND = os.getenv("EMBEDDING_RERANKER_BACKEND", "OVMS")

    # OVMS embedding settings
    OVMS_EMBEDDING_ENDPOINT = os.environ.get("OVMS_EMBEDDING_ENDPOINT", "")
    OVMS_EMBEDDING_MODEL = os.environ.get("OVMS_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    embedding_ctx_length = os.environ.get("embedding_ctx_length",510)

    # TEI Embedding endpoints
    TEI_EMBEDDING_ENDPOINT = os.getenv("TEI_EMBEDDING_ENDPOINT", "")


    if EMBEDDING_RERANKER_BACKEND.lower() == "ovms":
        from langchain_openai import OpenAIEmbeddings

        logger.info(f"OVMS_EMBEDDING_ENDPOINT:{OVMS_EMBEDDING_ENDPOINT}")

        # create embeddings using OVMS endpoint service
        em_func = OpenAIEmbeddings(
            model=OVMS_EMBEDDING_MODEL,
            api_key="unused",
            base_url=OVMS_EMBEDDING_ENDPOINT,
            tiktoken_enabled=False,
            embedding_ctx_length=embedding_ctx_length
        )
        logger.debug(f"embedding_function:{em_func}")

    elif EMBEDDING_RERANKER_BACKEND.lower() == "tei":
        from langchain_community.embeddings import HuggingFaceHubEmbeddings

        # create embeddings using TEI endpoint service
        logger.info(f"TEI_EMBEDDING_ENDPOINT:{TEI_EMBEDDING_ENDPOINT}")

        em_func = HuggingFaceHubEmbeddings(model=TEI_EMBEDDING_ENDPOINT) # TODO wrong parameter?
        logger.debug(f"embedding_function:{em_func}")

    else:
        # unsupported embedding model
        logger.error("Unsupported embedding model")
        sys.exit(1)

    return em_func

# global var for embedding function
embedding_function = init_embedding_function()
