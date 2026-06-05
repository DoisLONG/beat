# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from typing import Any

import requests

from comps.excel.config import EXCEL_ASR_BASE_URL


logger = logging.getLogger("excel-asr-client")


def fetch_asr_result(job_id: str, auth_header: str = "", timeout_s: int = 120) -> dict[str, Any]:
    url = f"{EXCEL_ASR_BASE_URL.rstrip('/')}/api/v1/asr/jobs/{job_id}/result"
    headers = {"Authorization": auth_header} if auth_header else None
    logger.info("Fetching ASR result: job_id=%s url=%s timeout=%s", job_id, url, timeout_s)
    response = requests.get(url, headers=headers, timeout=timeout_s)
    if response.status_code != 200:
        logger.error("ASR result fetch failed: job_id=%s status=%s", job_id, response.status_code)
        raise RuntimeError(f"ASR result http {response.status_code}: {response.text[:300]}")
    payload = response.json()
    if payload.get("message") != "success":
        logger.warning("ASR result not ready or failed: job_id=%s message=%s", job_id, payload.get("message"))
        raise RuntimeError(f"ASR result not ready or failed: {payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        logger.error("ASR result payload invalid: job_id=%s", job_id)
        raise RuntimeError(f"ASR result invalid payload: {payload}")
    logger.info("ASR result fetched successfully: job_id=%s", job_id)
    return data


def extract_full_text(asr_result: dict[str, Any]) -> str:
    segments = asr_result.get("segments", [])
    if segments:
        return "\n".join(
            str(segment.get("text", "")).strip()
            for segment in segments
            if str(segment.get("text", "")).strip()
        )
    keywords = asr_result.get("keywords", [])
    if keywords:
        return " ".join(
            f"{item.get('keyword', '')}: {item.get('original', '')}"
            for item in keywords
        )
    return str(asr_result.get("text", ""))
