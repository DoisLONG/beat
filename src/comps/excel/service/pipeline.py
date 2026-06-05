# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from comps.excel.config import EXCEL_EXECUTOR_WORKERS, OUT_DIR, now_ts, safe_filename, update_job
from comps.excel.service.asr_client import extract_full_text, fetch_asr_result
from comps.excel.service.excel_writer import create_excel_from_structure
from comps.excel.service.llm_processor import analyze_content_with_llm
from comps.excel.service.upload_client import upload_excel


logger = logging.getLogger("excel-pipeline")
EXECUTOR = ThreadPoolExecutor(max_workers=EXCEL_EXECUTOR_WORKERS)


def run_excel_pipeline(
    task_id: str,
    job_id: str,
    position_id: int,
    token: str,
    start_time: str,
    end_time: str,
    custom_title: str = "",
    lang: str = "zh",
) -> None:
    try:
        logger.info(
            "Excel pipeline started: task_id=%s job_id=%s position_id=%s start_time=%s end_time=%s lang=%s",
            task_id,
            job_id,
            position_id,
            start_time,
            end_time,
            lang,
        )
        update_job(task_id, status="running", progress="开始处理", upload_done=False, upload_resp={})

        asr_result = fetch_asr_result(job_id, auth_header=token)
        logger.info("ASR result fetched: task_id=%s job_id=%s", task_id, job_id)
        update_job(task_id, progress="已获取ASR结果")

        full_text = extract_full_text(asr_result)
        if not full_text:
            raise ValueError("无法从ASR结果中提取有效文本")
        logger.info("ASR text extracted: task_id=%s text_length=%s", task_id, len(full_text))
        update_job(task_id, progress="已提取文本", text_length=len(full_text))

        asr_language = str(asr_result.get("language", "")).strip()
        table_structure = analyze_content_with_llm(full_text, language=asr_language)
        logger.info(
            "LLM table analyzed: task_id=%s language=%s headers=%s rows=%s",
            task_id,
            asr_language or "auto",
            len(table_structure.get("headers", [])),
            len(table_structure.get("rows", [])),
        )
        update_job(task_id, progress="已分析内容结构")

        preferred_title = (custom_title or "").strip()
        title = preferred_title or str(asr_result.get("title", "")).strip() or f"内容表格_{job_id}"
        if preferred_title:
            output_name = f"{safe_filename(preferred_title)}.xlsx"
        else:
            output_name = f"{int(now_ts() * 1000)}.xlsx"
        output_path = OUT_DIR / output_name
        create_excel_from_structure(table_structure, output_path, title)
        logger.info("Excel file generated: task_id=%s path=%s", task_id, output_path)

        update_job(
            task_id,
            progress="Excel生成完成",
            excel_path=str(output_path),
            excel_done=True,
            output_info={
                "file_name": output_path.name,
                "file_size": output_path.stat().st_size,
                "headers": table_structure.get("headers", []),
                "row_count": len(table_structure.get("rows", [])),
            },
            generated_at=now_ts(),
        )

        upload_response = upload_excel(output_path, position_id, token, start_time, end_time, lang=lang)
        logger.info(
            "Upload response received: task_id=%s http_status=%s",
            task_id,
            upload_response.get("http_status"),
        )
        update_job(task_id, upload_resp=upload_response, progress="上传调用完成")
        if upload_response.get("http_status") != 200:
            error_text = upload_response.get("text", "")[:200]
            raise RuntimeError(f"上传失败: HTTP {upload_response.get('http_status')} - {error_text}")

        update_job(task_id, status="succeeded", progress="上传完成", upload_done=True)
        logger.info("Excel pipeline succeeded: task_id=%s", task_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Excel pipeline failed: task_id=%s err=%s", task_id, exc)
        update_job(
            task_id,
            status="failed",
            error=str(exc),
            progress="处理失败",
            error_details=repr(exc),
        )
