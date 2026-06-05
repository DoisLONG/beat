# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

from comps.system_common.resolver import get_cached_config_resolver, ModelConfigScope

# Local Embedding model
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "maidalun1020/bce-embedding-base_v1")
# TEI Embedding endpoints
TEI_EMBEDDING_ENDPOINT = os.getenv("TEI_EMBEDDING_ENDPOINT", "")

# Env fallbacks (will be handled by resolver, but kept here for explicit reference if needed)
BAILIAN_EMBEDDING_ENDPOINT = os.getenv("BAILIAN_EMBEDDING_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
BAILIAN_EMBEDDING_MODEL = os.getenv("BAILIAN_EMBEDDING_MODEL", "text-embedding-v4")
BAILIAN_EMBEDDING_API_KEY = os.getenv("BAILIAN_EMBEDDING_API_KEY", "sk-50f1809932d54d958040350ac90bec60")

# MILVUS configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", 19530))
MILVUS_COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_milvus")
# OVMS embedding
OVMS_EMBEDDING_ENDPOINT = os.environ.get("OVMS_EMBEDDING_ENDPOINT", "")
OVMS_EMBEDDING_MODEL = os.environ.get("OVMS_EMBEDDING_MODEL", "bge-large-zh-v1.5")
embedding_ctx_length = os.environ.get("embedding_ctx_length",470)
# Redis配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 16379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "Eap@dfxw2025")
TIME_LIMIT = os.environ.get("TIME_LIMIT",600)
SESSION_REDIS_PREFIX = os.environ.get("SESSION_REDIS_PREFIX","exam:session:")
TIME_REDIS_PREFIX = os.environ.get("TIME_REDIS_PREFIX","exam:global_timer:")
# mongo配置
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", 27017)
DB_NAME = os.getenv("MONGO_DB_NAME", "OPEA_EAP")
USER_LOGS_COLLECTION_NAME = os.getenv("USER_LOGS_COLLECTION_NAME", "UserLogs")

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

# 运行配置
total_time = int(os.getenv("TOTAL_ROUNDS", 10))  # 总轮数
llm_endpoint = os.getenv("SMART_PRACTICE_LLM_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
model_name = os.getenv("SMART_PRACTICE_LLM_MODEL", "qwen-turbo")
openai_api_key = os.getenv("SMART_PRACTICE_LLM_API_KEY", "")
MILVUS_URI = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
index_params = {"index_type": "FLAT", "metric_type": "L2", "params": {}}

def get_llm_extra_body(model: str) -> dict:
    if model.lower() in ["qwen3-235b-a22b", "qwen/qwen3-32b"]:
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {"enable_thinking": False}

# Legacy static config (kept for backward compatibility where runtime resolution is not yet implemented)
LLM_EXTRA_BODY = get_llm_extra_body(model_name)

TOP_PUSH_URL = os.getenv("TOP_PUSH_URL", "http://dashboard:6020/api/dashboard/leaderboard/recalculate")
