# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
import re

from fastapi import FastAPI, Request
# from fastapi.responses import StreamingResponse
# from langchain_core.prompts import PromptTemplate
import uvicorn
from contextlib import asynccontextmanager
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)

SERVICE_PORT = int(os.getenv("KB_SERVICE_PORT", 9932))

EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://0.0.0.0:3000/v3")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
RETRIEVER_BASE_URL = os.getenv("RETRIEVER_BASE_URL", "http://0.0.0.0:7000/v1")
RERANK_BASE_URL = os.getenv("RERANK_BASE_URL", "http://0.0.0.0:3010/V1")

LLM_MODEL = os.getenv("LLM_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")


@app.post("/retrieval")
async def retrieval(request: Request):
    data = await request.json()
    query = data.get("query")
    knowledge_id = data.get("knowledge_id")
    retrieval_setting = data.get("retrieval_setting")
    top_k = retrieval_setting.get("top_k", 5) if retrieval_setting else 5
    score_threshold = retrieval_setting.get("score_threshold", 0.5) if retrieval_setting else 0.5

    client = app.state.http_client

    embedding_url = f"{EMBEDDING_BASE_URL}/embeddings"
    embedding_payload = {
        "model": EMBEDDING_MODEL,
        "input": query
    }

    retriever_url = f"{RETRIEVER_BASE_URL}/retrieval"
    retriever_payload = {
        "text": query,
        "embedding": []
    }

    rerank_url = f"{RERANK_BASE_URL}/rerank"
    rerank_payload = {
        "query": query,
        "texts": []
    }

    headers = {
        "Content-Type": "application/json"
    }

    # get embeddings
    response = await client.post(embedding_url, json=embedding_payload, headers=headers)
    # print(f"embedding response: {response.json()}")

    # get retrieval results
    retriever_payload["search_type"]="similarity_score_threshold"
    retriever_payload["k"]=top_k
    # retriever_payload["k"]=10
    retriever_payload["distance_threshold"]=None
    retriever_payload["fetch_k"]=20
    retriever_payload["lambda_mult"]=0.5
    retriever_payload["score_threshold"]=score_threshold
    # retriever_payload["score_threshold"]=0.8
    retriever_payload["constraints"]=None
    retriever_payload["collection_name"]=knowledge_id

    embeddings = response.json()["data"][0]["embedding"]
    retriever_payload["embedding"] = embeddings
    # print(f"retriever_payload: {retriever_payload}")
    response = await client.post(retriever_url, json=retriever_payload, headers=headers)

    try:
        retriever_response = response.json()
    except json.decoder.JSONDecodeError:
        return {"records": []}
    formatted_docs = []
    for doc in retriever_response.get("retrieved_docs", []):
        formatted_doc = {
            "metadata": {
                "path": doc["metadata"].get("filename", ""),
                "description": " "
            },
            "score": doc.get("score", score_threshold),
            "title": doc["metadata"].get("filename", ""),
            "content": doc.get("text", "")
        }
        formatted_docs.append(formatted_doc)
    return {"records": formatted_docs}

if __name__ == "__main__":
    uvicorn.run(app=app, host='0.0.0.0', port=SERVICE_PORT)
