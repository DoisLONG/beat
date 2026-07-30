#!/usr/bin/env bash

# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# helper function to give the text some colors
function _coloring() {
    local color=$1
    shift
    echo -ne "\033[${color}m$@\033[0m"
}

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

# Host IP
detected_host_ip=$(ip route get 1 | awk '{print $(NF-2);exit}')
confirm_or_new "host_ip" $detected_host_ip "Please make sure this IP is reachable from containers"

# TAG of container images, mostly "latest" cannot work, need to specify a good one
confirm_or_new "TAG" "latest" "TAG of container images, mostly 'latest' cannot work, need to specify a good one"

# default container registry to localhost, need to use a valid one if no local registry
confirm_or_new "REGISTRY" "localhost:5000" "default container registry to localhost, need to use a valid one if no local registry"

# vLLM endpoint
confirm_or_new "vLLM_ENDPOINT" "http://${host_ip}:18008" "Some local vLLM setup or public API endpoint"

# LLM model id, it's very possible to be changed!
confirm_or_new "LLM_MODEL" "/weights/DeepSeek-R1-BF8-Gaudi2d" "LLM model id, it's very possible to be changed!"

# choose it from "ovms" or "tei"
confirm_or_new "EMBEDDING_RERANKER_BACKEND" "ovms" "choose it from 'ovms' or 'tei'"

# confirm TIMEZONE
confirm_or_new "TIMEZONE" "Asia/Shanghai" "TIMEZONE of the hosts"

# exposed ports
confirm_or_new "EKBA_UI_PORT" "5174" "EKBA Chatbot UI listening port"
confirm_or_new "EAP_RETRIEVER_PORT" "17001" "EAP Retriever listening port"

# TOTAL_ROUNDS
confirm_or_new "TOTAL_ROUNDS" "10" "Total training rounds"

# TRAIN_LLM_ENDPOINT
confirm_or_new "TRAIN_LLM_ENDPOINT" "https://dashscope.aliyuncs.com/compatible-mode" "Training LLM endpoint"

# TRAIN_LLM_MODEL
confirm_or_new "TRAIN_LLM_MODEL" "qwen3-235b-a22b-instruct-2507" "Training LLM model"

# QWEN_API_KEY (no default, must input)
read -p "Please input $(_coloring 33 QWEN_API_KEY): " QWEN_API_KEY
while [ -z "$QWEN_API_KEY" ]; do
    echo $(_coloring 31 "QWEN_API_KEY cannot be empty!")
    read -p "Please input $(_coloring 33 QWEN_API_KEY): " QWEN_API_KEY
done

cat <<EOF > .env

host_ip=${host_ip}
TAG=${TAG}
REGISTRY=${REGISTRY}
vLLM_ENDPOINT=${vLLM_ENDPOINT}
LLM_MODEL=${LLM_MODEL}
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

# for llm-usvc config
FILTER_QUERIES=0

# chathistory config
MONGO_HOST=mongodb
MONGO_PORT=27017
MONGO_DB_NAME="OPEA_EAP"
MONGO_COLLECTION_NAME="ChatHistory"

# Huggingface ENDPOINT and token config
HF_ENDPOINT="https://hf-mirror.com"
HUGGINGFACEHUB_API_TOKEN="you-huggingface-token" # optional

## !! need ONLY to choose ONE of the following two sections
## !! for different flavors: OVMS or Huggingface TEI

# OVMS embedding and reranking config
OVMS_EMBEDDING_ENDPOINT="http://${host_ip}:13020/v3"
OVMS_EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5"
embedding_ctx_length=510
OVMS_RERANKING_ENDPOINT="http://${host_ip}:13010/v3"
OVMS_RERANKING_MODEL="BAAI/bge-reranker-large"

# HF TEI embedding and reranking config
TEI_EMBEDDING_ENDPOINT="http://${host_ip}:13020"
LOCAL_EMBEDDING_MODEL="BAAI/bge-base-zh-v1.5/"
TEI_RERANKING_ENDPOINT="http://${host_ip}:13010"
RERANK_MODEL_ID="BAAI/bge-reranker-base/"

# RERANKING outstanding score config
OUTSTANDING_SCORE=0

# TRAIN
TOTAL_ROUNDS=${TOTAL_ROUNDS}
TRAIN_LLM_ENDPOINT=${TRAIN_LLM_ENDPOINT}
TRAIN_LLM_MODEL=${TRAIN_LLM_MODEL}
QWEN_API_KEY=${QWEN_API_KEY}

EOF

echo "Generated .env file, please open .env file to double check the configs"
