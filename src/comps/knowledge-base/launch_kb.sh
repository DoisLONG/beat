#!/bin/bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

export KB_SERVICE_PORT=9923

export EMBEDDING_BASE_URL="http://10.239.75.251:3008/v3"
export EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5"
export RETRIEVER_BASE_URL="http://10.239.75.251:7000/v1"


docker run -d --rm --name="kb-service" \
       -p 9923:9923 \
       --network=host \
       -e EMBEDDING_BASE_URL=${EMBEDDING_BASE_URL} \
       -e EMBEDDING_MODEL=${EMBEDDING_MODEL} \
       -e RETRIEVER_BASE_URL=${RETRIEVER_BASE_URL} \
       -e KB_SERVICE_PORT=${KB_SERVICE_PORT} \
       localhost:5000/ekba/knowledge-base:latest
