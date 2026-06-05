# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from comps.excel.config import DATAPREP_LLM_API_KEY


CHAT_ENDPOINT = "/chat/completions"
logger = logging.getLogger("excel-llm-api")


@dataclass(slots=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_s: int = 600
    retries: int = 3
    backoff_s: float = 1.5
    temperature: float = 0.2
    max_tokens: int | None = None


def chat_completions(
    messages: list[dict[str, str]],
    cfg: LLMConfig,
    extra: dict[str, Any] | None = None,
) -> str:
    session = requests.Session()
    session.trust_env = False
    headers = {"Content-Type": "application/json"}
    api_key = cfg.api_key or DATAPREP_LLM_API_KEY
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": cfg.temperature,
        "stream": False,
    }
    if cfg.max_tokens is not None:
        payload["max_tokens"] = cfg.max_tokens
    if extra:
        payload.update(extra)

    url = cfg.base_url.rstrip("/") + CHAT_ENDPOINT
    logger.info("LLM request prepared: model=%s url=%s retries=%s", cfg.model, url, cfg.retries)
    last_error: Exception | None = None
    for attempt in range(1, cfg.retries + 1):
        try:
            logger.info("LLM request attempt: model=%s attempt=%s/%s", cfg.model, attempt, cfg.retries)
            response = session.post(url, headers=headers, json=payload, timeout=cfg.timeout_s)
            response.raise_for_status()
            data = response.json()
            logger.info("LLM request succeeded: model=%s attempt=%s", cfg.model, attempt)
            return data["choices"][0]["message"].get("content", "") or ""
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("LLM request failed: model=%s attempt=%s err=%s", cfg.model, attempt, exc)
            if attempt < cfg.retries:
                time.sleep(cfg.backoff_s * attempt)

    raise RuntimeError(f"LLM call failed after {cfg.retries} tries: {last_error}")
