# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

your_ip="localhost"
your_port="9001"

# ---------------------------------------------------------------------------------
# test ChatCompletionRequest

# non-streaming mode
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}]}'

# streaming mode
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "max_tokens": 10,
        "stream": true,
        "stream_options": {"include_usage": true}}'

curl -x "" http://${your_ip}:${your_port}/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "stream": true,
        "stream_options": {"include_usage": true}}'

# chat with history
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions \
  -X POST \
  -d '{
   "messages":[
   {
    "role":"user",
    "content":"who are you",
    "time":"1746682671"
    },
   {
    "role":"assistant",
    "content":"How can I assist you today? 😊",
    "time":"1746682678",
    "token_usage":{"prompt_tokens":12,"completion_tokens":218,"total_tokens":230},
    "feedback":"",
    "current_references":[]
    },
   {
    "role":"user",
    "content":"what is deep learning"
    }],
    "stream":true,
    "stream_options": {"include_usage": true}}' \
  -H 'Content-Type: application/json'

# ---------------------------------------------------------------------------------
# test LLMParamsDoc

# non-streaming mode
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions   \
    -X POST   \
    -d '{
        "query":"What is Deep Learning?"}' \
    -H 'Content-Type: application/json'

# streaming mode
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions   \
    -d '{
        "query":"What is Deep Learning?",
        "max_tokens":10,
        "stream":true,
        "stream_options": {"include_usage": true}}' \
    -H 'Content-Type: application/json'

curl -x "" http://${your_ip}:${your_port}/v1/chat/completions   \
    -X POST   \
    -d '{
        "query":"What is Deep Learning?",
        "stream":true,
        "stream_options": {"include_usage": true}}' \
    -H 'Content-Type: application/json'

# -----------------------------------------------------------------------------------
# test SearchedDoc

# non-streaming mode
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions   \
    -X POST   \
    -d '{
        "initial_query":"What is Deep Learning?",
        "retrieved_docs": []}' \
    -H 'Content-Type: application/json'

# streaming mode with retrieved_docs
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions   \
    -X POST   \
    -d '{
        "initial_query":"What is Deep Learning?",
        "retrieved_docs": [
            {
                "title": "Deep Learning Overview",
                "text": "Deep learning is a subset of machine learning that uses neural networks with many layers to analyze various factors of data."
            },
            {
                "title": "Applications of Deep Learning",
                "text": "Deep learning is used in image recognition, natural language processing, and more."
            }
        ],
        "max_tokens":10,
        "stream":true,
        "stream_options": {"include_usage": true}}' \
    -H 'Content-Type: application/json'

curl -x "" http://${your_ip}:${your_port}/v1/chat/completions   \
    -X POST   \
    -d '{
        "initial_query":"What is Deep Learning?",
        "retrieved_docs": [
            {
                "title": "Deep Learning Overview",
                "text": "Deep learning is a subset of machine learning that uses neural networks with many layers to analyze various factors of data."
            },
            {
                "title": "Applications of Deep Learning",
                "text": "Deep learning is used in image recognition, natural language processing, and more."
            }
        ],
        "stream":true,
        "stream_options": {"include_usage": true}}' \
    -H 'Content-Type: application/json'

# streaming mode without retrieved_docs
curl -x "" http://${your_ip}:${your_port}/v1/chat/completions   \
    -X POST   \
    -d '{
        "initial_query":"What is Deep Learning?",
        "retrieved_docs": [],
        "stream":true,
        "stream_options": {"include_usage": true}}' \
    -H 'Content-Type: application/json'