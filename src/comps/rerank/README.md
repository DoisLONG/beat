# Reranking Microservice

The Reranking Microservice enhances semantic search capabilities by reordering documents based on their relevance to a query. In a text retrieval system, after initial document retrieval (via dense embedding or sparse lexical search), the reranking model refines the results by optimizing their final order based on semantic relevance.

## 📡 API Usage

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

Test the service using any of these endpoints:

```bash
# OVMS Backend
curl http://localhost:8010/v3/rerank \
 -H "Content-Type: application/json" \
 -d '{"model": "BAAI/bge-reranker-large", "query": "What is Deep Learning?", "documents": ["Deep Learning is not...", "Deep learning is..."]}'

# TEI Backend
curl http://localhost:8808/rerank \
 -H "Content-Type: application/json" \
 -d '{"query": "What is Deep Learning?", "documents": ["Deep Learning is not...", "Deep learning is..."]}'

# OPEA Service Endpoint
curl http://localhost:8000/v1/reranking \
  -X POST \
  -d '{"initial_query":"What is Deep Learning?", "retrieved_docs": [{"text":"Deep Learning is not..."}, {"text":"Deep learning is..."}]}' \
  -H 'Content-Type: application/json'
```
