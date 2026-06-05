# Retriever Microservice with Milvus

The Retriever Microservice provides vector similarity search capabilities using Milvus as the backend. It enables efficient retrieval of semantically similar documents based on vector embeddings.

## Libs preparing (optional)

For development launching, make sure the libs "opea_cores" have been built at ../../libs, and the wheel package file is available at ../../libs/dist/, the building commmand can be:

  ```cd ../../libs; uv build```

If you want to build the container image directly, need not care about this step.

## Launching for Development

Before launching the app, please copy file env.example to .env, and check the values inside .env file.
Then just run ```uv run uvicorn src.main:app --reload --port 7001 --host 0.0.0.0```

In production environment, the cli is different in Dockerfile, but it's the same as:
```uv run -m src.main```

## Container image building

Go to ../../../scripts/build.all.images dir, run ```docker compose build retriever-new```

## Deployment

Go to ../../../deployment/docker-compose/ekba/ dir, run ```docker compose up retriever-new```
Also need to check the ENV settings in the .env file under this deployment dir.

## Service Verification

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

### Health Check

```bash
curl http://localhost:7001/v1/health_check \
  -X GET \
  -H 'Content-Type: application/json'
```

### Retrieval Examples

> **Note:** In the examples below, `rag_milvus` is just a sample collection name. You can replace it with any collection name of your choice.

#### Basic Retrieval
```bash
# Generate a mock embedding vector
export your_embedding=$(python -c "import random; embedding = [random.uniform(-1, 1) for _ in range(768)]; print(embedding)")

curl http://localhost:7001/v1/retrieval \
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
curl http://localhost:7001/v1/retrieval \
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
curl http://localhost:7001/v1/retrieval \
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
curl http://localhost:7001/v1/retrieval \
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
curl http://localhost:7001/v1/retrieval \
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

