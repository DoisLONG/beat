# Retriever API Documentation

## Overview
This API provides endpoints for retrieving information from knowledge bases, including document retrieval.

## Endpoints

### Health Check
- **GET** `/v1/health_check`
  - **Description**: Check if the service is running
  - **Response**: `{"Service Title": "Retriever New"}`

### Retrieval
- **POST** `/v1/retrieval`
  - **Description**: Retrieve documents based on embedding and search parameters
  - **Request Body**: `EmbedDoc` object
    ```json
    {
      "text": "string",
      "embedding": [float],
      "search_type": "string" (default: "similarity_score_threshold"),
      "k": int (default: 4),
      "distance_threshold": float (optional),
      "fetch_k": int (default: 20),
      "lambda_mult": float (default: 0.5),
      "score_threshold": float (default: 0.5),
      "constraints": object (optional),
      "collection_name": string (optional)
    }
    ```
  - **Response**: `SearchedDoc` object
    ```json
    {
      "retrieved_docs": [
        {
          "text": "string",
          "metadata": object
        }
      ],
      "initial_query": "string",
      "top_n": int (default: 1)
    }
    ```

### Dify Retrieval
- **POST** `/v1/dify/retrieval`
  - **Description**: Retrieve documents using Dify API format
  - **Request Body**: `DifyRetrievalRequest` object
    ```json
    {
      "query": "string",
      "knowledge_id": "string",
      "retrieval_setting": {
        "top_k": int (default: 4),
        "score_threshold": float (default: 0.5)
      }
    }
    ```
  - **Response**: Object containing retrieved records
    ```json
    {
      "records": [
        {
          "metadata": {
            "path": "string",
            "description": "string"
          },
          "score": float,
          "title": "string",
          "content": "string"
        }
      ]
    }
    ```

### Knowledge Base Management

- **GET** `/v1/kbs`
  - **Description**: List all knowledge bases
  - **Response**: Dictionary mapping knowledge base names to UUIDs
    ```json
    {
      "kb-name": "uuid"
    }
    ```

- **GET** `/v1/kbs/{kb_id}`
  - **Description**: Get information about a specific knowledge base
  - **Parameters**: `kb_id` (string) - Knowledge base ID
  - **Response**: Knowledge base information object
    ```json
    {
      "name": "string",
      "uuid": "string",
      "files": ["string"],
      "questions": ["string"]
    }
    ```

- **GET** `/v1/kbs/files/{kb_id}`
  - **Description**: List files in a knowledge base
  - **Parameters**: `kb_id` (string) - Knowledge base ID
  - **Response**: List of file objects
    ```json
    [
      {
        "name": "string",
        "id": "string",
        "type": "File",
        "parent": ""
      }
    ]
    ```

- **GET** `/v1/kbs/questions/{kb_id}`
  - **Description**: Get questions associated with a knowledge base
  - **Parameters**: `kb_id` (string) - Knowledge base ID
  - **Response**: List of question strings
    ```json
    ["string"]
    ```

## Search Types
The API supports different search types for document retrieval:
- `similarity`: Basic similarity search
- `similarity_distance_threshold`: Similarity search with distance threshold
- `similarity_score_threshold`: Similarity search with score threshold
- `mmr`: Maximum Marginal Relevance search 