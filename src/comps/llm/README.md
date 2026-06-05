# vLLM Microservice

The vLLM Microservice provides fast and efficient LLM inference capabilities using [vLLM](https://github.com/vllm-project/vllm). It supports both GPU and Intel hardware (CPUs and Gaudi accelerators), delivering state-of-the-art serving throughput with advanced features like PagedAttention and Continuous batching.

## Service Usage Guide

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

### Check Service Status

```bash
curl -X POST http://localhost:8008/v1/chat/completions \
 -H "Content-Type: application/json" \
 -d '{
    "model": "/weights/Meta-Llama-3-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Deep Learning?"}],
    "max_tokens": 128,
    "temperature": 0,
    "stream": true
    }'
```

### Query Examples

1. **Non-streaming Mode**
```bash
curl http://localhost:9000/v1/chat/completions \
  -X POST \
  -d '{"query":"What is Deep Learning?","max_new_tokens":17,"top_p":0.95,"temperature":0.01,"streaming":false}' \
  -H 'Content-Type: application/json'
```

2. **Streaming Mode**
```bash
curl http://localhost:9000/v1/chat/completions \
  -X POST \
  -d '{"query":"What is Deep Learning?","max_new_tokens":17,"top_k":10,"top_p":0.95,"typical_p":0.95,"temperature":0.01,"repetition_penalty":1.03,"streaming":true}' \
  -H 'Content-Type: application/json'
```

3. **Custom Chat Template**
```bash
curl http://localhost:9000/v1/chat/completions \
  -X POST \
  -d '{"query":"What is Deep Learning?","max_new_tokens":17,"top_k":10,"top_p":0.95,"typical_p":0.95,"temperature":0.01,"repetition_penalty":1.03,"streaming":true, "chat_template":"### You are a helpful, respectful and honest assistant to help the user with questions.\n### Context: {context}\n### Question: {question}\n### Answer:"}' \
  -H 'Content-Type: application/json'
```

4. **Chat with Retrieved Documents**
```bash
curl http://localhost:9000/v1/chat/completions \
  -X POST \
  -d '{"initial_query":"What is Deep Learning?","retrieved_docs":[{"text":"Deep Learning is a ..."},{"text":"Deep Learning is b ..."}]}' \
  -H 'Content-Type: application/json'
```
