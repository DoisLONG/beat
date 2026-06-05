# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import base64
import os
import json
from io import BytesIO
from typing import Union

import requests
from fastapi import Request
from fastapi.responses import StreamingResponse
from PIL import Image

from ..proto.api_protocol import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatMessage,
    UsageInfo,
)
from ..proto.docarray import LLMParams, RerankerParms, RetrieverParms
from .constants import MegaServiceEndpoint, ServiceRoleType, ServiceType
from .micro_service import MicroService


class Gateway:
    def __init__(
        self,
        megaservice,
        host="0.0.0.0",
        port=8888,
        endpoint=str(MegaServiceEndpoint.CHAT_QNA),
        input_datatype=ChatCompletionRequest,
        output_datatype=ChatCompletionResponse,
    ):
        self.megaservice = megaservice
        self.host = host
        self.port = port
        self.endpoint = endpoint
        self.input_datatype = input_datatype
        self.output_datatype = output_datatype
        self.service = MicroService(
            service_role=ServiceRoleType.MEGASERVICE,
            service_type=ServiceType.GATEWAY,
            host=self.host,
            port=self.port,
            endpoint=self.endpoint,
            input_datatype=self.input_datatype,
            output_datatype=self.output_datatype,
        )
        self.define_routes()
        self.service.start()

    def define_routes(self):
        self.service.app.router.add_api_route(self.endpoint, self.handle_request, methods=["POST"])
        self.service.app.router.add_api_route(str(MegaServiceEndpoint.LIST_SERVICE), self.list_service, methods=["GET"])
        self.service.app.router.add_api_route(
            str(MegaServiceEndpoint.LIST_PARAMETERS), self.list_parameter, methods=["GET"]
        )

    def add_route(self, endpoint, handler, methods=["POST"]):
        self.service.app.router.add_api_route(endpoint, handler, methods=methods)

    def stop(self):
        self.service.stop()

    async def handle_request(self, request: Request):
        raise NotImplementedError("Subclasses must implement this method")

    def list_service(self):
        response = {}
        for node in self.all_leaves():
            response = {self.services[node].description: self.services[node].endpoint_path}
        return response

    def list_parameter(self):
        pass

    def _handle_message(self, messages):
        images = []
        if isinstance(messages, str):
            prompt = messages
        else:
            messages_dict = {}
            system_prompt = ""
            prompt = ""
            for message in messages:
                msg_role = message["role"]
                if msg_role == "system":
                    system_prompt = message["content"]
                elif msg_role == "user":
                    if type(message["content"]) == list:
                        text = ""
                        text_list = [item["text"] for item in message["content"] if item["type"] == "text"]
                        text += "\n".join(text_list)
                        image_list = [
                            item["image_url"]["url"] for item in message["content"] if item["type"] == "image_url"
                        ]
                        if image_list:
                            messages_dict[msg_role] = (text, image_list)
                        else:
                            messages_dict[msg_role] = text
                    else:
                        messages_dict[msg_role] = message["content"]
                elif msg_role == "assistant":
                    messages_dict[msg_role] = message["content"]
                else:
                    raise ValueError(f"Unknown role: {msg_role}")

            if system_prompt:
                prompt = system_prompt + "\n"
            for role, message in messages_dict.items():
                if isinstance(message, tuple):
                    text, image_list = message
                    if text:
                        prompt += role + ": " + text + "\n"
                    else:
                        prompt += role + ":"
                    for img in image_list:
                        # URL
                        if img.startswith("http://") or img.startswith("https://"):
                            response = requests.get(img)
                            image = Image.open(BytesIO(response.content)).convert("RGBA")
                            image_bytes = BytesIO()
                            image.save(image_bytes, format="PNG")
                            img_b64_str = base64.b64encode(image_bytes.getvalue()).decode()
                        # Local Path
                        elif os.path.exists(img):
                            image = Image.open(img).convert("RGBA")
                            image_bytes = BytesIO()
                            image.save(image_bytes, format="PNG")
                            img_b64_str = base64.b64encode(image_bytes.getvalue()).decode()
                        # Bytes
                        else:
                            img_b64_str = img

                        images.append(img_b64_str)
                else:
                    if message:
                        prompt += role + ": " + message + "\n"
                    else:
                        prompt += role + ":"
        if images:
            return prompt, images
        else:
            return prompt


class ChatQnAGateway(Gateway):
    def __init__(self, megaservice, host="0.0.0.0", port=8888):
        super().__init__(
            megaservice, host, port, str(MegaServiceEndpoint.CHAT_QNA), ChatCompletionRequest, ChatCompletionResponse
        )

    async def handle_request(self, request: Request):
        data = await request.json()
        stream_opt = data.get("stream", False)
        chat_request = ChatCompletionRequest.parse_obj(data)
        prompt = json.dumps(chat_request.messages, ensure_ascii=False, indent=2)
        parameters = LLMParams(
            max_tokens=chat_request.max_tokens if chat_request.max_tokens else 0,
            top_k=chat_request.top_k if chat_request.top_k else 10,
            top_p=chat_request.top_p if chat_request.top_p else 0.95,
            temperature=chat_request.temperature if chat_request.temperature else 0.01,
            frequency_penalty=chat_request.frequency_penalty if chat_request.frequency_penalty else 0.0,
            presence_penalty=chat_request.presence_penalty if chat_request.presence_penalty else 0.0,
            repetition_penalty=chat_request.repetition_penalty if chat_request.repetition_penalty else 1.03,
            stream=stream_opt,
            stream_options=chat_request.stream_options,
            chat_template=chat_request.chat_template if chat_request.chat_template else None,
        )
        retriever_parameters = RetrieverParms(
            search_type=chat_request.search_type if chat_request.search_type else "similarity_score_threshold",
            k=chat_request.k if chat_request.k else 4,
            distance_threshold=chat_request.distance_threshold if chat_request.distance_threshold else None,
            fetch_k=chat_request.fetch_k if chat_request.fetch_k else 20,
            lambda_mult=chat_request.lambda_mult if chat_request.lambda_mult else 0.5,
            score_threshold=chat_request.score_threshold if chat_request.score_threshold else 0.2,
            collection_name=chat_request.collection_name,
        )
        reranker_parameters = RerankerParms(
            top_n=chat_request.top_n if chat_request.top_n else 1,
        )
        result_dict, runtime_graph = await self.megaservice.schedule(
            initial_inputs={"text": prompt},
            llm_parameters=parameters,
            retriever_parameters=retriever_parameters,
            reranker_parameters=reranker_parameters,
        )
        for node, response in result_dict.items():
            if isinstance(response, StreamingResponse):
                return response
        last_node = runtime_graph.all_leaves()[-1]
        response = result_dict[last_node]["choices"][0]["message"]["content"]
        choices = []
        usage = UsageInfo()
        choices.append(
            ChatCompletionResponseChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response),
                finish_reason="stop",
            )
        )
        return ChatCompletionResponse(model="chatqna", choices=choices, usage=usage)