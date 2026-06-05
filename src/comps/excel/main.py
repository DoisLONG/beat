# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Dict

from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse

from comps import opea_microservices, register_microservice
from comps.account.auth import require_auth_dict
from comps.excel.config import EXCEL_ASR_BASE_URL, LOG_LEVEL, get_dataprep_llm_connection, load_job, now_ts, save_job
from comps.excel.service.pipeline import EXECUTOR, run_excel_pipeline
from comps.excel.service.time_range import resolve_time_range


SERVICE_NAME = "opea_service@excel"
logging.basicConfig(level=LOG_LEVEL, force=True)
logger = logging.getLogger("excel-api")
logger.setLevel(LOG_LEVEL)


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/health",
    host="0.0.0.0",
    port=8001,
    methods=["GET"],
)
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "excel"}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/v2/universal/jobs",
    host="0.0.0.0",
    port=8001,
    methods=["GET"],
)
@require_auth_dict()
async def create_excel_job(
    request: Request,
    position_id: int = Query(..., description="岗位ID"),
    job_id: str = Query(..., description="ASR任务ID"),
    custom_title: str = Query("", description="自定义表格标题"),
    start_time: str = Query("", description="开始时间，格式 YYYY-MM-DD"),
    end_time: str = Query("", description="结束时间，格式 YYYY-MM-DD"),
    user: Dict = None,
) -> dict[str, object]:
    resolved_start_time, resolved_end_time = resolve_time_range(start_time, end_time)
    if resolved_start_time > resolved_end_time:
        logger.warning(
            "Rejected excel job: start_time=%s end_time=%s",
            resolved_start_time,
            resolved_end_time,
        )
        raise HTTPException(status_code=400, detail="start_time 不能大于 end_time")

    lang = (user or {}).get("lang") or "zh"
    if lang not in ("zh", "en", "th"):
        lang = "zh"

    task_id = "UNIVERSAL_" + uuid.uuid4().hex[:16]
    logger.info(
        "Create excel job request: task_id=%s job_id=%s position_id=%s start_time=%s end_time=%s custom_title=%s lang=%s",
        task_id,
        job_id,
        position_id,
        resolved_start_time,
        resolved_end_time,
        custom_title,
        lang,
    )
    llm_base_url, llm_model, _llm_api_key = get_dataprep_llm_connection()
    save_job(
        task_id,
        {
            "task_id": task_id,
            "job_id": job_id,
            "position_id": position_id,
            "custom_title": custom_title,
            "status": "queued",
            "progress": "",
            "created_at": now_ts(),
            "updated_at": now_ts(),
            "config": {
                "asr_base_url": EXCEL_ASR_BASE_URL,
                "llm_base_url": llm_base_url,
                "llm_model": llm_model,
            },
            "requested_time_range": {
                "start_time": resolved_start_time,
                "end_time": resolved_end_time,
            },
        },
    )

    EXECUTOR.submit(
        run_excel_pipeline,
        task_id,
        job_id,
        position_id,
        request.headers.get("Authorization", ""),
        resolved_start_time,
        resolved_end_time,
        custom_title,
        lang,
    )
    logger.info("Excel pipeline submitted: task_id=%s job_id=%s", task_id, job_id)
    return {
        "code": 200,
        "message": "任务创建成功",
        "data": {
            "task_id": task_id,
            "status": "queued",
            "job_id": job_id,
            "api": {
                "status_url": f"/api/v2/universal/jobs/{task_id}/status",
                "result_url": f"/api/v2/universal/jobs/{task_id}/result",
            },
        },
    }


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/v2/universal/jobs/{task_id}/status",
    host="0.0.0.0",
    port=8001,
    methods=["GET"],
)
async def get_excel_status(task_id: str) -> dict[str, object]:
    try:
        job = load_job(task_id)
    except FileNotFoundError as exc:
        logger.warning("Status query failed: task_id=%s not found", task_id)
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    logger.info(
        "Status queried: task_id=%s status=%s progress=%s",
        task_id,
        job.get("status"),
        job.get("progress", ""),
    )

    response = {
        "task_id": job["task_id"],
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job.get("progress", ""),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "excel_done": job.get("excel_done", False),
        "upload_done": job.get("upload_done", False),
    }
    if job["status"] == "succeeded":
        response.update(
            {
                "excel_path": job.get("excel_path"),
                "headers": job.get("output_info", {}).get("headers", []),
                "row_count": job.get("output_info", {}).get("row_count", 0),
                "upload_status": job.get("upload_resp", {}).get("http_status"),
            }
        )
    if job["status"] == "failed":
        response["error"] = job.get("error", "")
    return {"code": 200, "message": "success", "data": response}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/v2/universal/jobs/{task_id}/result",
    host="0.0.0.0",
    port=8001,
    methods=["GET"],
)
async def get_excel_result(
    task_id: str,
    download: bool = Query(False, description="是否直接下载Excel文件"),
):
    try:
        job = load_job(task_id)
    except FileNotFoundError as exc:
        logger.warning("Result query failed: task_id=%s not found", task_id)
        raise HTTPException(status_code=404, detail="任务不存在") from exc

    if job["status"] != "succeeded":
        logger.info("Result not ready: task_id=%s status=%s", task_id, job.get("status"))
        return {
            "code": 200,
            "message": "任务未完成",
            "data": {"status": job["status"], "progress": job.get("progress", "")},
        }

    excel_path = Path(job.get("excel_path", ""))
    if not excel_path.exists():
        logger.error("Result file missing: task_id=%s path=%s", task_id, excel_path)
        raise HTTPException(status_code=404, detail="Excel文件不存在")

    if download:
        logger.info("Result download: task_id=%s path=%s", task_id, excel_path)
        return FileResponse(
            excel_path,
            filename=excel_path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    logger.info("Result metadata returned: task_id=%s path=%s", task_id, excel_path)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "file_name": excel_path.name,
            "file_size": excel_path.stat().st_size,
            "file_path": str(excel_path),
            "download_url": f"/api/v2/universal/jobs/{task_id}/result?download=true",
            "table_info": {
                "headers": job.get("output_info", {}).get("headers", []),
                "row_count": job.get("output_info", {}).get("row_count", 0),
            },
        },
    }


if __name__ == "__main__":
    # opea_microservices[SERVICE_NAME].run()
    opea_microservices[SERVICE_NAME].start()
