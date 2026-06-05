# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import json
import time
from typing import Union
from pathlib import Path

from fastapi.responses import StreamingResponse
from fastapi import Request
from openai import OpenAI
from .template import ChatTemplate

import dotenv
dotenv.load_dotenv()

from opea_cores import (
    CustomLogger,
    LLMParamsDoc,
    SearchedDoc,
    ServiceType,
    opea_microservices,
    register_microservice,
    register_statistics,
    statistics_dict,
    ChatCompletionRequest
)

logger = CustomLogger("llm_vllm", os.getenv("LOG_LEVEL", "INFO"))
llm_endpoint = os.getenv("vLLM_ENDPOINT", "http://localhost:8008")
model_name = os.getenv("LLM_MODEL", "")
openai_api_key = os.getenv("OPENAI_API_KEY", "EMPTY")

stream_gen_time = []

def parse_bool_strict(value: str) -> bool:
    """Parse string to boolean, only accepting 0/1."""
    value = str(value).strip()
    if value not in ('0', '1'):
        raise ValueError("Environment variable must be '0' or '1'")
    return value == '1'

# FILTER_QUERIES: Environment variable to control query filtering behavior
# When set to "true":
#   - Filters out queries that don't have matching documents from the knowledge base
#   - Returns a "no context" response for queries without relevant documentation
#   - Exception: Queries containing specific keywords (defined in config.json) are still processed
# When set to "false" (default):
#   - All queries are processed normally, regardless of document availability
FILTER_QUERIES = parse_bool_strict(os.getenv("FILTER_QUERIES", "0"))
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_NO_CONTEXT_MESSAGE = "I apologize, but your question appears to be outside the scope of my knowledge base. I can only answer questions related to specific topics covered in the provided documentation."

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return {
                'keywords': set(config.get('keywords', [])),
                'no_context_message': config.get('no_context_message', DEFAULT_NO_CONTEXT_MESSAGE)
            }
    except FileNotFoundError:
        logger.warning(f"Config file not found at {CONFIG_FILE}")
        return {'keywords': set(), 'no_context_message': DEFAULT_NO_CONTEXT_MESSAGE}
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in config file at {CONFIG_FILE}")
        return {'keywords': set(), 'no_context_message': DEFAULT_NO_CONTEXT_MESSAGE}

def contains_keywords(query: str, keywords: set) -> bool:
    query_lower = query.lower()
    return any(keyword.lower() in query_lower for keyword in keywords)

def should_filter_query(query: str, documents: list) -> bool:
    if not FILTER_QUERIES:
        return False

    if documents:
        return False

    config = load_config()
    has_keywords = contains_keywords(query, config['keywords'])

    if not has_keywords:
        logger.info("No documents found and query doesn't contain keywords - filtering query")

    return not has_keywords

def create_no_context_response():
    config = load_config()
    return {
        "id": "no_context_response",
        "object": "chat.completion",
        "created": int(time.time()),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": config['no_context_message']
            },
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }

def create_no_context_response_stream():
    config = load_config()
    message = config['no_context_message']
    chunk_repr = repr(message.encode("utf-8"))
    yield f"data: {chunk_repr}\n\n"
    yield "data: [DONE]\n\n"
    yield "data: [METADATA DONE]\n\n"

def filter_messages(original_messages: list) -> list:
    new_messages = []
    for msg in original_messages:
        new_messages.append({
            "role": msg.get("role", ""),
            "content": msg.get("content", "")
        })
    return new_messages

def is_json_string(s):
    """
    Check if a string is a valid JSON string.
    :param s: The string to check.
    :return: True if the string is valid JSON, False otherwise.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None

async def _llm_generate(request: Request, input: Union[LLMParamsDoc, ChatCompletionRequest, SearchedDoc]):

    if model_name == "":
        logger.error("LLM_MODEL is not set")
        # Return a 404 response indicating the model was not found
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Model not found. LLM_MODEL environment variable is not set."
        )

    logger.debug(f"llm_endpoint: {llm_endpoint}, model_name: {model_name}, openai_api_key: {openai_api_key}, input: {input}")

    start = time.time()
    messages = ""
    documents = []
    websearch = []

    llm_client = OpenAI(
        api_key=openai_api_key,
        base_url=llm_endpoint + "/v1",
    )

    # rag/retriever -> llm
    if isinstance(input, SearchedDoc):
        logger.info("[ SearchedDoc ] input from retriever microservice")
        query_data = is_json_string(input.initial_query)
        if query_data:
            messages = query_data
        else:
            messages = [{"role": "user", "content": input.initial_query}]
        documents = []
        if input.retrieved_docs:
            logger.debug(f"[ SearchedDoc ] retrieved docs: {input.retrieved_docs}")
            for doc in input.retrieved_docs:
                logger.debug(f"[ SearchedDoc ] {doc}")

            documents = [{"text": doc.text, "metadata": doc.metadata} for doc in input.retrieved_docs]

    # rerank -> llm
    elif isinstance(input, LLMParamsDoc):
        logger.info("[ LLMParamsDoc ] input from rerank microservice")
        query_data = is_json_string(input.query)
        if query_data:
            messages = query_data
        else:
            messages = [{"role": "user", "content": input.query}]
        documents = input.documents

    # llm only
    else:
        logger.info("[ ChatCompletionRequest ] input in opea format, llm only")
        if input.messages is str:
            query_data = is_json_string(input.messages)
            if query_data:
                messages = query_data
            else:
                messages = [{"role": "user", "content": input.messages}]
        else:
            messages = input.messages
        documents = getattr(input, "documents", []) or []
    
    logger.debug(f"init messages: {messages}")
    logger.debug(f"init documents: {documents}")
    logger.debug(f"init websearch: {websearch}")

    if should_filter_query(messages[-1].get("content", ""), documents):
        if getattr(input, 'stream', False):
            return StreamingResponse(
                create_no_context_response_stream(),
                headers={"Content-Type": "text/event-stream; charset=utf-8"}
            )
        return create_no_context_response()

    retrieved_docs = []
    websearch_docs = []
    if documents:
        retrieved_docs = [doc["text"] for doc in documents]
    if websearch:
        websearch_docs = [doc["text"] for doc in websearch]
    systme_prompt = ChatTemplate.generate_rag_system_prompt(messages[-1].get("content", ""), retrieved_docs, websearch_docs)
    if not any(message.get("role") == "system" for message in messages):
        messages.insert(0, {"role": "system", "content": systme_prompt})
    messages = filter_messages(messages)
    chat_params = {
        "model": model_name,
        "messages": messages,
        "stream": input.stream,
        "stream_options": input.stream_options
    }

    if hasattr(input, 'max_tokens') and input.max_tokens > 0:
        chat_params["max_tokens"] = input.max_tokens
    new_input = ChatCompletionRequest(**chat_params)

    logger.debug(f"final chat_params: {new_input}")

    chat_completion = llm_client.chat.completions.create(**chat_params)
    """TODO need validate following parameters for vllm. OpenAI's API rejects request due to the following unexpected parameters in the request body.
        service_tier=input.service_tier,
        tools=input.tools,
        tool_choice=input.tool_choice,
        parallel_tool_calls=input.parallel_tool_calls,
    """

    if input.stream:
        async def stream_generator():
            token_usage = None
            for c in chat_completion:

                if await request.is_disconnected():
                    logger.info("Request disconnected")
                    break

                stream_gen_time.append(time.time() - start)
                if c.choices and c.choices[0].delta.content is not None:
                    text = c.choices[0].delta.content
                else:
                    text = ""
                chunk_repr = repr(text.encode("utf-8"))
                logger.debug(f"chunk:{chunk_repr}")
                yield f"data: {chunk_repr}\n\n"
                if c.usage:
                    logger.info(f"token usage: {c.usage}")
                    token_usage = c.usage
            # Development mode will report an error
            # statistics_dict["opea_service@llm_vllm"].append_latency(stream_gen_time[-1], stream_gen_time[0])
            yield "data: [DONE]\n\n"

            if documents or token_usage:
                if documents:
                    yield f"data: {{\"documents\": {json.dumps(documents)}}}\n\n"
                if token_usage:
                    yield f"data: {json.dumps({'token_usage': token_usage.model_dump()})}\n\n"
                yield "data: [METADATA DONE]\n\n"

        return StreamingResponse(stream_generator(), headers={"Content-Type": "text/event-stream; charset=utf-8"})
    else:
        logger.debug(chat_completion)
        return chat_completion


if __name__ == "__main__":

    @register_microservice(
        name="opea_service@llm_vllm",
        service_type=ServiceType.LLM,
        endpoint="/v1/chat/completions",
        host="0.0.0.0", port=9000
    )
    @register_statistics(names=["opea_service@llm_vllm"])
    async def llm_generate(request: Request, input: Union[LLMParamsDoc, ChatCompletionRequest, SearchedDoc]):
        return await _llm_generate(request, input)
    
    opea_microservices["opea_service@llm_vllm"].start()

else:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/v1/health_check")
    async def _health_check():
        return {"Service Title": "LLM New"}

    @app.post("/v1/chat/completions")
    async def llm_generate(request: Request, input: Union[LLMParamsDoc, ChatCompletionRequest, SearchedDoc]):
        return await _llm_generate(request, input)