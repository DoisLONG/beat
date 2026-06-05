# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

your_ip="localhost"
your_port="8888"

# non-streaming mode
curl http://${your_ip}:${your_port}/v1/chatqna \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "collection_name":"kb"}'

# streaming mode
curl http://${your_ip}:${your_port}/v1/chatqna \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "collection_name":"kb",
        "stream": true,
        "stream_options": {"include_usage": true}}'

curl http://${your_ip}:${your_port}/v1/chatqna \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "collection_name":"kb",
        "stream": true,
        "max_tokens": 10,
        "stream_options": {"include_usage": true}}'

# streaming mode with history
curl -x "" http://${your_ip}:${your_port}/v1/chatqna \
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
    "collection_name":"kb",
    "stream":true,
    "stream_options": {"include_usage": true}}' \
  -H 'Content-Type: application/json'