# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import File, HTTPException, Query, Request, UploadFile

from comps import opea_microservices, register_microservice
from comps.account.auth import require_auth_dict
from comps.asr.config import LOG_LEVEL, UPLOAD_DIR
from comps.asr.service.glossary_router import router as glossary_router
from comps.asr.service.job_store import load_job, now_ts, save_job
from comps.asr.service.pipeline import EXECUTOR, run_pipeline


SERVICE_NAME = "opea_service@video"
logging.basicConfig(level=LOG_LEVEL, force=True)
logger = logging.getLogger("asr-api")
logger.setLevel(LOG_LEVEL)


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/health",
    host="0.0.0.0",
    port=8000,
    methods=["GET"],
)
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "video"}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/v1/asr/jobs",
    host="0.0.0.0",
    port=8000,
)
@require_auth_dict()
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    min_k: int = Query(6, ge=3, le=20),
    max_k: int = Query(9, ge=3, le=30),
    chunk_s: float = Query(25.0, ge=8.0, le=120.0),
    language: str | None = Query(None, description="语言代码，如 zh, en, th"),
) -> dict[str, object]:
    filename = file.filename or ""
    if not filename.lower().endswith(".mp4"):
        logger.warning("Rejected create_job request: filename=%s is not mp4", filename)
        raise HTTPException(status_code=400, detail="only .mp4 is supported")

    job_id = "ASRJOB_" + uuid.uuid4().hex[:16]
    video_path = UPLOAD_DIR / f"{job_id}.mp4"
    logger.info(
        "Received ASR job create request: job_id=%s filename=%s min_k=%s max_k=%s chunk_s=%s language=%s",
        job_id,
        filename,
        min_k,
        max_k,
        chunk_s,
        language,
    )

    with video_path.open("wb") as output_file:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            output_file.write(chunk)

    save_job(
        job_id,
        {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "created_at": now_ts(),
            "updated_at": now_ts(),
            "error": "",
            "input": {
                "filename": filename,
                "stored_path": str(video_path),
                "min_k": min_k,
                "max_k": max_k,
                "chunk_s": chunk_s,
                "language": language,
            },
            "result_file": "",
        },
    )
    # debug_sync = __import__("os").getenv("DEBUG_SYNC", "1")
    # if debug_sync:
    #     logger.info("Running pipeline in sync mode for job_id=%s DEBUG_SYNC=%s", job_id, debug_sync)
    #     run_pipeline(job_id, video_path, min_k, max_k, chunk_s, language)
    # else:
    logger.info("Running pipeline in async mode for job_id=%s", job_id)
    EXECUTOR.submit(run_pipeline, job_id, video_path, min_k, max_k, chunk_s, language)
    return {"code": 200, "message": "success", "data": {"job_id": job_id, "status": "queued"}}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/v1/asr/jobs/{job_id}/status",
    host="0.0.0.0",
    port=8000,
    methods=["GET"],
)
@require_auth_dict()
async def get_status(request: Request, job_id: str) -> dict[str, object]:
    try:
        job = load_job(job_id)
    except FileNotFoundError as exc:
        logger.warning("Status query failed: job_id=%s not found", job_id)
        raise HTTPException(status_code=404, detail="job_id not found") from exc
    logger.info(
        "Status queried: job_id=%s status=%s progress=%s",
        job_id,
        job.get("status"),
        job.get("progress", 0.0),
    )
    return {
        "code": 200,
        "message": "success",
        "data": {
            "job_id": job["job_id"],
            "status": job["status"],
            "progress": job.get("progress", 0.0),
            "error": job.get("error", ""),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
        },
    }


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/v1/asr/jobs/{job_id}/result",
    host="0.0.0.0",
    port=8000,
    methods=["GET"],
)
@require_auth_dict()
async def get_result(request: Request, job_id: str) -> dict[str, object]:
    try:
        job = load_job(job_id)
    except FileNotFoundError as exc:
        logger.warning("Result query failed: job_id=%s not found", job_id)
        raise HTTPException(status_code=404, detail="job_id not found") from exc

    if job.get("status") != "succeeded":
        logger.info("Result not ready: job_id=%s status=%s", job_id, job.get("status"))
        return {
            "code": 200,
            "message": "not_ready",
            "data": {
                "job_id": job_id,
                "status": job.get("status"),
                "error": job.get("error", ""),
            },
        }

    result_file = Path(job.get("result_file", ""))
    if not result_file.exists():
        logger.error("Result file missing: job_id=%s path=%s", job_id, result_file)
        raise HTTPException(status_code=500, detail="result missing")

    data = json.loads(result_file.read_text(encoding="utf-8"))
    logger.info("Result returned: job_id=%s result_file=%s", job_id, result_file)
    return {"code": 200, "message": "success", "data": data}


opea_microservices[SERVICE_NAME].app.include_router(glossary_router)


if __name__ == "__main__":
    opea_microservices[SERVICE_NAME].start()
    # opea_microservices[SERVICE_NAME].run()
