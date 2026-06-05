# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
import os
import time

import urllib3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import requests

from comps.asr.config import (
    ASR_API_KEY,
    ASR_ENGINE,
    ASR_SSL_VERIFY,
    ASR_WHISPER_COMPUTE_TYPE,
    ASR_WHISPER_DEVICE,
    ASR_WHISPER_MODEL_PATH,
    ASR_WHISPER_MODEL_SIZE,
    get_asr_connection,
)


logger = logging.getLogger("asr-engine")

if not ASR_SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BaseASREngine(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str | None = None) -> dict[str, Any]:
        raise NotImplementedError


class QwenASREngine(BaseASREngine):
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BACKOFF_SECONDS = 1.5

    def __init__(self) -> None:
        self.api_url, self.model_name, self.api_key, _transport, _runtime_options = get_asr_connection()
        logger.info("Initialized QwenASREngine: api_url=%s model=%s ssl_verify=%s", self.api_url, self.model_name, ASR_SSL_VERIFY)

    def transcribe(self, audio_path: Path, language: str | None = None) -> dict[str, Any]:
        target_language = (language or "").strip().lower()
        logger.info(
            "Starting remote transcription: file=%s language=%s api_url=%s",
            audio_path,
            target_language or "auto",
            self.api_url,
        )
        with audio_path.open("rb") as file_obj:
            files = {
                "file": (
                    audio_path.name,
                    file_obj.read(),
                    "audio/mpeg" if audio_path.suffix.lower() == ".mp3" else "audio/wav",
                )
            }
        data = {
            "model": self.model_name,
            "response_format": "verbose_json",
            "prompt": "Transcribe audio faithfully in the original spoken language. Preserve terminology, numbers, and punctuation.",
            "timestamp_granularities[]": "segment",
        }
        if target_language:
            data["language"] = target_language
        headers = {"Authorization": f"Bearer {self.api_key or ASR_API_KEY or 'local'}"}
        session = requests.Session()
        session.trust_env = False

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self._post_transcription(session, files, data, headers)
                response.raise_for_status()
                payload = response.json()
                detected_language = payload.get("language") or ""
                logger.info(
                    "Remote ASR response parsed: file=%s api_url=%s detected_language=%s attempt=%s",
                    audio_path,
                    self.api_url,
                    detected_language or "unknown",
                    attempt,
                )
                logger.info(
                    "Remote ASR request succeeded: file=%s api_url=%s attempt=%s",
                    audio_path,
                    self.api_url,
                    attempt,
                )
                return _normalize_asr_payload(payload, audio_path)
            except requests.exceptions.RequestException as exc:
                if self._is_retryable_exception(exc) and attempt < self.MAX_RETRIES:
                    status_code = exc.response.status_code if exc.response is not None else "n/a"
                    sleep_seconds = self.BACKOFF_SECONDS * attempt
                    logger.warning(
                        "Remote ASR request temporary failure: file=%s api_url=%s status=%s attempt=%s/%s retry_in=%.1fs",
                        audio_path,
                        self.api_url,
                        status_code,
                        attempt,
                        self.MAX_RETRIES,
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
                    continue
                self._raise_runtime_error(exc)

        raise RuntimeError("Remote ASR API failed after retries")

    @classmethod
    def _is_retryable_exception(cls, exc: requests.exceptions.RequestException) -> bool:
        if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if exc.response is None:
            return False
        return exc.response.status_code in cls.RETRYABLE_STATUS_CODES

    @staticmethod
    def _raise_runtime_error(exc: requests.exceptions.RequestException) -> None:
        logger.error(f"Remote ASR request failed: {exc}")
        if exc.response is not None:
            logger.error(f"ASR raw response status={exc.response.status_code} body={exc.response.text[:2000]}")
            try:
                error_payload = exc.response.json()
                message = error_payload.get("error", {}).get("message", "")
                code = error_payload.get("error", {}).get("code", 0)
                if code == 400:
                    raise RuntimeError(f"ASR请求参数错误: {message or exc.response.text[:300]}") from exc
                if code == 500 and "vllm[audio]" in message:
                    raise RuntimeError("ASR服务器缺少 vllm[audio] 依赖") from exc
            except json.JSONDecodeError:
                raise RuntimeError(f"ASR服务返回非JSON错误: {exc.response.text[:300]}") from exc
        raise RuntimeError(f"Remote ASR API failed: {exc}") from exc

    def _post_transcription(
        self,
        session: requests.Session,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str],
        headers: dict[str, str],
    ) -> requests.Response:
        try:
            response = self._post_once(session, self.api_url, files, data, headers)
        except requests.exceptions.SSLError:
            fallback_url = self._switch_scheme(self.api_url)
            if not fallback_url:
                raise

            logger.warning(
                "ASR SSL handshake failed with %s, retrying using %s",
                self.api_url,
                fallback_url,
            )
            response = self._post_once(session, fallback_url, files, data, headers)
            self.api_url = fallback_url

        if (
            response.status_code == 400
            and "plain HTTP request was sent to HTTPS port" in response.text
            and self.api_url.startswith("http://")
        ):
            fallback_url = self._switch_scheme(self.api_url)
            if fallback_url:
                logger.warning(f"ASR endpoint expects HTTPS, retrying with {fallback_url}")
                response = self._post_once(session, fallback_url, files, data, headers)
                self.api_url = fallback_url
        return response

    @staticmethod
    def _switch_scheme(url: str) -> str | None:
        if url.startswith("http://"):
            return "https://" + url[len("http://"):]
        if url.startswith("https://"):
            return "http://" + url[len("https://"):]
        return None

    @staticmethod
    def _post_once(
        session: requests.Session,
        url: str,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str],
        headers: dict[str, str],
    ) -> requests.Response:
        logger.info("Sending ASR request: url=%s", url)
        return session.post(
            url,
            files=files,
            data=data,
            headers=headers,
            timeout=600,
            verify=ASR_SSL_VERIFY,
        )


class FasterWhisperEngine(BaseASREngine):
    def __init__(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("faster-whisper is not installed") from exc

        _base_url, _model_name, _api_key, resolved_transport, runtime_options = get_asr_connection()
        use_resolved_local = resolved_transport == "local" or str(runtime_options.get("engine", "")).strip().lower() == "faster_whisper"

        self.model_size = str(runtime_options.get("model_size") or runtime_options.get("model") or ASR_WHISPER_MODEL_SIZE).strip()
        self.device = str(runtime_options.get("device") or ASR_WHISPER_DEVICE).strip()
        self.compute_type = str(runtime_options.get("compute_type") or ASR_WHISPER_COMPUTE_TYPE).strip()
        self.model_path = Path(str(runtime_options.get("model_path") or ASR_WHISPER_MODEL_PATH).strip())
        if not use_resolved_local:
            self.model_size = ASR_WHISPER_MODEL_SIZE
            self.device = ASR_WHISPER_DEVICE
            self.compute_type = ASR_WHISPER_COMPUTE_TYPE
            self.model_path = Path(ASR_WHISPER_MODEL_PATH)

        model_source: str = self.model_size
        offline_mode = os.getenv("HF_HUB_OFFLINE", "0").strip() in {"1", "true", "yes", "on"}
        if self.model_path.exists():
            logger.info(f"Loading faster-whisper model from local path: {self.model_path}")
            model_source = str(self.model_path)
        else:
            if offline_mode:
                raise RuntimeError(
                    "ASR_ENGINE=faster_whisper requires a local model when HF_HUB_OFFLINE is enabled; "
                    f"model path not found: {self.model_path}"
                )
            logger.info(
                "Loading faster-whisper model by size name "
                f"{self.model_size} because local path {self.model_path} was not found"
            )

        self.model = WhisperModel(
            model_source,
            device=self.device,
            compute_type=self.compute_type,
        )
        logger.info(
            "Initialized FasterWhisperEngine: model=%s device=%s compute_type=%s model_path=%s",
            self.model_size,
            self.device,
            self.compute_type,
            self.model_path,
        )

    def transcribe(self, audio_path: Path, language: str | None = None) -> dict[str, Any]:
        logger.info("Starting local faster-whisper transcription: file=%s language=%s", audio_path, language)
        segments, info = self.model.transcribe(str(audio_path), language=language, word_timestamps=False)
        normalized_segments: list[dict[str, Any]] = []
        for segment in segments:
            normalized_segments.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": segment.text.strip(),
                }
            )
        duration = float(info.duration or 0.0)
        if duration <= 0.0 and normalized_segments:
            duration = normalized_segments[-1]["end"]
        logger.info(
            "Local ASR transcription completed: file=%s language=%s segment_count=%s",
            audio_path,
            info.language or language or "unknown",
            len(normalized_segments),
        )
        return {
            "audio": str(audio_path),
            "language": info.language or language or "zh",
            "duration": duration,
            "segments": normalized_segments,
            "backend": {
                "engine": "faster-whisper-local",
                "model": self.model_size,
                "device": self.device,
                "compute_type": self.compute_type,
                "model_path": str(self.model_path),
            },
            "meta": {
                "segment_count": len(normalized_segments),
                "avg_segment_len": (
                    sum(len(segment["text"]) for segment in normalized_segments)
                    / max(1, len(normalized_segments))
                )
                if normalized_segments
                else 0.0,
            },
        }


def _normalize_asr_payload(payload: dict[str, Any], audio_path: Path) -> dict[str, Any]:
    api_url, model_name, _api_key, _transport, _runtime_options = get_asr_connection()
    duration = float(payload.get("duration", 0.0))
    segments: list[dict[str, Any]] = []
    raw_segments = payload.get("segments", [])
    if raw_segments:
        for segment in raw_segments:
            text = (segment.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                {
                    "start": float(segment.get("start") or segment.get("start_time") or 0.0),
                    "end": float(segment.get("end") or segment.get("end_time") or 0.0),
                    "text": text,
                }
            )
    else:
        text = (payload.get("text") or "").strip()
        if text:
            segments.append(
                {
                    "start": 0.0,
                    "end": duration if duration > 0.0 else 10.0,
                    "text": text,
                }
            )

    if segments:
        duration = segments[-1]["end"]

    return {
        "audio": str(audio_path),
        "language": payload.get("language", "zh"),
        "duration": duration,
        "segments": segments,
        "backend": {
            "engine": "qwen3-asr-remote",
            "model": model_name,
            "url": api_url,
        },
        "meta": {"segment_count": len(segments)},
    }


# 全局单例引擎
_engine_instance = None


def get_asr_engine() -> BaseASREngine:
    """
    ASR 加载工厂。根据环境变量 ASR_ENGINE 初始化并返回指定的引擎单例。
    默认返回 QwenASREngine，设置 ASR_ENGINE=faster_whisper 返回 FasterWhisperEngine。
    当前约定使用 ASR_ENGINE=qwen 表示远端 Qwen ASR。
    """
    global _engine_instance
    if _engine_instance is None:
        _base_url, _model_name, _api_key, transport, runtime_options = get_asr_connection()
        backend = ASR_ENGINE.lower()
        if transport == "local" or str(runtime_options.get("engine", "")).strip().lower() == "faster_whisper":
            backend = "faster_whisper"
        logger.info(f"当前环境变量 ASR_ENGINE 值为: {backend}")
        if backend == "faster_whisper":
            logger.info("Using FasterWhisper engine based on environment variable (ASR_ENGINE=faster_whisper).")
            _engine_instance = FasterWhisperEngine()
        else:
            logger.info(f"Using Qwen engine based on environment variable (ASR_ENGINE={backend}).")
            _engine_instance = QwenASREngine()

    return _engine_instance
