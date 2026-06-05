# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import os
import time
from decimal import Decimal
from typing import Optional
from urllib.parse import urljoin
import requests
from tokenizers import BertWordPieceTokenizer

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import (
    AIModelEntity,
    EmbeddingInputType,
    FetchFrom,
    ModelPropertyKey,
    ModelType,
    PriceConfig,
    PriceType,
)
from dify_plugin.entities.model.text_embedding import (
    EmbeddingUsage,
    TextEmbeddingResult,
)
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
)
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel

from dify_plugin.errors.model import InvokeAuthorizationError, InvokeBadRequestError, InvokeConnectionError, InvokeError, InvokeRateLimitError, InvokeServerUnavailableError

class OpenAITextEmbeddingModel(TextEmbeddingModel):

    def __init__(self, model_schemas=None):
        super().__init__(model_schemas or [])
        self._tokenizer = BertWordPieceTokenizer("vocab.txt")

    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: Optional[str] = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        """
        Invoke text embedding model

        :param model: model name
        :param credentials: model credentials
        :param texts: texts to embed
        :param user: unique user id
        :param input_type: input type
        :return: embeddings result
        """

        # Prepare headers and payload for the request
        headers = {"Content-Type": "application/json"}
        api_key = credentials.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        endpoint_url = credentials.get("endpoint_url", "")
        if not endpoint_url.endswith("/"):
            endpoint_url += "/"
        endpoint_url = urljoin(endpoint_url, "embeddings")

        extra_model_kwargs = {}
        if user:
            extra_model_kwargs["user"] = user
        extra_model_kwargs["encoding_format"] = "float"

        # get model properties
        context_size = self._get_context_size(model, credentials)
        max_chunks = self._get_max_chunks(model, credentials)

        inputs = []
        indices = []
        used_tokens = 0

        num_tokens_list = self.get_num_tokens(model, credentials, texts)

        for i, text in enumerate(texts):
            # Here token count is only an approximation based on the tokenizer
            num_tokens = num_tokens_list[i]
            if num_tokens >= context_size:
                # bge-large-zh-1.5 model ​1 Chinese character ≈ 1.2-1.5 tokens
                # we repeatedly tested ths Chinese Excel tables(7.6M)
                # found that the number of tokens and the length of the text were almost the same, basically 1:1
                # 1.0 is selected as the truncation ratio
                cutoff = int(1.0 * context_size)
                # if num tokens is larger than context length, only use the start
                inputs.append(text[0:cutoff])
            else:
                inputs.append(text)
            indices += [i]

        batched_embeddings = []
        _iter = range(0, len(inputs), max_chunks)

        for i in _iter:
            # Prepare the payload for the request
            payload = {
                "input": inputs[i : i + max_chunks],
                "model": model,
                **extra_model_kwargs,
            }

            # Make the request to the OpenAI API
            response = requests.post(
                endpoint_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=(10, 300),
            )
            response.raise_for_status()  # Raise an exception for HTTP errors
            response_data = response.json()

            # Extract embeddings and used tokens from the response
            embeddings_batch = [data["embedding"] for data in response_data["data"]]
            embedding_used_tokens = response_data["usage"]["total_tokens"]

            used_tokens += embedding_used_tokens
            batched_embeddings += embeddings_batch

        # calc usage
        usage = self._calc_response_usage(model=model, credentials=credentials, tokens=used_tokens)

        return TextEmbeddingResult(embeddings=batched_embeddings, usage=usage, model=model)

    def get_num_tokens(self, model: str, credentials: dict, texts: list[str]) -> list[int]:
        """
        Approximate number of tokens for given messages using tokenizer

        :param model: model name
        :param credentials: model credentials
        :param texts: texts to embed
        :return:
        """

        encodings = self._tokenizer.encode_batch(texts)
        return [len(encoding.ids) for encoding in encodings]

    def validate_credentials(self, model: str, credentials: dict) -> None:
        """
        Validate model credentials

        :param model: model name
        :param credentials: model credentials
        :return:
        """
        try:
            headers = {"Content-Type": "application/json"}

            api_key = credentials.get("api_key")

            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            endpoint_url = credentials.get("endpoint_url", "")
            if not endpoint_url.endswith("/"):
                endpoint_url += "/"

            endpoint_url = urljoin(endpoint_url, "embeddings")

            payload = {"input": "ping", "model": model}

            response = requests.post(
                url=endpoint_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=(10, 300),
            )

            if response.status_code != 200:
                raise CredentialsValidateFailedError(
                    f"Credentials validation failed with status code {response.status_code}"
                )

            try:
                json_result = response.json()
            except json.JSONDecodeError as e:
                raise CredentialsValidateFailedError("Credentials validation failed: JSON decode error") from e

            if "data" not in json_result:
                raise CredentialsValidateFailedError("Credentials validation failed: invalid response")
        except CredentialsValidateFailedError:
            raise
        except Exception as ex:
            raise CredentialsValidateFailedError(str(ex)) from ex

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        """
        Map model invoke error to unified error
        The key is the error type thrown to the caller
        The value is the error type thrown by the model,
        which needs to be converted into a unified error type for the caller.

        :return: Invoke error mapping
        """
        return {
            InvokeConnectionError: [InvokeConnectionError],
            InvokeServerUnavailableError: [InvokeServerUnavailableError],
            InvokeRateLimitError: [InvokeRateLimitError],
            InvokeAuthorizationError: [InvokeAuthorizationError],
            InvokeBadRequestError: [KeyError],
        }
    
    def get_customizable_model_schema(self, model: str, credentials: dict) -> AIModelEntity:
        """
        generate custom model entities from credentials
        """
        entity = AIModelEntity(
            model=model,
            label=I18nObject(en_US=model),
            model_type=ModelType.TEXT_EMBEDDING,
            fetch_from=FetchFrom.CUSTOMIZABLE_MODEL,
            model_properties={
                ModelPropertyKey.CONTEXT_SIZE: int(credentials.get("context_size", 512)),
                ModelPropertyKey.MAX_CHUNKS: 1,
            },
            parameter_rules=[],
            pricing=PriceConfig(
                input=Decimal(credentials.get("input_price", 0)),
                unit=Decimal(credentials.get("unit", 0)),
                currency=credentials.get("currency", "USD"),
            ),
        )

        return entity

    def _calc_response_usage(self, model: str, credentials: dict, tokens: int) -> EmbeddingUsage:
        """
        Calculate response usage

        :param model: model name
        :param credentials: model credentials
        :param tokens: input tokens
        :return: usage
        """
        # get input price info
        input_price_info = self.get_price(
            model=model,
            credentials=credentials,
            price_type=PriceType.INPUT,
            tokens=tokens,
        )

        # transform usage
        usage = EmbeddingUsage(
            tokens=tokens,
            total_tokens=tokens,
            unit_price=input_price_info.unit_price,
            price_unit=input_price_info.unit,
            total_price=input_price_info.total_amount,
            currency=input_price_info.currency,
            latency=time.perf_counter() - self.started_at,
        )

        return usage
