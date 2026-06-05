# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

your_ip="localhost"

curl -x "" http://${your_ip}:8008/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "Qwen/Qwen2-72B-Instruct","messages": [{"role": "user", "content": "What is Deep Learning?"}], "max_tokens": 128, "temperature": 0, "stream": true }'

##query microservice
curl -x "" http://${your_ip}:9000/v1/chat/completions   \
    -X POST   \
    -d '{"query":"What is Deep Learning?","max_new_tokens":17,"top_k":10,"top_p":0.95,"typical_p":0.95,"temperature":0.01,"repetition_penalty":1.03,"streaming":true}' \
    -H 'Content-Type: application/json'
