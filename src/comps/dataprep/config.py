# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from comps.system_common.model import ModelConfigScope
from comps.system_common.resolver import get_cached_config_resolver

from openai import OpenAI

def get_dataprep_llm_config(refresh: bool = False):
    resolver = get_cached_config_resolver()
    return resolver.resolve(ModelConfigScope.DATAPREP_LLM, refresh=refresh)

def get_client(refresh: bool = False):
    config = get_dataprep_llm_config(refresh=refresh)
    api_key = config.api_key.get_secret_value() if config.api_key else MODEL_API_KEY
    base_url = config.base_url if config.base_url else MODEL_BASE_URL
    return OpenAI(api_key=api_key, base_url=base_url)

def get_embedding_config(refresh: bool = False):
    resolver = get_cached_config_resolver()
    return resolver.resolve(ModelConfigScope.EMBEDDING, refresh=refresh)

def get_llm_extra_body(model_name: str):
    if model_name.lower() in ["qwen3-235b-a22b", "qwen/qwen3-32b"]:
        return {
            "chat_template_kwargs": {
                "enable_thinking": False
            }
        }
    return {
        "enable_thinking": False
    }

# Local Embedding model
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "maidalun1020/bce-embedding-base_v1")
# TEI Embedding endpoints
TEI_EMBEDDING_ENDPOINT = os.getenv("TEI_EMBEDDING_ENDPOINT", "")
# BAILIAN Embedding endpoints
BAILIAN_EMBEDDING_ENDPOINT = os.getenv("BAILIAN_EMBEDDING_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
BAILIAN_EMBEDDING_MODEL = os.getenv("BAILIAN_EMBEDDING_MODEL", "text-embedding-v4")
BAILIAN_EMBEDDING_API_KEY = os.getenv("BAILIAN_EMBEDDING_API_KEY", "")

# MILVUS configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", 19530))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_milvus")
# Redis配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 16379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "Eap@dfxw2025")
# MOSEC configuration
MOSEC_EMBEDDING_MODEL = os.environ.get("MOSEC_EMBEDDING_MODEL", "/home/user/bge-large-zh-v1.5")
MOSEC_EMBEDDING_ENDPOINT = os.environ.get("MOSEC_EMBEDDING_ENDPOINT", "")

# OVMS embedding
OVMS_EMBEDDING_ENDPOINT = os.environ.get("OVMS_EMBEDDING_ENDPOINT", "")
OVMS_EMBEDDING_MODEL = os.environ.get("OVMS_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
embedding_ctx_length = os.environ.get("embedding_ctx_length", 470)

# MODEL 配置 (Now using lazy resolver)
def get_llm_model_name():
    return get_dataprep_llm_config().model

def get_model_base_url():
    return get_dataprep_llm_config().base_url

def get_model_api_key():
    config = get_dataprep_llm_config()
    return config.api_key.get_secret_value() if config.api_key else ""

# Static env defaults for dataprep_llm scope
LLM_MODEL_NAME = os.environ.get("DATAPREP_LLM_MODEL", "qwen-max")
MODEL_BASE_URL = os.environ.get("DATAPREP_LLM_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL_API_KEY = os.environ.get("DATAPREP_LLM_API_KEY", "your-key")

# MYSQL配置
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 13306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Eap@dfxw2025")
MYSQL_DB = os.getenv("MYSQL_DB", "ekba_kb")

MYSQL_CONFIG = {
    "host": MYSQL_HOST,
    "port": MYSQL_PORT,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "db": MYSQL_DB
}

LLM_EXTRA_BODY = get_llm_extra_body(LLM_MODEL_NAME)

ACCESS_KEY_ID = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
# aliyun or local
DATA_LOADER_TYPE = os.getenv("DATA_LOADER_TYPE", "local")
FILES_STORED_TYPE = os.getenv("FILES_STORED_TYPE", "minio")
TOTAL_ROUNDS = int(os.getenv("TOTAL_ROUNDS", 10))

# Remote magic-pdf parse config
MAGIC_PDF_REMOTE_ENABLED = os.getenv("MAGIC_PDF_REMOTE_ENABLED", "true").strip().lower() not in {
    "0", "false", "off", "no"
}
MAGIC_PDF_PARSE_URL = os.getenv("MAGIC_PDF_PARSE_URL", "")
MAGIC_PDF_PARSE_METHOD = os.getenv("MAGIC_PDF_PARSE_METHOD", "auto")
MAGIC_PDF_PARSE_LANG = os.getenv("MAGIC_PDF_PARSE_LANG", "ch_server")
MAGIC_PDF_PARSE_CONNECT_TIMEOUT = float(os.getenv("MAGIC_PDF_PARSE_CONNECT_TIMEOUT", "10"))
MAGIC_PDF_PARSE_READ_TIMEOUT = float(
    os.getenv("MAGIC_PDF_PARSE_READ_TIMEOUT", os.getenv("MAGIC_PDF_PARSE_TIMEOUT", "600"))
)
MAGIC_PDF_PARSE_RETRIES = max(0, int(os.getenv("MAGIC_PDF_PARSE_RETRIES", "2")))
MAGIC_PDF_PARSE_RETRY_BACKOFF_SECONDS = float(os.getenv("MAGIC_PDF_PARSE_RETRY_BACKOFF_SECONDS", "1.5"))
DATAPREP_QA_CONCURRENCY_LIMIT = int(os.getenv("DATAPREP_QA_CONCURRENCY_LIMIT", 3))