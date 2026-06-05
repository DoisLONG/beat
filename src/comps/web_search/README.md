# Web_search Microservice

This microservice is responsible for web_search.

## 🚀 Service Usage Guide

> **Note:** The examples below use `localhost` and specific ports applicable for Docker deployment. For Kubernetes deployment:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

### 1. Start the Service

#### **Using Docker**
Run the following command to start the web_search service in a Docker container:
```bash
docker build -t web_search -f ./comps/web_search/Dockerfile .

docker run -d \
  --name web_search \
  -p 7050:7050 \
  -e BING_API_KEY=d41d328a36aa498abe25a7ee9864126c \
  -e GOOGLE_API_KEY=d41d328a36aa498abe25a7ee9864126c \
  -e GOOGLE_CX= \
  -e SEARCH_ENGINE_ORDER=duckduckgo,bing,google \
   web_search
```

### 2. WEB_SEARCH by links

You can send URLs to be web_search using a `POST` request:
```bash
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"text": "openvino如何做文生图"}' \
    http://localhost:7050/v1/web_search
```