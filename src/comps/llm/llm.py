# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import copy
import os
import json
import time
from typing import Union, List, Optional, Dict, Any
from pathlib import Path
from fastapi.responses import StreamingResponse
from fastapi import Request
from langchain_core.prompts import PromptTemplate
from openai import OpenAI

from template import ChatTemplate

from comps import (
    CustomLogger,
    LLMParamsDoc,
    SearchedDoc,
    ServiceType,
    opea_microservices,
    register_microservice,
    register_statistics,
    statistics_dict,
    ToolResult,
    McpResultRequest,
)
from comps.cores.proto.api_protocol import ChatCompletionRequest

logger = CustomLogger("llm_vllm", os.getenv("LOG_LEVEL", "INFO"))

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


async def process_llm_request_with_tool_result(input: McpResultRequest, start_time: float, llm_client: OpenAI,
                                               tool_result_info:dict,model_name: str):
    # 调用模型的聊天接口，使用流式输出
    messages = [
        {"role": "system", "content": input.prompt},
        {"role": "user", "content": json.dumps(input.generate_info)}
    ]
    chat_params = {
        "model": model_name,
        "messages": messages,
        "stream": input.streaming
    }
    if hasattr(input, 'max_tokens') and input.max_tokens > 0:
        chat_params["max_tokens"] = input.max_tokens

    logger.debug(f"chat_params: {chat_params}")

    chat_completion = llm_client.chat.completions.create(**chat_params)

    if input.streaming:
        def stream_generator():
            chat_response = ""
            for c in chat_completion:
                stream_gen_time.append(time.time() - start_time)

                if c.choices and c.choices[0].delta.content is not None:
                    text = c.choices[0].delta.content
                else:
                    text = ""
                chat_response += text

                chunk_repr = repr(text.encode("utf-8"))
                logger.debug(f"chunk:{chunk_repr}")
                yield f"data: {chunk_repr}\n\n"

            statistics_dict["opea_service@llm_vllm"].append_latency(stream_gen_time[-1], stream_gen_time[0])
            yield "data: [DONE]\n\n"

            if input.generate_info:
                if input.generate_info["tool_result"]:
                    yield f"data: {{\"tool_info\": {json.dumps(tool_result_info['tool_result'])}}}\n\n"
                if input.documents:
                    yield f"data: {{\"documents\": {json.dumps(input.documents)}}}\n\n"
                yield "data: [METADATA DONE]\n\n"

        return StreamingResponse(stream_generator(), headers={"Content-Type": "text/event-stream; charset=utf-8"})
    else:
        logger.debug(chat_completion)
        return chat_completion

async def process_llm_request(input: LLMParamsDoc, start_time: float, llm_client: OpenAI, model_name: str):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": input.query},
    ]

    chat_params = {
        "model": model_name,
        "messages": messages,
        "stream": input.streaming,
        "stream_options": input.stream_options
    }
    if hasattr(input, 'max_tokens') and input.max_tokens > 0:
        chat_params["max_tokens"] = input.max_tokens

    logger.debug(f"chat_params: {chat_params}")

    chat_completion = llm_client.chat.completions.create(**chat_params)

    if input.streaming:
        def stream_generator():
            chat_response = ""
            token_usage = None
            for c in chat_completion:
                stream_gen_time.append(time.time() - start_time)

                if c.choices and c.choices[0].delta.content is not None:
                    text = c.choices[0].delta.content
                else:
                    text = ""
                chat_response += text

                chunk_repr = repr(text.encode("utf-8"))
                logger.debug(f"chunk:{chunk_repr}")
                yield f"data: {chunk_repr}\n\n"

                if c.usage:
                    logger.info(f"token usage: {c.usage}")
                    token_usage = c.usage

            statistics_dict["opea_service@llm_vllm"].append_latency(stream_gen_time[-1], stream_gen_time[0])
            yield "data: [DONE]\n\n"

            if input.documents or token_usage:
                if input.documents:
                    yield f"data: {{\"documents\": {json.dumps(input.documents)}}}\n\n"
                if token_usage:
                    yield f"data: {json.dumps({'token_usage': token_usage.model_dump()})}\n\n"
                yield "data: [METADATA DONE]\n\n"

        return StreamingResponse(stream_generator(), headers={"Content-Type": "text/event-stream; charset=utf-8"})
    else:
        logger.debug(chat_completion)
        return chat_completion

def format_prompt_with_template(question: str, documents: list = None, template: PromptTemplate = None) -> str:
    if template:
        if sorted(template.input_variables) == ["context", "question"]:
            context = "\n".join([doc["text"] for doc in documents]) if documents else ""
            return template.format(question=question, context=context)
        elif template.input_variables == ["question"]:
            return template.format(question=question)
        else:
            logger.info(
                f"Prompt template {template} not used, we only support 2 input variables ['question', 'context']")
            return question
    else:
        if documents:
            doc_texts = [doc["text"] for doc in documents]
            return ChatTemplate.generate_rag_prompt(question, doc_texts)
        return question

def filter_messages(original_messages: list) -> list:
    new_messages = []
    for msg in original_messages:
        new_messages.append({
            "role": msg.get("role", ""),
            "content": msg.get("content", "")
        })
    return new_messages

@register_microservice(
    name="opea_service@llm_vllm",
    service_type=ServiceType.LLM,
    endpoint="/v1/chat/completions",
    host="0.0.0.0", port=9000)
@register_statistics(names=["opea_service@llm_vllm"])
async def llm_generate(request: Request,
                       input: Union[McpResultRequest, LLMParamsDoc, ChatCompletionRequest, SearchedDoc]):
    llm_endpoint = os.getenv("vLLM_ENDPOINT", "http://localhost:8008")
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    openai_api_key = os.getenv("OPENAI_API_KEY", "EMPTY")

    if model_name == "":
        logger.error("LLM_MODEL is not set")

        # Return a 404 response indicating the model was not found
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Model not found. LLM_MODEL environment variable is not set."
        )

    logger.debug(f"llm_endpoint:{llm_endpoint}")
    logger.debug(f"model_name:{model_name}")
    logger.debug(f"input:{input}")

    prompt_template = None
    if input.chat_template:
        prompt_template = PromptTemplate.from_template(input.chat_template)
        input_variables = prompt_template.input_variables

    start = time.time()

    llm_client = OpenAI(
        api_key=openai_api_key,
        base_url=llm_endpoint + "/v1",
    )

    # rag/retriever -> llm
    if isinstance(input, SearchedDoc):
        logger.info("[ SearchedDoc ] input from retriever microservice")

        documents = []
        if input.retrieved_docs:
            logger.debug(f"[ SearchedDoc ] retrieved docs: {input.retrieved_docs}")
            for doc in input.retrieved_docs:
                logger.debug(f"[ SearchedDoc ] {doc}")

            documents = [{"text": doc.text, "metadata": doc.metadata} for doc in input.retrieved_docs]

        if should_filter_query(input.initial_query, documents):
            if getattr(input, 'streaming', False):
                return StreamingResponse(
                    create_no_context_response_stream(),
                    headers={"Content-Type": "text/event-stream; charset=utf-8"}
                )
            return create_no_context_response()

        prompt = format_prompt_with_template(input.initial_query, documents, prompt_template)

        chat_params = {
            "query": prompt,
            "documents": documents,
            "top_k": getattr(input, 'top_k', 10),
            "top_p": getattr(input, 'top_p', 0.95),
            "temperature": getattr(input, 'temperature', 0.01),
            "frequency_penalty": getattr(input, 'frequency_penalty', 0.0),
            "presence_penalty": getattr(input, 'presence_penalty', 0.0),
            "repetition_penalty": getattr(input, 'repetition_penalty', 1.03),
            "streaming": getattr(input, 'streaming', False),
            "stream_options": getattr(input, 'stream_options', None),
            "chat_template": getattr(input, 'chat_template', None)
        }
        if hasattr(input, 'max_tokens') and input.max_tokens > 0:
            chat_params['max_tokens'] = input.max_tokens
        new_input = LLMParamsDoc(**chat_params)

        logger.debug(f"[ SearchedDoc ] final input: {new_input}")
        return await process_llm_request(request, new_input, start, llm_client, model_name)

    # rerank -> llm
    elif isinstance(input, LLMParamsDoc):
        logger.info("[ LLMParamsDoc ] input from rerank microservice")

        if should_filter_query(input.query, input.documents):
            if input.streaming:
                return StreamingResponse(
                    create_no_context_response_stream(),
                    headers={"Content-Type": "text/event-stream; charset=utf-8"}
                )
            return create_no_context_response()

        prompt = format_prompt_with_template(input.query, input.documents, prompt_template)
        input.query = prompt
        return await process_llm_request(input, start, llm_client, model_name)

    elif isinstance(input, McpResultRequest):
        logger.info("[ ToolResult ] input from mcp microservice")
        tool_result_info = copy.deepcopy(input.generate_info)
        if input.documents:
            input.type = "tool"
            input.generate_info["tool_chain"].append("rag")
            input.generate_info["tool_result"].append({
                "name": "rag",
                "result": input.documents
            })
        if input.type == "tool" or input.type == "chain":
            return await process_llm_request_with_tool_result(input, start, llm_client,tool_result_info, model_name)
        else:
            query = input.query
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query}
            ]

            chat_params = {
                "model": model_name,
                "messages": messages,
                "stream": input.streaming
            }

            if hasattr(input, 'max_tokens') and input.max_tokens > 0:
                chat_params["max_tokens"] = input.max_tokens
            logger.debug(f"chat_params: {chat_params}")
            chat_completion = llm_client.chat.completions.create(**chat_params)

            if input.streaming:
                async def stream_generator():
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

                    statistics_dict["opea_service@llm_vllm"].append_latency(stream_gen_time[-1], stream_gen_time[0])
                    yield "data: [DONE]\n\n"

                return StreamingResponse(stream_generator(),
                                         headers={"Content-Type": "text/event-stream; charset=utf-8"})
            else:
                logger.debug(chat_completion)
                return chat_completion

    # llm only
    else:
        logger.info("[ ChatCompletionRequest ] input in opea format, llm only")
        query = input.messages if isinstance(input.messages, str) else input.messages[-1].get("content", "")
        documents = getattr(input, "documents", [])
        # Add query filtering for ChatCompletionRequest
        if should_filter_query(query, documents):
            if input.stream:
                return StreamingResponse(
                    create_no_context_response_stream(),
                    headers={"Content-Type": "text/event-stream; charset=utf-8"}
                )
            return create_no_context_response()

        if isinstance(input.messages, str):
            # ui llm only without chathistory
            input.messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": input.messages}, ]
        else:
            # ui llm only with chathistory
            if not any(message.get("role") == "system" for message in input.messages):
                input.messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})
            input.messages = filter_messages(input.messages)

        chat_params = {
            "model": model_name,
            "messages": input.messages,
            "frequency_penalty": input.frequency_penalty,
            "n": input.n,
            "presence_penalty": input.presence_penalty,
            "response_format": input.response_format,
            "seed": input.seed,
            "stop": input.stop,
            "stream": input.stream,
            "stream_options": input.stream_options,
            "temperature": input.temperature,
            "user": input.user,
        }

        if hasattr(input, 'max_tokens') and input.max_tokens > 0:
            chat_params["max_tokens"] = input.max_tokens
        logger.debug(f"chat_params: {chat_params}")

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
                statistics_dict["opea_service@llm_vllm"].append_latency(stream_gen_time[-1], stream_gen_time[0])
                yield "data: [DONE]\n\n"

                if input.documents or token_usage:
                    if input.documents:
                        yield f"data: {{\"documents\": {json.dumps(input.documents)}}}\n\n"
                    if token_usage:
                        yield f"data: {json.dumps({'token_usage': token_usage.model_dump()})}\n\n"
                    yield "data: [METADATA DONE]\n\n"

            return StreamingResponse(stream_generator(), headers={"Content-Type": "text/event-stream; charset=utf-8"})
        else:
            logger.debug(chat_completion)
            return chat_completion


if __name__ == "__main__":
    opea_microservices["opea_service@llm_vllm"].start()
