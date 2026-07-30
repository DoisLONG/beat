#!/bin/bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
MODEL_PATH=${LLM_MODEL:-"/llm/models/DeepSeek-R1-Distill-Qwen-32B"}
SERVED_MODEL_NAME=${LLM_MODEL:-"DeepSeek-R1-Distill-Qwen-32B"}
TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE:-4}  # Default to 2 if not set

echo "Starting service with model: $LLM_MODEL"
echo "Served model name: $LLM_MODEL"
echo "Tensor parallel size: $TENSOR_PARALLEL_SIZE"

export CCL_WORKER_COUNT=${TENSOR_PARALLEL_SIZE}
export SYCL_CACHE_PERSISTENT=1
export FI_PROVIDER=shm
export CCL_ATL_TRANSPORT=ofi
export CCL_ZE_IPC_EXCHANGE=sockets
export CCL_ATL_SHM=1

export USE_XETLA=OFF
export SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=2
export TORCH_LLM_ALLREDUCE=0

export CCL_SAME_STREAM=1
export CCL_BLOCKING_WAIT=0

source /opt/intel/1ccl-wks/setvars.sh

python -m ipex_llm.vllm.xpu.entrypoints.openai.api_server \
  --served-model-name $SERVED_MODEL_NAME \
  --port 80 \
  --model $MODEL_PATH \
  --trust-remote-code \
  --block-size 8 \
  --gpu-memory-utilization 0.9 \
  --device xpu \
  --dtype float16 \
  --enforce-eager \
  --load-in-low-bit fp8 \
  --max-model-len 20000 \
  --max-num-batched-tokens 20000 \
  --max-num-seqs 256 \
  --tensor-parallel-size $TENSOR_PARALLEL_SIZE \
  --disable-async-output-proc \
  --distributed-executor-backend ray
