# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
import re
from typing import Any

from comps.excel.config import get_dataprep_llm_connection
from comps.excel.service.llm_api import LLMConfig, chat_completions


logger = logging.getLogger("excel-llm-processor")


def extract_json_from_llm_response(response: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for pattern in (r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"\{.*\}"):
        matches = re.findall(pattern, cleaned, re.DOTALL)
        for match in matches:
            try:
                payload = json.loads(match.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "headers" in payload:
                return payload
    return None


def _analyze_chunk_with_llm(
    text: str,
    predefined_headers: list[str] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    resolved_language = (language or "").strip().lower()
    if "-" in resolved_language:
        resolved_language = resolved_language.split("-", 1)[0]
    prompt = """
你是一个多语种教学内容结构化助手。
请把讲解型文本整理成 JSON 表格数据。

要求：
1. 必须严格返回 {"headers": [...], "rows": [[...], [...]]} 这种 JSON 结构。
2. headers 第一列必须始终是 "No."。
3. 如果给定了预定义表头，必须严格沿用，不允许增删列。
4. 除 "No." 外，其他表头和所有单元格内容必须与源内容语种保持一致。
5. 禁止把内容翻译成其他语种。
6. 术语、专有名词、缩写等按原文保留。
7. 只输出 JSON，不要输出解释、说明或 Markdown。
8. 当 source language 为 "auto" 或为空时，先根据输入内容判断主语种，再严格使用该主语种输出（除 "No." 外）。
"""
    if predefined_headers:
        user_content = (
            f"source language: {resolved_language or 'auto'}\n"
            f"预定义表头: {json.dumps(predefined_headers, ensure_ascii=False)}\n"
            f"请分析以下文本并输出 JSON:\n{text}"
        )
    else:
        user_content = (
            f"source language: {resolved_language or 'auto'}\n"
            f"请分析以下文本并自行设计合适表头，输出 JSON:\n{text}"
        )

    llm_base_url, llm_model, llm_api_key = get_dataprep_llm_connection()
    cfg = LLMConfig(
        base_url=llm_base_url,
        model=llm_model,
        api_key=llm_api_key,
        temperature=0.1,
        max_tokens=4096,
    )
    response = chat_completions(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        cfg=cfg,
    )
    result = extract_json_from_llm_response(response)
    if result is None:
        raise ValueError("LLM返回的不是有效JSON格式")
    return result


def analyze_content_with_llm(text: str, language: str | None = None) -> dict[str, Any]:
    chunk_size = 4000
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)] or [text]
    logger.info("Analyze content with LLM: text_length=%s chunk_count=%s", len(text), len(chunks))

    headers: list[str] = []
    all_rows: list[list[str]] = []
    for index, chunk in enumerate(chunks):
        if len(chunk) < 50 and index > 0:
            logger.info("Skip tiny tail chunk: index=%s length=%s", index, len(chunk))
            continue
        logger.info("Processing chunk: index=%s length=%s", index, len(chunk))
        result = _analyze_chunk_with_llm(chunk, headers or None, language=language)
        if not headers:
            raw_headers = result.get("headers", ["No.", "Content"])
            headers = raw_headers if isinstance(raw_headers, list) and raw_headers else ["No.", "Content"]
            if not headers:
                headers = ["No.", "Content"]
            headers[0] = "No."
        for row in result.get("rows", []):
            if isinstance(row, dict):
                normalized_row = [str(row.get(header, "")) for header in headers]
            elif isinstance(row, list):
                normalized_row = [str(value) for value in (row + [""] * len(headers))[:len(headers)]]
            else:
                continue
            all_rows.append(normalized_row)

    for row_index, row in enumerate(all_rows, 1):
        row[0] = str(row_index)

    if not all_rows:
        all_rows = [["1"] + [""] * (len(headers) - 1)] if headers else [["1", ""]]
        if not headers:
            headers = ["No.", "Content"]
    headers[0] = "No."
    logger.info("LLM analyze completed: headers=%s rows=%s", len(headers), len(all_rows))

    return {"headers": headers, "rows": all_rows}
