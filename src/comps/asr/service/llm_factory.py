# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from comps.asr.config import LLMProvider, get_dataprep_llm_connection, get_dataprep_llm_provider


class LLMFactory:
    @staticmethod
    def create_model(timeout: int = 600):  # noqa: ANN001
        provider = get_dataprep_llm_provider()
        llm_base_url, llm_model, llm_api_key = get_dataprep_llm_connection()

        if provider == LLMProvider.DASHSCOPE:
            from agno.models.dashscope import DashScope

            return DashScope(
                id=llm_model,
                api_key=llm_api_key,
                base_url=llm_base_url,
                temperature=0,
                enable_thinking=False,
                timeout=timeout,
            )

        if provider == LLMProvider.VLLM:
            from agno.models.vllm import VLLM

            return VLLM(
                id=llm_model,
                api_key=llm_api_key or "EMPTY",
                base_url=llm_base_url,
                temperature=0,
                timeout=timeout,
            )

        if provider == LLMProvider.OPENAI:
            from agno.models.openai import OpenAIChat

            return OpenAIChat(
                id=llm_model,
                api_key=llm_api_key,
                base_url=llm_base_url,
                temperature=0,
                timeout=timeout,
            )

        raise ValueError(f"Unsupported provider: {provider}")
