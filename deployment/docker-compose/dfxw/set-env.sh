#!/usr/bin/env bash

# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# helper function to give the text some colors
function _coloring() {
    local color=$1
    shift
    echo -ne "\033[${color}m$@\033[0m"
}

DEFAULT_MODEL_CONFIG_ENCRYPTION_KEY="fd90Zn9EmvWbHtAyjP9bApzes-DtPcvHOXyAs-_QPjU="
DEFAULT_INTERNAL_API_KEY="sk-50f1809932d54d958040350ac90bec60"

# helper function to confirm default value
function confirm_or_new() {
    local var_name=$1
    local default_value=$2
    local hint=$3
    local answer

    # load current value from .env file
    local cur_value=$(grep -E "^${var_name}=" .env  2>/dev/null | cut -d'=' -f2)
    [[ -n "$cur_value" ]] && default_value=$cur_value

    [[ -n "$hint" ]] && echo $(_coloring 32 "Hint:") $hint
    read -p "To set $(_coloring 33 $var_name) as [$(_coloring 34 "$default_value")], press Enter to confirm, or type a new value: " answer
    if [ -z "$answer" ]; then
        eval "$var_name=$default_value"
    else
        eval "$var_name=$answer"
        echo "Using new value: $(_coloring 31 $answer)"
    fi
    echo
}

# helper function to accept hidden default value without showing it in prompt
function confirm_secret_or_default() {
    local var_name=$1
    local default_value=$2
    local hint=$3
    local answer

    local cur_value=$(grep -E "^${var_name}=" .env 2>/dev/null | cut -d'=' -f2-)
    [[ -n "$cur_value" ]] && default_value=$cur_value

    [[ -n "$hint" ]] && echo $(_coloring 32 "Hint:") $hint
    read -p "Please input $(_coloring 33 $var_name) (press Enter to use configured default): " answer
    if [ -z "$answer" ]; then
        eval "$var_name=\$default_value"
    else
        eval "$var_name=\$answer"
        echo "Using new value: $(_coloring 31 $answer)"
    fi
    echo
}

# Host IP
detected_host_ip=$(ip route get 1 | awk '{print $(NF-2);exit}')
confirm_or_new "host_ip" $detected_host_ip "Please make sure this IP is reachable from containers"

# TAG of container images, mostly "latest" cannot work, need to specify a good one
confirm_or_new "TAG" "latest" "TAG of container images, mostly 'latest' cannot work, need to specify a good one"

# default container registry for tagged local images
confirm_or_new "REGISTRY" "localhost:5000" "container registry prefix used by tagged local practice images"

# confirm TIMEZONE
confirm_or_new "TIMEZONE" "Asia/Shanghai" "TIMEZONE of the hosts"

# exposed ports
confirm_or_new "EKBA_UI_PORT" "5174" "EKBA Chatbot UI listening port"
confirm_or_new "EAP_RETRIEVER_PORT" "17001" "EAP Retriever listening port"

# dfxw interface address credentials
confirm_or_new "DFXW_BASE_URL" "" "DFXW_BASE_URL"
confirm_or_new "DFXW_TOKEN_URL" "" "DFXW_TOKEN_URL"
confirm_or_new "DFXW_CLIENT_ID" "" "DFXW_CLIENT_ID"
confirm_or_new "DFXW_CLIENT_SECRET" "" "DFXW_CLIENT_SECRET"
confirm_or_new "JWT_EXPIRATION_DELTA" "86400" "JWT expiration time in seconds"
confirm_or_new "MODEL_CONFIG_ENCRYPTION_KEYS" "${DEFAULT_MODEL_CONFIG_ENCRYPTION_KEY}" "Comma-separated Fernet keys for model-config secrets"

# TOTAL_ROUNDS
confirm_or_new "TOTAL_ROUNDS" "10" "Total training rounds"

# DATAPREP_QA_CONCURRENCY_LIMIT
confirm_or_new "DATAPREP_QA_CONCURRENCY_LIMIT" "3" "Dataprep QA generation concurrency limit"

# TIME_LIMIT
confirm_or_new "TIME_LIMIT" "600" "Practice time limit in seconds"

# BAILIAN_EMBEDDING_ENDPOINT
confirm_or_new "BAILIAN_EMBEDDING_ENDPOINT" "https://dashscope.aliyuncs.com/compatible-mode/v1" "BAILIAN EMBEDDING ENDPOINT"

# BAILIAN_EMBEDDING_MODEL
confirm_or_new "BAILIAN_EMBEDDING_MODEL" "text-embedding-v4" "BAILIAN EMBEDDING MODEL"

# BAILIAN_EMBEDDING_API_KEY
confirm_secret_or_default "BAILIAN_EMBEDDING_API_KEY" "${DEFAULT_INTERNAL_API_KEY}" "Internal default key is available and will be used if left empty"

# DATAPREP_LLM_ENDPOINT
confirm_or_new "DATAPREP_LLM_PROVIDER" "dashscope" "DATAPREP LLM provider"
confirm_or_new "DATAPREP_LLM_ENDPOINT" "https://dashscope.aliyuncs.com/compatible-mode/v1" "DATAPREP LLM ENDPOINT"

confirm_or_new "DATAPREP_LLM_MODEL" "qwen3-max" "DATAPREP LLM MODEL"
confirm_or_new "ASR_LLM_MODEL" "${DATAPREP_LLM_MODEL}" "ASR postprocess LLM model (defaults to DATAPREP_LLM_MODEL)"

# DATAPREP_LLM_API_KEY (no default, must input)
confirm_secret_or_default "DATAPREP_LLM_API_KEY" "${DEFAULT_INTERNAL_API_KEY}" "Internal default key is available and will be used if left empty"

# SMART_PRACTICE_LLM
confirm_or_new "SMART_PRACTICE_LLM_PROVIDER" "dashscope" "SMART PRACTICE LLM provider"
confirm_or_new "SMART_PRACTICE_LLM_ENDPOINT" "https://dashscope.aliyuncs.com/compatible-mode/v1" "SMART PRACTICE LLM endpoint"
confirm_or_new "SMART_PRACTICE_LLM_MODEL" "qwen-turbo" "SMART PRACTICE LLM model"

confirm_secret_or_default "SMART_PRACTICE_LLM_API_KEY" "${DEFAULT_INTERNAL_API_KEY}" "Internal default key is available and will be used if left empty"

# ASR (optional)
confirm_or_new "ASR_PROVIDER" "env" "ASR provider"
confirm_or_new "ASR_TRANSPORT" "http" "ASR transport: http or local"
confirm_or_new "ASR_API_KEY" "" "ASR API key"
confirm_or_new "ASR_RUNTIME_OPTIONS_JSON" "" "ASR runtime options JSON for local mode, e.g. {\"engine\":\"faster_whisper\",\"device\":\"auto\"}"
confirm_or_new "ASR_ENGINE" "qwen" "ASR engine, e.g. qwen or faster_whisper"
confirm_or_new "ASR_ENDPOINT" "https://183.95.195.121:31439/qwen3-asr/v1/audio/transcriptions" "Remote ASR transcription endpoint"
confirm_or_new "ASR_MODEL" "Qwen/Qwen3-ASR-1.7B" "ASR model name"
confirm_or_new "ASR_SSL_VERIFY" "false" "Verify TLS certificate when calling remote ASR? (true/false)"
if [ "$ASR_ENGINE" == "faster_whisper" ]; then
    confirm_or_new "ASR_WHISPER_MODEL_SIZE" "medium" "Local faster-whisper model size"
    confirm_or_new "ASR_WHISPER_DEVICE" "auto" "Local faster-whisper device, e.g. auto/cpu/cuda"
    confirm_or_new "ASR_WHISPER_COMPUTE_TYPE" "default" "Local faster-whisper compute type"
    confirm_or_new "ASR_WHISPER_MODEL_PATH" "/opt/models/faster-whisper-medium" "Mounted local faster-whisper model path"
    confirm_or_new "HF_HUB_OFFLINE" "1" "Disable model download and require local model files? (1/0)"
else
    ASR_WHISPER_MODEL_SIZE=""
    ASR_WHISPER_DEVICE=""
    ASR_WHISPER_COMPUTE_TYPE=""
    ASR_WHISPER_MODEL_PATH=""
    HF_HUB_OFFLINE=""
fi

# MAGIC_PDF_MODEL
confirm_or_new "MAGIC_PDF_MODEL_PATH" "/opt/models" "PDF MODEL PATH"
confirm_or_new "MAGIC_PDF_REMOTE_ENABLED" "true" "Enable remote magic-pdf parse"
confirm_or_new "MAGIC_PDF_PARSE_URL" "http://183.95.195.121:31439/magic-pdf/parse" "Magic-pdf parse URL"
confirm_or_new "MAGIC_PDF_PARSE_METHOD" "auto" "Magic-pdf parse method"
confirm_or_new "MAGIC_PDF_PARSE_LANG" "ch_server" "Magic-pdf parse language"

# 1. 首先询问存储类型
confirm_or_new "FILES_STORED_TYPE" "minio" "Storage type: oss or minio"

# 2. 根据存储类型进入分支
if [ "$FILES_STORED_TYPE" == "minio" ]; then
    echo $(_coloring 35 "--- Configuring MinIO Settings ---")

    confirm_or_new "MINIO_ENDPOINT" "${host_ip}:9000" "MinIO Endpoint (IP:PORT, no http://)"
    confirm_or_new "MINIO_ACCESS_KEY" "minioadmin" "MinIO Access Key"
    confirm_or_new "MINIO_SECRET_KEY" "minioadmin" "MinIO Secret Key"
    confirm_or_new "MINIO_BUCKET_NAME" "eap" "MinIO Bucket Name"
    confirm_or_new "MINIO_PREFIX" "ai-doc" "MinIO object prefix"
    confirm_or_new "MINIO_SECURE" "false" "Use HTTPS for MinIO? (true/false)"

    # 为 Docker Compose 设置兼容性变量
    MINIO_ROOT_USER=${MINIO_ACCESS_KEY}
    MINIO_ROOT_PASSWORD=${MINIO_SECRET_KEY}

    # OSS 变量设为空
    OSS_ENDPOINT=""
    OSS_BUCKET_NAME=""
    OSS_DEST_PREFIX=""
    ALIYUN_ACCESS_KEY_ID=""
    ALIYUN_ACCESS_KEY_SECRET=""

elif [ "$FILES_STORED_TYPE" == "oss" ]; then
    echo $(_coloring 35 "--- Configuring Aliyun OSS Settings ---")

    # MinIO 变量设为空
    MINIO_ENDPOINT=""
    MINIO_ACCESS_KEY=""
    MINIO_SECRET_KEY=""
    MINIO_BUCKET_NAME=""
    MINIO_PREFIX=""
    MINIO_SECURE=""
    MINIO_ROOT_USER=""
    MINIO_ROOT_PASSWORD=""

    confirm_or_new "OSS_ENDPOINT" "https://oss-cn-shanghai.aliyuncs.com" "OSS_ENDPOINT"
    confirm_or_new "OSS_BUCKET_NAME" "eh-shanghai-ai" "OSS_BUCKET_NAME"
    confirm_or_new "OSS_DEST_PREFIX" "ai-doc" "OSS_DEST_PREFIX"

    # OSS 必须输入的密钥
    read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_ID): " ALIYUN_ACCESS_KEY_ID
    while [ -z "$ALIYUN_ACCESS_KEY_ID" ]; do
        echo $(_coloring 31 "ALIYUN_ACCESS_KEY_ID cannot be empty!")
        read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_ID): " ALIYUN_ACCESS_KEY_ID
    done

    read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_SECRET): " ALIYUN_ACCESS_KEY_SECRET
    while [ -z "$ALIYUN_ACCESS_KEY_SECRET" ]; do
        echo $(_coloring 31 "ALIYUN_ACCESS_KEY_SECRET cannot be empty!")
        read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_SECRET): " ALIYUN_ACCESS_KEY_SECRET
    done
else
    echo $(_coloring 31 "Invalid FILES_STORED_TYPE! Please run again and choose 'minio' or 'oss'.")
    exit 1
fi

#  ALIYUN_ACCESS_KEY_ID (no default, must input)
#read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_ID): " ALIYUN_ACCESS_KEY_ID
#while [ -z "$ALIYUN_ACCESS_KEY_ID" ]; do
#    echo $(_coloring 31 "ALIYUN_ACCESS_KEY_ID cannot be empty!")
#    read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_ID): " ALIYUN_ACCESS_KEY_ID
#done
#
## ALIYUN_ACCESS_KEY_SECRET (no default, must input)
#read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_SECRET): " ALIYUN_ACCESS_KEY_SECRET
#while [ -z "$ALIYUN_ACCESS_KEY_SECRET" ]; do
#    echo $(_coloring 31 "ALIYUN_ACCESS_KEY_SECRET cannot be empty!")
#    read -p "Please input $(_coloring 33 ALIYUN_ACCESS_KEY_SECRET): " ALIYUN_ACCESS_KEY_SECRET
#done

cat <<EOF > .env

host_ip=${host_ip}
TAG=${TAG}
REGISTRY=${REGISTRY}
EMBEDDING_RERANKER_BACKEND=${EMBEDDING_RERANKER_BACKEND}
TIMEZONE=${TIMEZONE}
EKBA_UI_PORT=${EKBA_UI_PORT}
EAP_RETRIEVER_PORT=${EAP_RETRIEVER_PORT}

# set the ports for the exra services without asking
EKBA_DATAPREP_PORT=6007
EKBA_MINI_UI_PORT=5175

# log level default to be INFO
LOG_LEVEL=INFO

# Pipeline config: Enable/Disable Rerank service
ENABLE_RERANK=true

# Milvus config
MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530
COLLECTION_NAME="mes_sop"

# ui config
SOP_API_HOST=dataprep:6010
CHAT_API_HOST=smart-practice-usvc:9010
COMPANY_API_HOST=system-common:8010
CHAT_HISTORY_API_HOST=chathistory:6022
USER_API_HOST=account:9011
LEARN_API_HOST=learn:7010
VIDEO_API_HOST=video:8000
VIDEO_API_HOST_V2=excel:8001
DASHBOARD_API_HOST=dashboard:6020

# for llm-usvc config
FILTER_QUERIES=0

# chathistory config
MONGO_HOST=mongodb
MONGO_PORT=27017
MONGO_DB_NAME="OPEA_EAP"
MONGO_COLLECTION_NAME="ChatHistory"

# mysql config
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER="root"
MYSQL_PASSWORD="Eap@dfxw2025"
MYSQL_DB="ekba_kb"
MODEL_CONFIG_ENCRYPTION_KEYS=${MODEL_CONFIG_ENCRYPTION_KEYS}

# redis config
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_USER=""
REDIS_PASSWORD="Eap@dfxw2025"
REDIS_DB=0
SESSION_REDIS_PREFIX="sp:exam:session:"
TIME_REDIS_PREFIX="sp:exam:global_timer:"

DATA_LOADER_TYPE=${DATA_LOADER_TYPE}
FILES_STORED_TYPE=${FILES_STORED_TYPE}

# minio config
MINIO_ENDPOINT=${MINIO_ENDPOINT}
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
MINIO_BUCKET_NAME=${MINIO_BUCKET_NAME}
MINIO_PREFIX=${MINIO_PREFIX}
MINIO_SECURE=${MINIO_SECURE}
MINIO_ROOT_USER=${MINIO_ROOT_USER}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}

# oss config
ALIYUN_ACCESS_KEY_ID=${ALIYUN_ACCESS_KEY_ID}
ALIYUN_ACCESS_KEY_SECRET=${ALIYUN_ACCESS_KEY_SECRET}
OSS_ENDPOINT=${OSS_ENDPOINT}
OSS_BUCKET_NAME=${OSS_BUCKET_NAME}
OSS_DEST_PREFIX=${OSS_DEST_PREFIX}

# Huggingface ENDPOINT and token config
HF_ENDPOINT="https://hf-mirror.com"
HUGGINGFACEHUB_API_TOKEN="you-huggingface-token" # optional

## !! need ONLY to choose ONE of the following two sections
## !! for different flavors: OVMS or Huggingface TEI

# HF TEI embedding and reranking config
embedding_ctx_length=510

# RERANKING outstanding score config
OUTSTANDING_SCORE=0

# dataprep config
BAILIAN_EMBEDDING_ENDPOINT=${BAILIAN_EMBEDDING_ENDPOINT}
BAILIAN_EMBEDDING_MODEL=${BAILIAN_EMBEDDING_MODEL}
BAILIAN_EMBEDDING_API_KEY=${BAILIAN_EMBEDDING_API_KEY}

DATAPREP_LLM_ENDPOINT=${DATAPREP_LLM_ENDPOINT}
DATAPREP_LLM_MODEL=${DATAPREP_LLM_MODEL}
ASR_LLM_MODEL=${ASR_LLM_MODEL}
DATAPREP_LLM_API_KEY=${DATAPREP_LLM_API_KEY}
DATAPREP_LLM_PROVIDER=${DATAPREP_LLM_PROVIDER}

TOTAL_ROUNDS=${TOTAL_ROUNDS}
DATAPREP_QA_CONCURRENCY_LIMIT=${DATAPREP_QA_CONCURRENCY_LIMIT}
MAX_SUPPLEMENT_ROUNDS=3
TIME_LIMIT=${TIME_LIMIT}
SMART_PRACTICE_LLM_PROVIDER=${SMART_PRACTICE_LLM_PROVIDER}
SMART_PRACTICE_LLM_ENDPOINT=${SMART_PRACTICE_LLM_ENDPOINT}
SMART_PRACTICE_LLM_MODEL=${SMART_PRACTICE_LLM_MODEL}
SMART_PRACTICE_LLM_API_KEY=${SMART_PRACTICE_LLM_API_KEY}

ASR_PROVIDER=${ASR_PROVIDER}
ASR_MODEL=${ASR_MODEL}
ASR_TRANSPORT=${ASR_TRANSPORT}
ASR_ENDPOINT=${ASR_ENDPOINT}
ASR_API_KEY=${ASR_API_KEY}
ASR_RUNTIME_OPTIONS_JSON=${ASR_RUNTIME_OPTIONS_JSON}
ASR_ENGINE=${ASR_ENGINE}
ASR_SSL_VERIFY=${ASR_SSL_VERIFY}
ASR_DATA_DIR=/home/user/comps/asr/data
ASR_WHISPER_MODEL_SIZE=${ASR_WHISPER_MODEL_SIZE}
ASR_WHISPER_DEVICE=${ASR_WHISPER_DEVICE}
ASR_WHISPER_COMPUTE_TYPE=${ASR_WHISPER_COMPUTE_TYPE}
ASR_WHISPER_MODEL_PATH=${ASR_WHISPER_MODEL_PATH}
HF_HUB_OFFLINE=${HF_HUB_OFFLINE}
ASR_MAX_WORKERS=3
ASR_CHUNK_WORKERS=4
ASR_FFMPEG_SEGMENT_SECONDS=300
ASR_REFINE_BATCH_SIZE=10
REFINE_BATCH_WORKERS=3

EXCEL_ASR_BASE_URL=http://video:8000
EXCEL_EXECUTOR_WORKERS=2
SOP_UPLOAD_URL=http://dataprep:6010/v1/dataprep/generate_qa
SOP_UPLOAD_FILE_FIELD=files
SOP_UPLOAD_FILE_TYPE=sop
SOP_UPLOAD_AUTH_HEADER=
SOP_UPLOAD_ENABLED=true

DFXW_BASE_URL=${DFXW_BASE_URL}
DFXW_TOKEN_URL=${DFXW_TOKEN_URL}
DFXW_CLIENT_ID=${DFXW_CLIENT_ID}
DFXW_CLIENT_SECRET=${DFXW_CLIENT_SECRET}
JWT_EXPIRATION_DELTA=${JWT_EXPIRATION_DELTA}

# MAGIC_PDF_MODEL_PATH
MAGIC_PDF_MODEL_PATH=${MAGIC_PDF_MODEL_PATH}
MAGIC_PDF_REMOTE_ENABLED=${MAGIC_PDF_REMOTE_ENABLED}
MAGIC_PDF_PARSE_URL=${MAGIC_PDF_PARSE_URL}
MAGIC_PDF_PARSE_METHOD=${MAGIC_PDF_PARSE_METHOD}
MAGIC_PDF_PARSE_LANG=${MAGIC_PDF_PARSE_LANG}
MAGIC_PDF_PARSE_CONNECT_TIMEOUT=${MAGIC_PDF_PARSE_CONNECT_TIMEOUT}
MAGIC_PDF_PARSE_TIMEOUT=${MAGIC_PDF_PARSE_TIMEOUT}
MAGIC_PDF_PARSE_READ_TIMEOUT=${MAGIC_PDF_PARSE_READ_TIMEOUT}
MAGIC_PDF_PARSE_RETRIES=${MAGIC_PDF_PARSE_RETRIES}
MAGIC_PDF_PARSE_RETRY_BACKOFF_SECONDS=${MAGIC_PDF_PARSE_RETRY_BACKOFF_SECONDS}
TGI_LLM_ENDPOINT=${TGI_LLM_ENDPOINT}
SUMMARIZE_IMAGE_VIA_LVM=${SUMMARIZE_IMAGE_VIA_LVM}
LOGFLAG=true
MAGIC_PDF_PARSE_CONNECT_TIMEOUT=10
MAGIC_PDF_PARSE_TIMEOUT=600
MAGIC_PDF_PARSE_READ_TIMEOUT=600
MAGIC_PDF_PARSE_RETRIES=2
MAGIC_PDF_PARSE_RETRY_BACKOFF_SECONDS=1.5

EOF

echo "Generated .env file, please open .env file to double check the configs"

# 创建 ASR 和 dataprep 所需目录
echo "Setting up local volume directories..."
VIDEO_DATA_DIR="./video_data"
EXCEL_DATA_DIR="./excel_data"
UPLOAD_DIR="./upload_files"

mkdir -p \
    "$VIDEO_DATA_DIR/uploads" \
    "$VIDEO_DATA_DIR/jobs" \
    "$VIDEO_DATA_DIR/asr" \
    "$VIDEO_DATA_DIR/results" \
    "$VIDEO_DATA_DIR/tmp" \
    "$EXCEL_DATA_DIR/jobs" \
    "$EXCEL_DATA_DIR/output" \
    "$EXCEL_DATA_DIR/tmp" \
    "$UPLOAD_DIR"

echo "Ensured local volume directories exist:"
echo "  - $VIDEO_DATA_DIR"
echo "  - $EXCEL_DATA_DIR"
echo "  - $UPLOAD_DIR"
