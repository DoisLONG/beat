# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from comps.system_common.model import ModelConfigScope
from comps.system_common.resolver import ResolvedModelConfig, get_cached_config_resolver


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("EXCEL_DATA_DIR", str(BASE_DIR / "data")))
JOBS_DIR = DATA_DIR / "jobs"
OUT_DIR = DATA_DIR / "output"
TMP_DIR = DATA_DIR / "tmp"

EXCEL_ASR_BASE_URL = os.getenv("EXCEL_ASR_BASE_URL", "http://127.0.0.1:8000").strip()
DATAPREP_LLM_ENDPOINT = os.getenv("DATAPREP_LLM_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
DATAPREP_LLM_MODEL = os.getenv("DATAPREP_LLM_MODEL", "qwen-max").strip()
DATAPREP_LLM_API_KEY = os.getenv("DATAPREP_LLM_API_KEY", "sk-50f1809932d54d958040350ac90bec60").strip()

SOP_UPLOAD_URL = os.getenv("SOP_UPLOAD_URL", "http://10.3.70.118:6007/v1/dataprep/generate_qa").strip()
SOP_UPLOAD_FILE_FIELD = os.getenv("SOP_UPLOAD_FILE_FIELD", "files").strip()
SOP_UPLOAD_FILE_TYPE = os.getenv("SOP_UPLOAD_FILE_TYPE", "sop").strip()
SOP_UPLOAD_AUTH_HEADER = os.getenv("SOP_UPLOAD_AUTH_HEADER", "").strip()
SOP_UPLOAD_ENABLED = os.getenv("SOP_UPLOAD_ENABLED", "true").lower() == "true"

EXCEL_EXECUTOR_WORKERS = int(os.getenv("EXCEL_EXECUTOR_WORKERS", "2"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def resolve_dataprep_llm_config() -> ResolvedModelConfig:
    return get_cached_config_resolver().resolve(ModelConfigScope.DATAPREP_LLM)


def get_dataprep_llm_connection() -> tuple[str, str, str | None]:
    resolved = resolve_dataprep_llm_config()
    api_key = resolved.api_key.get_secret_value() if isinstance(resolved.api_key, SecretStr) else DATAPREP_LLM_API_KEY
    return (
        resolved.base_url or DATAPREP_LLM_ENDPOINT,
        resolved.model or DATAPREP_LLM_MODEL,
        api_key or None,
    )

for path in (DATA_DIR, JOBS_DIR, OUT_DIR, TMP_DIR):
    path.mkdir(parents=True, exist_ok=True)


def now_ts() -> float:
    return time.time()


def safe_filename(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:max_len] or "Universal_Table"


def job_path(task_id: str) -> Path:
    return JOBS_DIR / f"{task_id}.json"


def save_job(task_id: str, data: dict[str, Any]) -> None:
    job_path(task_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_job(task_id: str) -> dict[str, Any]:
    path = job_path(task_id)
    if not path.exists():
        raise FileNotFoundError(task_id)
    return json.loads(path.read_text(encoding="utf-8"))


def update_job(task_id: str, **fields: Any) -> None:
    job = load_job(task_id)
    job.update(fields)
    job["updated_at"] = now_ts()
    save_job(task_id, job)
