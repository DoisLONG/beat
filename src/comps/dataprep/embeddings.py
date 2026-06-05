# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from typing import List, Optional
from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import (
    HuggingFaceHubEmbeddings,
    OpenAIEmbeddings,
)
from openai import OpenAI
from comps import CustomLogger
from comps.dataprep.config import (
    LOCAL_EMBEDDING_MODEL,
    MOSEC_EMBEDDING_ENDPOINT,
    MOSEC_EMBEDDING_MODEL,
    TEI_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_ENDPOINT,
    OVMS_EMBEDDING_MODEL,
    embedding_ctx_length,
    BAILIAN_EMBEDDING_MODEL,
    BAILIAN_EMBEDDING_ENDPOINT,
    BAILIAN_EMBEDDING_API_KEY,
    get_embedding_config
)

logger = CustomLogger("dataprep-embeddings", os.getenv("LOG_LEVEL", "INFO"))


def _build_embedding_fingerprint(config) -> tuple[object, ...]:
    has_api_key = bool(config.api_key and config.api_key.get_secret_value())
    return (
        config.source,
        config.version,
        config.provider,
        config.model,
        config.base_url,
        config.transport,
        has_api_key,
    )

class MosecEmbeddings(OpenAIEmbeddings):
    def _get_len_safe_embeddings(
            self, texts: List[str], *, engine: str, chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        _chunk_size = chunk_size or self.chunk_size
        batched_embeddings: List[List[float]] = []
        response = self.client.create(input=texts, **self._invocation_params)
        if not isinstance(response, dict):
            response = response.model_dump()
        batched_embeddings.extend(r["embedding"] for r in response["data"])

        _cached_empty_embedding: Optional[List[float]] = None

        def empty_embedding() -> List[float]:
            nonlocal _cached_empty_embedding
            if _cached_empty_embedding is None:
                average_embedded = self.client.create(input="", **self._invocation_params)
                if not isinstance(average_embedded, dict):
                    average_embedded = average_embedded.model_dump()
                _cached_empty_embedding = average_embedded["data"][0]["embedding"]
            if _cached_empty_embedding is None:
                raise ValueError("Failed to compute empty embedding cache.")
            return list(_cached_empty_embedding)

        return [e if e is not None else empty_embedding() for e in batched_embeddings]

class BailianEmbeddings(Embeddings):
    def __init__(self, api_key: str, model: str, base_url: str, dimensions: int = 256):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.dimensions = dimensions

    def embed_query(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions
        )
        return resp.data[0].embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        resp = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions
        )
        return [d.embedding for d in resp.data]

def get_embeddings(refresh: bool = False, resolved_config=None):
    config = resolved_config if resolved_config is not None else get_embedding_config(refresh=refresh)
    has_active_db_config = (
        config.source == "db"
        and bool(config.model)
        and bool(config.base_url)
        and config.api_key is not None
    )

    logger.info(
        f"embedding config candidate source={config.source} "
        f"refresh={refresh} model={config.model} base_url={config.base_url} has_api_key={config.api_key is not None}"
    )
    
    if has_active_db_config:
        api_key_secret = config.api_key
        base_url = config.base_url
        if api_key_secret is None or base_url is None:
            raise ValueError("Active embedding config is missing api_key or base_url.")
        api_key = api_key_secret.get_secret_value()
        model = config.model

        logger.info(
            f"using DB embedding config provider={config.provider} "
            f"model={model} base_url={base_url} version={config.version}"
        )
        embeddings = BailianEmbeddings(
            api_key=api_key,
            model=model,
            base_url=base_url,
            dimensions=1024,
        )
    # Priority 1: OVMS (ENV fallback only when no active DB config)
    elif OVMS_EMBEDDING_ENDPOINT:
        from langchain_openai import OpenAIEmbeddings

        logger.info(
            f"using ENV fallback branch=ovms model={OVMS_EMBEDDING_MODEL} "
            f"base_url={OVMS_EMBEDDING_ENDPOINT}"
        )

        # Create an instance of OpenAIEmbedding
        embeddings = OpenAIEmbeddings(
            model=OVMS_EMBEDDING_MODEL,
            api_key="unused",
            base_url=OVMS_EMBEDDING_ENDPOINT,
            tiktoken_enabled=False,
            embedding_ctx_length=embedding_ctx_length,
        )
        logger.debug(f"OVMS_EMBEDDING_MODEL:{embeddings}")
    # Priority 2: TEI (from ENV)
    elif TEI_EMBEDDING_ENDPOINT:
        logger.info(f"using ENV fallback branch=tei base_url={TEI_EMBEDDING_ENDPOINT}")
        embeddings = HuggingFaceHubEmbeddings(
            model=f"{TEI_EMBEDDING_ENDPOINT}/embed",
            huggingfacehub_api_token="dummy"
        )
    # Priority 3: MOSEC (from ENV)
    elif MOSEC_EMBEDDING_ENDPOINT:
        logger.info(
            f"using ENV fallback branch=mosec model={MOSEC_EMBEDDING_MODEL} "
            f"base_url={MOSEC_EMBEDDING_ENDPOINT}"
        )
        embeddings = MosecEmbeddings(model=MOSEC_EMBEDDING_MODEL)
    # Priority 4: ENV fallback (Bailian or other)
    else:
        api_key = BAILIAN_EMBEDDING_API_KEY
        model = BAILIAN_EMBEDDING_MODEL
        base_url = BAILIAN_EMBEDDING_ENDPOINT
        
        logger.info(
            f"using ENV fallback branch=bailian model={model} "
            f"base_url={base_url} has_api_key={bool(api_key)}"
        )
        embeddings = BailianEmbeddings(
            api_key=api_key,
            model=model,
            base_url=base_url,
            dimensions=1024,
        )
    return embeddings

# Global instance for backward compatibility, but lazy-loaded and refreshable
_embeddings = None
_embedding_fingerprint: tuple[object, ...] | None = None

class _LazyEmbeddings(Embeddings):
    def ensure_latest(self) -> Embeddings:
        global _embeddings, _embedding_fingerprint

        latest_config = get_embedding_config(refresh=True)
        latest_fingerprint = _build_embedding_fingerprint(latest_config)

        if _embeddings is None or _embedding_fingerprint != latest_fingerprint:
            logger.info(
                f"rebuilding embedding backend old_fingerprint={_embedding_fingerprint} "
                f"new_fingerprint={latest_fingerprint}"
            )
            _embeddings = get_embeddings(refresh=True, resolved_config=latest_config)
            _embedding_fingerprint = latest_fingerprint
        return _embeddings

    def _get_embeddings(self) -> Embeddings:
        global _embeddings, _embedding_fingerprint
        if _embeddings is None:
            initial_config = get_embedding_config(refresh=False)
            _embeddings = get_embeddings(resolved_config=initial_config)
            _embedding_fingerprint = _build_embedding_fingerprint(initial_config)
        return _embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._get_embeddings().embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._get_embeddings().embed_query(text)

    def refresh(self):
        global _embeddings, _embedding_fingerprint
        refreshed_config = get_embedding_config(refresh=True)
        _embeddings = get_embeddings(refresh=True, resolved_config=refreshed_config)
        _embedding_fingerprint = _build_embedding_fingerprint(refreshed_config)

embeddings = _LazyEmbeddings()
