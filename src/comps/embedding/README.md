# Embedding Microservice

The Embedding Microservice provides text embedding generation capabilities using state-of-the-art language models. It supports two deployment modes:

- **TEI Mode**: Uses Transformers Embedding Interface for standard CPU inference
- **OpenVINO Mode**: Uses OpenVINO optimization for accelerated inference on Intel hardware

## Service Usage Guide

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

### Check Service Status

Verify if the service is running properly:

```bash
curl http://localhost:6000/v1/health_check \
  -X GET \
  -H 'Content-Type: application/json'
```

### Generate Embeddings

Generate embeddings for input text (works the same way for both modes):

```bash
curl http://localhost:6000/v1/embeddings \
  -X POST \
  -d '{"text":"hello"}' \
  -H 'Content-Type: application/json'
```

Example response:
```json
{
    "embedding": [0.123, -0.456, 0.789, ...],
    "text": "hello"
}
```
