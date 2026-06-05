# LLM Microservice

The LLM Microservice provides fast and efficient LLM inference capabilities using [vLLM](https://github.com/vllm-project/vllm). It supports both GPU and Intel hardware (CPUs and Gaudi accelerators), delivering state-of-the-art serving throughput with advanced features like PagedAttention and Continuous batching.

## Libs preparing (optional)

For development launching, make sure the libs "opea_cores" have been built at ../../libs, and the wheel package file is available at ../../libs/dist/, the building commmand can be:

  ```cd ../../libs; uv build```

If you want to build the container image directly, need not care about this step.

## Launching for Development

Before launching the app, please copy file env.example to .env, and check the values inside .env file.
Then just run ```uv run uvicorn src.main:app --reload --port 9001 --host 0.0.0.0```

In production environment, the cli is different in Dockerfile, but it's the same as:
```uv run -m src.main```

## Container image building

Go to ../../../scripts/build.all.images dir, run ```docker compose build llm-new```

## Deployment

Go to ../../../deployment/docker-compose/ekba/ dir, run ```docker compose up llm-new```
Also need to check the ENV settings in the .env file under this deployment dir.

## Service Verification

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

**For more query examples, please refer to example-query.sh.**

### Health Check

```bash
curl http://localhost:9001/v1/health_check \
  -X GET \
  -H 'Content-Type: application/json'
```

### Query Examples

1. **Non-streaming Mode**
```bash
curl -x "" http://localhost:9001/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}]}'
```

2. **Streaming Mode**
```bash
curl -x "" http://localhost:9001/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "stream": true,
        "stream_options": {"include_usage": true}}'
```

3. **Chat with history**
```bash
curl -x "" http://localhost:9001/v1/chat/completions \
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
```

4. **Chat with Retrieved Documents**
```bash
curl -x "" http://localhost:9001/v1/chat/completions   \
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
  
curl -x "" http://localhost:9001/v1/chat/completions   \
    -X POST   \
    -d '{
        "initial_query":"What is Deep Learning?",
        "retrieved_docs": [],
        "stream":true,
        "stream_options": {"include_usage": true}}' \
    -H 'Content-Type: application/json'
```
