# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from comps.asr.config import ASR_CHUNK_WORKERS, ASR_DIR, ASR_FFMPEG_SEGMENT_SECONDS, ASR_MAX_WORKERS, TMP_DIR
from comps.asr.models import ASRSegment
from comps.asr.service.asr_engine import get_asr_engine
from comps.asr.service.glossary import GlossaryManager
from comps.asr.service.job_store import result_path, update_job
from comps.asr.service.keyword_extractor import generate_jump_result
from comps.asr.service.refine_agent import RefineAgentService


logger = logging.getLogger("asr-pipeline")
EXECUTOR = ThreadPoolExecutor(max_workers=ASR_MAX_WORKERS)
_glossary_mgr = GlossaryManager()
_refine_agent: RefineAgentService | None = None


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


def resolve_detected_language(requested_language: str | None, detected_languages: list[str]) -> str:
    requested = normalize_language_code(requested_language)
    if requested:
        return requested

    normalized = [normalize_language_code(lang) for lang in detected_languages if normalize_language_code(lang)]
    if not normalized:
        return "zh"

    counter: dict[str, int] = {}
    for lang in normalized:
        counter[lang] = counter.get(lang, 0) + 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def is_chinese_language(language: str | None) -> bool:
    return normalize_language_code(language).startswith("zh")


def get_refine_agent() -> RefineAgentService:
    global _refine_agent
    if _refine_agent is None:
        _refine_agent = RefineAgentService(_glossary_mgr)
    return _refine_agent


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg/ffprobe not found")


def get_audio_duration(audio_path: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 600.0
    return 600.0


def has_audio_stream(video_path: Path) -> bool:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or result.stdout.strip()}")
    return any(line.strip() == "audio" for line in result.stdout.splitlines())


def resolve_segment_seconds(chunk_s: float | None) -> int:
    if chunk_s is None:
        return ASR_FFMPEG_SEGMENT_SECONDS
    return max(8, int(round(chunk_s)))


def extract_mp3_chunks(video_path: Path, output_dir: Path, segment_seconds: int | None = None) -> list[Path]:
    if not has_audio_stream(video_path):
        raise RuntimeError("uploaded video does not contain an audio stream")
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "chunk_%03d.mp3"
    resolved_segment_seconds = resolve_segment_seconds(segment_seconds)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        "-f",
        "segment",
        "-segment_time",
        str(resolved_segment_seconds),
        str(pattern),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Output file #0 does not contain any stream" in stderr:
            raise RuntimeError("uploaded video does not contain an audio stream")
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    chunks = sorted(output_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise RuntimeError("ffmpeg failed to produce audio chunks")
    return list(chunks)


def save_asr_outputs(asr_result: dict[str, Any], out_json: Path, out_txt: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(asr_result, ensure_ascii=False, indent=2), encoding="utf-8")
    text = "\n".join(
        segment["text"] for segment in asr_result.get("segments", []) if segment.get("text")
    )
    out_txt.write_text(text, encoding="utf-8")


def run_pipeline(
    job_id: str,
    video_file: Path,
    min_k: int,
    max_k: int,
    chunk_s: float,
    language: str | None = None,
) -> None:
    try:
        logger.info(
            "Pipeline started: job_id=%s video=%s min_k=%s max_k=%s chunk_s=%s language=%s",
            job_id,
            video_file,
            min_k,
            max_k,
            chunk_s,
            language,
        )
        update_job(job_id, status="running", progress=0.05, error="")
        ensure_ffmpeg()

        audio_dir = TMP_DIR / job_id / "audio_chunks"
        chunks = extract_mp3_chunks(video_file, audio_dir, segment_seconds=resolve_segment_seconds(chunk_s))
        logger.info("Audio chunks extracted: job_id=%s chunk_count=%s dir=%s", job_id, len(chunks), audio_dir)
        update_job(job_id, progress=0.25)

        asr_engine = get_asr_engine()
        offsets: list[float] = []
        current_offset = 0.0
        for chunk in chunks:
            offsets.append(current_offset)
            current_offset += get_audio_duration(chunk)
        total_duration = current_offset
        logger.info("Chunk offsets prepared: job_id=%s total_duration=%.2f", job_id, total_duration)

        def _process_chunk(chunk_path: Path, offset: float) -> tuple[list[dict[str, Any]], str]:
            result = asr_engine.transcribe(chunk_path, language=language)
            segments = result.get("segments", [])
            for segment in segments:
                segment["start"] += offset
                segment["end"] += offset
            detected_language = normalize_language_code(result.get("language"))
            logger.info(
                "Chunk transcription detail: job_id=%s chunk=%s segment_count=%s detected_language=%s",
                job_id,
                chunk_path.name,
                len(segments),
                detected_language or "unknown",
            )
            return segments, detected_language

        ordered_results: list[tuple[list[dict[str, Any]], str] | None] = [None] * len(chunks)
        with ThreadPoolExecutor(max_workers=ASR_CHUNK_WORKERS) as pool:
            future_map = {
                pool.submit(_process_chunk, chunk, offset): index
                for index, (chunk, offset) in enumerate(zip(chunks, offsets))
            }
            for future in as_completed(future_map):
                index = future_map[future]
                ordered_results[index] = future.result()
        logger.info("Chunk transcription completed: job_id=%s", job_id)

        merged_segments: list[dict[str, Any]] = []
        chunk_languages: list[str] = []
        for chunk_result in ordered_results:
            if not chunk_result:
                continue
            chunk_segments, chunk_language = chunk_result
            if chunk_language:
                chunk_languages.append(chunk_language)
            if chunk_segments:
                merged_segments.extend(chunk_segments)
        merged_segments.sort(key=lambda item: item["start"])
        logger.info("ASR merge completed: job_id=%s segment_count=%s", job_id, len(merged_segments))

        detected_language = resolve_detected_language(language, chunk_languages)
        logger.info(
            "ASR language resolved: job_id=%s requested=%s detected_candidates=%s resolved=%s",
            job_id,
            language or "auto",
            chunk_languages,
            detected_language,
        )

        asr_result = {
            "segments": merged_segments,
            "language": detected_language,
            "duration": total_duration,
            "doc_id": job_id,
            "source_video": str(video_file),
        }

        if asr_result.get("segments") and is_chinese_language(detected_language):
            logger.info(
                "ASR refine decision: job_id=%s refine_enabled=true language=%s segment_count=%s",
                job_id,
                detected_language,
                len(asr_result.get("segments", [])),
            )
            asr_segments = [
                ASRSegment(
                    id=str(index + 1),
                    start=segment.get("start", 0.0),
                    end=segment.get("end", 0.0),
                    text=segment.get("text", ""),
                )
                for index, segment in enumerate(asr_result["segments"])
            ]
            try:
                refine_result = get_refine_agent().process(asr_segments)
                if refine_result.status == "success" and refine_result.refined_segments:
                    asr_result["segments"] = [
                        {
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.refined_text,
                        }
                        for segment in refine_result.refined_segments
                    ]
                    asr_result["corrected"] = True
                    asr_result["correction_info"] = {
                        "new_terms_added": refine_result.new_terms_added,
                        "message": refine_result.message,
                    }
                    logger.info(
                        "ASR refine succeeded: job_id=%s corrected_segment_count=%s new_terms=%s",
                        job_id,
                        len(refine_result.refined_segments),
                        len(refine_result.new_terms_added),
                    )
            except Exception as exc:  # noqa: BLE001
                asr_result["correction_error"] = str(exc)
                logger.warning("ASR refine failed but pipeline continues: job_id=%s err=%s", job_id, exc)
        elif asr_result.get("segments"):
            asr_result["corrected"] = False
            asr_result["correction_info"] = {
                "skipped": True,
                "reason": f"skip refine for non-zh language: {detected_language}",
            }
            logger.info(
                "ASR refine decision: job_id=%s refine_enabled=false language=%s reason=non_zh",
                job_id,
                detected_language,
            )

        asr_json = ASR_DIR / f"{job_id}.asr.json"
        asr_txt = ASR_DIR / f"{job_id}.asr.txt"
        save_asr_outputs(asr_result, asr_json, asr_txt)
        logger.info("ASR outputs saved: job_id=%s json=%s txt=%s", job_id, asr_json, asr_txt)
        update_job(job_id, progress=0.60)

        jump_result = generate_jump_result(asr_result, min_k=min_k, max_k=max_k, output_language=detected_language)
        final_result = result_path(job_id)
        final_result.write_text(json.dumps(jump_result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Jump result generated: job_id=%s result=%s", job_id, final_result)

        update_job(job_id, status="succeeded", progress=1.0, result_file=str(final_result))
        logger.info("Pipeline finished successfully: job_id=%s", job_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ASR pipeline failed: job_id=%s err=%s", job_id, exc)
        update_job(job_id, status="failed", error=repr(exc), progress=1.0)
