# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from comps.asr.config import JOBS_DIR, RESULT_DIR

logger = logging.getLogger("asr-job-store")


def now_ts() -> float:
    return time.time()


def job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def result_path(job_id: str) -> Path:
    return RESULT_DIR / f"{job_id}.jump.json"


def save_job(job_id: str, data: dict[str, Any]) -> None:
    job_path(job_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Job saved: job_id=%s path=%s status=%s", job_id, job_path(job_id), data.get("status"))


def load_job(job_id: str) -> dict[str, Any]:
    path = job_path(job_id)
    if not path.exists():
        raise FileNotFoundError(job_id)
    return json.loads(path.read_text(encoding="utf-8"))


def update_job(job_id: str, **fields: Any) -> None:
    job = load_job(job_id)
    job.update(fields)
    job["updated_at"] = now_ts()
    save_job(job_id, job)
    logger.info(
        "Job updated: job_id=%s status=%s progress=%s error=%s",
        job_id,
        job.get("status"),
        job.get("progress"),
        job.get("error", ""),
    )
