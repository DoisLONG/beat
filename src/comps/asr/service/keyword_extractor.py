# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from typing import Any
import logging

from comps.asr.config import get_dataprep_llm_connection
from comps.asr.service.llm_api import LLMConfig, chat_completions


logger = logging.getLogger("asr-keyword-extractor")


WS_RE = re.compile(r"\s+")
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
RE_BAD_WORDS = re.compile(r"(步骤|操作|方法|流程|阶段|内容)$")
RE_FILLER_START = re.compile(r"^(这里基于|大家好|今天我|主要介绍|那个|我们现在|这里是|这一节|我们来看)")
ALLOWED_SUFFIX = [
    "介绍",
    "目的",
    "准备",
    "设备",
    "材料",
    "参数",
    "操作",
    "检查",
    "判定",
    "记录",
    "注意",
    "异常",
    "交接",
    "结束",
    "演示",
    "说明",
]
PROCESS_SIGNAL_RE = re.compile(r"(首先|然后|接着|随后|最后|下一步|第[一二三四五六七八九十]步|步骤[一二三四五六七八九十])")


def norm(value: str) -> str:
    return WS_RE.sub(" ", (value or "").strip())


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_language_code(language: str | None) -> str:
    if not language:
        return ""
    lang = str(language).strip().lower().replace("_", "-")
    aliases = {
        "cn": "zh",
        "zh-cn": "zh",
        "zh-hans": "zh",
        "zh-hant": "zh",
        "en-us": "en",
        "en-gb": "en",
        "th-th": "th",
        "auto": "",
    }
    if lang in aliases:
        return aliases[lang]
    if "-" in lang:
        return lang.split("-", 1)[0]
    return lang


def get_language_rule(language: str) -> str:
    if language == "en":
        return "title、keywords[].keyword 和 keywords[].desc 必须使用英文。"
    if language == "th":
        return "title、keywords[].keyword 和 keywords[].desc 必须使用泰文。"
    if language == "zh":
        return "title、keywords[].keyword 和 keywords[].desc 必须使用中文。"
    return "title、keywords[].keyword 和 keywords[].desc 必须与 ASR 原文主语言一致。"


def default_title_for_language(language: str) -> str:
    if language == "en":
        return "Video Analysis Result"
    if language == "th":
        return "ผลการวิเคราะห์วิดีโอ"
    return "视频解析结果"


def extract_json_block(content: str) -> str | None:
    cleaned = THINK_RE.sub("", content).strip()
    markdown_match = re.search(r"```json\s*([\{\[].*?[\}\]])\s*```", cleaned, re.DOTALL)
    if markdown_match:
        return markdown_match.group(1)
    object_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if object_match:
        return object_match.group(1)
    return None


def normalize_keyword_template(keyword: str, default_topic: str) -> str:
    normalized = norm(keyword)
    normalized = RE_FILLER_START.sub("", normalized).strip()
    normalized = RE_BAD_WORDS.sub("", normalized).strip()
    normalized = re.sub(r"[。，？！,.?!]$", "", normalized)

    if not normalized or len(normalized) < 2:
        return f"{default_topic}说明"
    if re.match(r"^(\d+[\.、\s]|第[一二三四五六七八九十][步点]|步骤[一二三四五六七八九十]|Step\s*\d)", normalized):
        return normalized
    for suffix in ALLOWED_SUFFIX:
        if normalized.endswith(suffix):
            return normalized
    if len(normalized) >= 4 and not normalized.endswith(("的", "了", "呢")):
        return normalized
    return f"{normalized}操作"


def estimate_keyword_target(
    duration_s: float,
    segment_count: int,
    requested_min_k: int,
    requested_max_k: int,
) -> tuple[int, int]:
    requested_min = max(2, requested_min_k)
    requested_max = max(requested_min, requested_max_k)

    if duration_s < 60.0:
        adaptive_min, adaptive_max = 2, 3
    elif duration_s < 180.0:
        adaptive_min, adaptive_max = 3, 5
    elif duration_s < 600.0:
        adaptive_min, adaptive_max = 5, 8
    else:
        adaptive_min, adaptive_max = 8, 12

    if segment_count > 0:
        segment_cap = max(2, segment_count // 4)
        adaptive_max = min(adaptive_max, segment_cap)
        adaptive_min = min(adaptive_min, adaptive_max)

    target_max = min(requested_max, adaptive_max)
    target_min = min(requested_min, target_max)
    return target_min, target_max


def get_merge_gap(duration_s: float) -> float:
    return round(min(5.0, max(1.0, duration_s * 0.015)), 2)


def looks_like_boundary(prev_segment: dict[str, Any] | None, segment: dict[str, Any], duration_s: float) -> bool:
    if prev_segment is None:
        return True
    current_text = norm(str(segment.get("text", "")))
    if not current_text:
        return False
    if PROCESS_SIGNAL_RE.search(current_text):
        return True

    previous_end = safe_float(prev_segment.get("end", 0.0))
    current_start = safe_float(segment.get("start", 0.0))
    if current_start - previous_end >= max(3.0, duration_s * 0.02):
        return True

    previous_text = norm(str(prev_segment.get("text", "")))
    if previous_text and current_text and previous_text[:2] != current_text[:2] and len(current_text) >= 10:
        return True
    return False


def build_outline_candidates(segments: list[dict[str, Any]], duration_s: float, max_candidates: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    previous_segment: dict[str, Any] | None = None
    for segment in segments:
        if looks_like_boundary(previous_segment, segment, duration_s):
            candidates.append(
                {
                    "start": round(safe_float(segment.get("start", 0.0)), 2),
                    "text": norm(str(segment.get("text", ""))),
                }
            )
        previous_segment = segment

    if not candidates and segments:
        candidates.append(
            {
                "start": round(safe_float(segments[0].get("start", 0.0)), 2),
                "text": norm(str(segments[0].get("text", ""))),
            }
        )

    if len(candidates) > max_candidates:
        step = len(candidates) / max_candidates
        sampled: list[dict[str, Any]] = []
        index = 0.0
        while int(index) < len(candidates) and len(sampled) < max_candidates:
            sampled.append(candidates[int(index)])
            index += step
        candidates = sampled
    return candidates


def align_start_to_allowed(
    raw_start: float,
    duration_s: float,
    allowed_starts: list[float] | None,
) -> float:
    clipped = round(min(max(raw_start, 0.0), duration_s), 2)
    if not allowed_starts:
        return clipped
    if clipped in allowed_starts:
        return clipped
    return min(allowed_starts, key=lambda candidate: (abs(candidate - clipped), candidate))


def postprocess_keywords(
    items: list[dict[str, Any]],
    duration_s: float,
    default_topic: str,
    min_k: int,
    max_k: int,
    allowed_starts: list[float] | None = None,
) -> list[dict[str, Any]]:
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        raw_start = safe_float(item.get("time", {}).get("start", 0.0))
        aligned_start = align_start_to_allowed(raw_start, duration_s, allowed_starts)
        normalized_items.append(
            {
                "keyword": normalize_keyword_template(str(item.get("keyword", "")), default_topic),
                "desc": norm(str(item.get("desc", ""))),
                "original": norm(str(item.get("original", ""))),
                "start": aligned_start,
            }
        )

    normalized_items.sort(key=lambda item: item["start"])
    cleaned: list[dict[str, Any]] = []
    merge_gap = get_merge_gap(duration_s)
    for item in normalized_items:
        if not cleaned:
            cleaned.append(item)
            continue
        if item["start"] - cleaned[-1]["start"] < merge_gap:
            if len(item["desc"]) > len(cleaned[-1]["desc"]):
                cleaned[-1] = item
            continue
        cleaned.append(item)

    if not cleaned:
        cleaned = [
            {
                "keyword": f"{default_topic}介绍",
                "desc": f"关于{default_topic}的整体操作演示。",
                "original": "",
                "start": 0.0,
            }
        ]

    if len(cleaned) > max_k:
        cleaned = cleaned[:max_k]
    elif len(cleaned) < min_k and normalized_items:
        existing_starts = {item["start"] for item in cleaned}
        for item in normalized_items:
            if item["start"] in existing_starts:
                continue
            cleaned.append(item)
            existing_starts.add(item["start"])
            cleaned.sort(key=lambda candidate: candidate["start"])
            if len(cleaned) >= min_k:
                break

    final_keywords: list[dict[str, Any]] = []
    for index, item in enumerate(cleaned):
        start = 0.0 if index == 0 else item["start"]
        if index < len(cleaned) - 1:
            end = round(max(start + 0.1, cleaned[index + 1]["start"]), 2)
        else:
            end = round(max(start + 0.1, duration_s), 2)
        final_keywords.append(
            {
                "keyword": item["keyword"],
                "desc": item["desc"],
                "original": item["original"],
                "time": {"start": start, "end": end},
            }
        )
    return final_keywords


def generate_jump_result(
    asr_result: dict[str, Any],
    *,
    min_k: int,
    max_k: int,
    output_language: str | None = None,
) -> dict[str, Any]:
    segments = asr_result.get("segments") or []
    duration = safe_float(asr_result.get("duration", 0.0))
    doc_id = str(asr_result.get("doc_id", ""))
    resolved_language = normalize_language_code(output_language or str(asr_result.get("language", "")))
    logger.info(
        "Keyword extraction language context: doc_id=%s output_language=%s segment_count=%s duration=%.2f",
        doc_id,
        resolved_language or "auto",
        len(segments),
        duration,
    )
    target_min_k, target_max_k = estimate_keyword_target(duration, len(segments), min_k, max_k)
    outline_candidates = build_outline_candidates(segments, duration, max_candidates=max(target_max_k * 2, 6))
    allowed_starts: list[float] = []

    total_segments = len(segments)
    if total_segments <= 600:
        content_for_llm = "\n".join(f"[{segment.get('start', 0.0):.2f}s] {segment.get('text', '')}" for segment in segments)
        allowed_starts = sorted({round(safe_float(segment.get("start", 0.0)), 2) for segment in segments})
        granularity_note = "章节的 start 时间必须和输入文本中的 [xx.xxs] 标记完全一致。"
    else:
        group_size = 5 if total_segments > 1500 else 3
        grouped_content: list[str] = []
        for index in range(0, total_segments, group_size):
            batch = segments[index:index + group_size]
            if not batch:
                continue
            group_start = round(safe_float(batch[0].get("start", 0.0)), 2)
            allowed_starts.append(group_start)
            grouped_content.append(
                f"[{group_start:.2f}s] "
                + " ".join(norm(str(segment.get("text", ""))) for segment in batch)
            )
        content_for_llm = "\n".join(grouped_content)
        allowed_starts = sorted(set(allowed_starts))
        granularity_note = f"当前输入按每 {group_size} 句聚合，章节时间必须对齐到可见的时间戳。"

    language_rule = get_language_rule(resolved_language)
    system_prompt = f"""你是技术视频章节抽取器，只能输出 JSON。

任务：
1. 生成视频标题 title。
2. 生成 {target_min_k} 到 {target_max_k} 个章节 keywords。
3. 章节应体现流程推进，并修正明显术语错误。

硬约束（必须满足）：
1. keywords 按 time.start 严格升序且不重复。
2. {granularity_note}
3. keyword 长度 6-14 个字，desc 长度 12-40 个字。
4. original 必须来自输入文本，不可杜撰。
5. 短视频保留关键阶段，不要为了凑数量强行拆分。
6. 仅输出 JSON，不要输出解释或 Markdown。
7. {language_rule}

输出格式：
{{
  "title": "视频标题",
  "keywords": [
    {{
      "keyword": "章节标题",
      "desc": "该章节摘要",
      "original": "原始 ASR 文本片段",
      "time": {{"start": 0.0}}
    }}
  ]
}}"""

    llm_base_url, llm_model, llm_api_key = get_dataprep_llm_connection()
    cfg = LLMConfig(
        base_url=llm_base_url,
        model=llm_model,
        api_key=llm_api_key,
        max_tokens=4096,
        temperature=0.0,
    )
    response = chat_completions(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "doc_id": doc_id,
                        "video_duration": duration,
                        "outline_candidates": outline_candidates,
                        "allowed_starts": allowed_starts,
                        "output_language": resolved_language or "auto",
                        "content": content_for_llm,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        cfg=cfg,
    )
    logger.info(
        "Keyword extraction LLM call completed: doc_id=%s response_chars=%s output_language=%s",
        doc_id,
        len(response or ""),
        resolved_language or "auto",
    )

    title = ""
    raw_items: list[dict[str, Any]] = []
    json_block = extract_json_block(response)
    if json_block:
        try:
            payload = json.loads(json_block)
            title = str(payload.get("title", "")).strip()
            keywords = payload.get("keywords", [])
            if isinstance(keywords, list):
                raw_items = [item for item in keywords if isinstance(item, dict)]
        except json.JSONDecodeError:
            raw_items = []

    if not title:
        head_text = "".join(str(segment.get("text", "")) for segment in segments[:3])
        title = RE_FILLER_START.sub("", head_text).strip()[:20] or doc_id or default_title_for_language(resolved_language)

    final_keywords = postprocess_keywords(
        raw_items,
        duration,
        title,
        target_min_k,
        target_max_k,
        allowed_starts=allowed_starts,
    )
    logger.info(
        "Keyword extraction finalized: doc_id=%s title=%s keyword_count=%s output_language=%s",
        doc_id,
        title,
        len(final_keywords),
        resolved_language or "auto",
    )
    return {
        "doc_id": doc_id,
        "language": resolved_language or str(asr_result.get("language", "")),
        "title": title,
        "duration": duration,
        "segments": segments,
        "keywords": final_keywords,
    }
