# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import SecretStr

from comps.system_common.model import ModelConfigScope
from comps.system_common.resolver import ResolvedModelConfig, get_cached_config_resolver


BASE_DIR = Path(__file__).resolve().parent


class LLMProvider(str, Enum):
    DASHSCOPE = "dashscope"
    VLLM = "vllm"
    OPENAI = "openai"


DATA_DIR = Path(os.getenv("ASR_DATA_DIR", str(BASE_DIR / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
JOBS_DIR = DATA_DIR / "jobs"
ASR_DIR = DATA_DIR / "asr"
RESULT_DIR = DATA_DIR / "results"
TMP_DIR = DATA_DIR / "tmp"
GLOSSARY_FILE = DATA_DIR / "glossary.json"

DATAPREP_LLM_PROVIDER = os.getenv("DATAPREP_LLM_PROVIDER", "dashscope").strip().lower()
DATAPREP_LLM_API_KEY = os.getenv("DATAPREP_LLM_API_KEY", "").strip()
DATAPREP_LLM_ENDPOINT = os.getenv("DATAPREP_LLM_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
DATAPREP_LLM_MODEL = os.getenv("DATAPREP_LLM_MODEL", "qwen3-max").strip()
ASR_LLM_MODEL = os.getenv("ASR_LLM_MODEL", "").strip()

ASR_API_KEY = os.getenv("ASR_API_KEY", "").strip()
ASR_ENDPOINT = os.getenv("ASR_ENDPOINT", "").strip()
ASR_MODEL = os.getenv("ASR_MODEL", "Qwen/Qwen3-ASR-1.7B").strip()
ASR_ENGINE = os.getenv("ASR_ENGINE", "qwen").strip().lower()
ASR_MAX_WORKERS = int(os.getenv("ASR_MAX_WORKERS", "2"))
ASR_CHUNK_WORKERS = int(os.getenv("ASR_CHUNK_WORKERS", "4"))
ASR_FFMPEG_SEGMENT_SECONDS = int(os.getenv("ASR_FFMPEG_SEGMENT_SECONDS", "300"))
ASR_SSL_VERIFY = os.getenv("ASR_SSL_VERIFY", "false").strip().lower() in {"1", "true", "yes", "on"}
ASR_WHISPER_MODEL_SIZE = os.getenv("ASR_WHISPER_MODEL_SIZE", "medium").strip()
ASR_WHISPER_DEVICE = os.getenv("ASR_WHISPER_DEVICE", "auto").strip()
ASR_WHISPER_COMPUTE_TYPE = os.getenv("ASR_WHISPER_COMPUTE_TYPE", "default").strip()
ASR_WHISPER_MODEL_PATH = os.getenv(
    "ASR_WHISPER_MODEL_PATH",
    f"/opt/models/faster-whisper-{ASR_WHISPER_MODEL_SIZE}",
).strip()

ASR_REFINE_BATCH_SIZE = int(os.getenv("ASR_REFINE_BATCH_SIZE", "10"))
REFINE_BATCH_WORKERS = int(os.getenv("REFINE_BATCH_WORKERS", "3"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def resolve_dataprep_llm_config() -> ResolvedModelConfig:
    return get_cached_config_resolver().resolve(ModelConfigScope.DATAPREP_LLM)


def resolve_asr_config() -> ResolvedModelConfig:
    return get_cached_config_resolver().resolve(ModelConfigScope.ASR)


def get_dataprep_llm_provider() -> LLMProvider:
    resolved = resolve_dataprep_llm_config()
    provider_raw = (resolved.provider or DATAPREP_LLM_PROVIDER or "dashscope").strip().lower()
    try:
        return LLMProvider(provider_raw)
    except ValueError:
        return LLMProvider.DASHSCOPE


def get_dataprep_llm_connection() -> tuple[str, str, str | None]:
    resolved = resolve_dataprep_llm_config()
    api_key = resolved.api_key.get_secret_value() if isinstance(resolved.api_key, SecretStr) else DATAPREP_LLM_API_KEY
    model_name = ASR_LLM_MODEL or resolved.model or DATAPREP_LLM_MODEL
    return (
        resolved.base_url or DATAPREP_LLM_ENDPOINT,
        model_name,
        api_key or None,
    )


def get_asr_connection() -> tuple[str, str, str | None, str, dict[str, object]]:
    resolved = resolve_asr_config()
    api_key = resolved.api_key.get_secret_value() if isinstance(resolved.api_key, SecretStr) else ASR_API_KEY
    return (
        resolved.base_url or ASR_ENDPOINT,
        resolved.model or ASR_MODEL,
        api_key or None,
        resolved.transport,
        resolved.runtime_options,
    )

for path in (DATA_DIR, UPLOAD_DIR, JOBS_DIR, ASR_DIR, RESULT_DIR, TMP_DIR):
    path.mkdir(parents=True, exist_ok=True)
