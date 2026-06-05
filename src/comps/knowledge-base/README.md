## External Knowledge Base

For developers with advanced content retrieval requirements, the built-in knowledge base functionality and text retrieval mechanisms of the Dify platform may have limitations, particularly in terms of customizing recall results.

Due to the requirement of higher accuracy of text retrieval and recall, as well as the need to manage internal materials, some developer teams choose to independently develop RAG algorithms and independently maintain text retrieval systems

## External Knowledge Base API
Dify defined an External Knowledge Base API, that makes all developers can connect self deployed knowledge base to Dify. Please refer to Dify's External Knowledge Base API specifications to ensure successful integration between your external knowledge base and Dify.
[API defination document](https://docs.dify.ai/guides/knowledge-base/external-knowledge-api-documentation)

Basically the API input and output defined as below

### Request Syntax
```
POST <your-endpoint>/retrieval HTTP/1.1
-- header
Content-Type: application/json
Authorization: Bearer your-api-key
-- data
{
    "knowledge_id": "your-knowledge-id",
    "query": "your question",
    "retrieval_setting":{
        "top_k": 2,
        "score_threshold": 0.5
    }
}
```

### Response Syntax
```
HTTP/1.1 200
Content-type: application/json
{
    "records": [{
                    "metadata": {
                            "path": "s3://dify/knowledge.txt",
                            "description": "dify knowledge document"
                    },
                    "score": 0.98,
                    "title": "knowledge.txt",
                    "content": "This is the document for external knowledge."
            },
            {
                    "metadata": {
                            "path": "s3://dify/introduce.txt",
                            "description": "dify introduce"
                    },
                    "score": 0.66,
                    "title": "introduce.txt",
                    "content": "The Innovation Engine for GenAI Applications"
            }
    ]
}
```

### Build Docker image

```
docker build . -t knowledget-base:0.01
```

### launch knowledge base service

```
##edit launch_kb.sh for environment below:
export KB_SERVICE_PORT=9923
export EMBEDDING_BASE_URL="http://10.239.75.251:3008/v3"
export EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5"
export RETRIEVER_BASE_URL="http://10.239.75.251:7000/v1"

./launch_kb.sh
```

### Test the knowledge base service

```
curl http://localhost:9923/retrieval -X POST -H "Content-Type: application/json" -d '{
    "knowledge_id": "AIGC",
    "query": "what is AIGC",
    "retrieval_setting":{
        "top_k": 2,
        "score_threshold": 0.5
    }
}'
```
