# Dataprep Microservice with Milvus

This microservice handles document preparation and embedding generation for Milvus vector database.

## 🚀 Service Usage Guide

> **Note:** The examples below use `localhost` and specific ports which are applicable for Docker deployment. For Kubernetes deployment, you'll need to:
> 1. Get the service IP: `kubectl get svc -n <namespace>`
> 2. Replace `localhost` with the service IP in the commands below
> 3. Use the port exposed by the Kubernetes service

### 1. Upload Documents

Upload documents to generate embeddings and save to the database.

> Note: In the examples below, `rag_milvus` is just a sample collection name. You can replace it with any collection name of your choice.

- Single file upload:
```bash
curl -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "files=@./file.pdf" \
    -F "collection_name=rag_milvus" \
    http://localhost:6007/v1/dataprep
```

You can customize chunk size and overlap:
```bash
curl -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "files=@./file.pdf" \
    -F "chunk_size=500" \
    -F "chunk_overlap=100" \
    -F "collection_name=rag_milvus" \
    http://localhost:6007/v1/dataprep
```

- Multiple file upload:
```bash
curl -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "files=@./file1.pdf" \
    -F "files=@./file2.pdf" \
    -F "files=@./file3.pdf" \
    -F "collection_name=rag_milvus" \
    http://localhost:6007/v1/dataprep
```

### 2. List Uploaded Files

```bash
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"collection_name": "rag_milvus"}' \
    http://localhost:6007/v1/dataprep/get_file
```

Example response:
```json
[
  {
    "name": "uploaded_file_1.txt",
    "id": "uploaded_file_1.txt",
    "type": "File",
    "parent": ""
  },
  {
    "name": "uploaded_file_2.txt",
    "id": "uploaded_file_2.txt",
    "type": "File",
    "parent": ""
  }
]
```

### 3. Delete Files

```bash
# Delete specific file
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"file_path": "uploaded_file_1.txt", "collection_name": "rag_milvus"}' \
    http://localhost:6007/v1/dataprep/delete_file

# Delete all files (drops the entire collection)
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"file_path": "all", "collection_name": "rag_milvus"}' \
    http://localhost:6007/v1/dataprep/delete_file
```