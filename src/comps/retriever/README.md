# Retriever Microservice with Milvus

The Retriever Microservice provides vector similarity search capabilities using Milvus as the backend. It enables efficient retrieval of semantically similar documents based on vector embeddings.

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

## Service Verification

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

### Health Check

```bash
curl http://localhost:7000/v1/health_check \
  -X GET \
  -H 'Content-Type: application/json'
```

### Retrieval Examples

> **Note:** In the examples below, `rag_milvus` is just a sample collection name. You can replace it with any collection name of your choice.

#### Basic Retrieval
```bash
# Generate a mock embedding vector
export your_embedding=$(python -c "import random; embedding = [random.uniform(-1, 1) for _ in range(768)]; print(embedding)")

curl http://localhost:7000/v1/retrieval \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"What is the revenue of Nike in 2023?\",
    \"embedding\": $your_embedding,
    \"collection_name\": \"rag_milvus\"
  }"
```

#### Similarity Search with K
```bash
curl http://localhost:7000/v1/retrieval \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"What is the revenue of Nike in 2023?\",
    \"embedding\": $your_embedding,
    \"search_type\": \"similarity\",
    \"k\": 4,
    \"collection_name\": \"rag_milvus\"
  }"
```

#### Similarity Search with Distance Threshold
```bash
curl http://localhost:7000/v1/retrieval \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"What is the revenue of Nike in 2023?\",
    \"embedding\": $your_embedding,
    \"search_type\": \"similarity_distance_threshold\",
    \"k\": 4,
    \"distance_threshold\": 1.0,
    \"collection_name\": \"rag_milvus\"
  }"
```

#### Similarity Search with Score Threshold
```bash
curl http://localhost:7000/v1/retrieval \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"What is the revenue of Nike in 2023?\",
    \"embedding\": $your_embedding,
    \"search_type\": \"similarity_score_threshold\",
    \"k\": 4,
    \"score_threshold\": 0.2,
    \"collection_name\": \"rag_milvus\"
  }"
```

#### MMR (Maximal Marginal Relevance) Search
```bash
curl http://localhost:7000/v1/retrieval \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"What is the revenue of Nike in 2023?\",
    \"embedding\": $your_embedding,
    \"search_type\": \"mmr\",
    \"k\": 4,
    \"fetch_k\": 20,
    \"lambda_mult\": 0.5,
    \"collection_name\": \"rag_milvus\"
  }"
```

