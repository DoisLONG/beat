# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

from comps.excel.config import (
    SOP_UPLOAD_AUTH_HEADER,
    SOP_UPLOAD_ENABLED,
    SOP_UPLOAD_FILE_FIELD,
    SOP_UPLOAD_FILE_TYPE,
    SOP_UPLOAD_URL,
)


logger = logging.getLogger("excel-upload-client")


def upload_excel(
    xlsx_path: Path,
    position_id: int,
    token: str,
    start_time: str,
    end_time: str,
    lang: str = "zh",
    timeout_s: int = 120,
) -> dict[str, Any]:
    if not SOP_UPLOAD_ENABLED:
        logger.info("Upload skipped because SOP_UPLOAD_ENABLED=false")
        return {
            "http_status": 200,
            "text": "upload disabled",
            "json": {"message": "upload_disabled"},
            "enabled": False,
        }

    if not xlsx_path.exists():
        logger.error("Upload failed because file does not exist: %s", xlsx_path)
        raise RuntimeError(f"xlsx not found: {xlsx_path}")

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = token
    elif SOP_UPLOAD_AUTH_HEADER:
        headers["Authorization"] = SOP_UPLOAD_AUTH_HEADER

    with xlsx_path.open("rb") as file_obj:
        files = {
            SOP_UPLOAD_FILE_FIELD: (
                xlsx_path.name,
                file_obj,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        data = {
            "position_id": str(position_id),
            "file_type": SOP_UPLOAD_FILE_TYPE,
            "start_time": start_time,
            "end_time": end_time,
            "lang": lang,
        }
        try:
            logger.info(
                "Uploading excel: path=%s url=%s position_id=%s start_time=%s end_time=%s lang=%s",
                xlsx_path,
                SOP_UPLOAD_URL,
                position_id,
                start_time,
                end_time,
                lang,
            )
            response = requests.post(
                SOP_UPLOAD_URL,
                files=files,
                data=data,
                headers=headers,
                timeout=timeout_s,
            )
        except requests.exceptions.Timeout:
            logger.error("Upload timeout: path=%s url=%s", xlsx_path, SOP_UPLOAD_URL)
            return {
                "http_status": 408,
                "text": "Request Timeout",
                "json": {"error": "timeout"},
                "enabled": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Upload exception: path=%s url=%s err=%s", xlsx_path, SOP_UPLOAD_URL, exc)
            return {
                "http_status": 500,
                "text": str(exc),
                "json": {"error": str(exc)},
                "enabled": True,
            }

    try:
        payload = response.json()
    except ValueError:
        payload = None

    return {
        "http_status": response.status_code,
        "text": response.text[:2000],
        "json": payload,
        "enabled": True,
    }
