# Router Microservice

The Router is a pipeline tool based on opea-cores, which can integrate services into a complete chat QnA solution.

## Libs preparing (optional)

For development launching, make sure the libs "opea_cores" have been built at ../../libs, and the wheel package file is available at ../../libs/dist/, the building commmand can be:

  ```cd ../../libs; uv build```

If you want to build the container image directly, need not care about this step.

## Launching for Development

Before launching the app, please copy file env.example to .env, and check the values inside .env file.
Then just run ```uv run -m src.main```

## Container image building

Go to ../../../scripts/build.all.images dir, run ```docker compose build router-new```

## Deployment

Go to ../../../deployment/docker-compose/ekba/ dir, run ```docker compose up router-new```
Also need to check the ENV settings in the .env file under this deployment dir.

## Service Verification

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service


**For more query examples, please refer to example-query.sh.**

### Query Examples

1. **Non-streaming Mode**
```bash
curl http://localhost:8888/v1/chatqna \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "collection_name":"kb"}'
```

2. **Streaming Mode**
```bash
curl http://localhost:8888/v1/chatqna \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [{"role": "user", "content": "What is Deep Learning?"}],
        "collection_name":"kb",
        "stream": true,
        "stream_options": {"include_usage": true}}'
```

3. **Chat with history**
```bash
curl -x "" http://localhost:8888/v1/chatqna \
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
```