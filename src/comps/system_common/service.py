# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import math
import re
import struct
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx

from sqlalchemy import func
from sqlalchemy.orm import Session

from comps.system_common.config import MODEL_CONFIG_ASR_PROBE_AUDIO_PATH
from comps.system_common.model import (
    ModelConfigCurrent,
    ModelConfigRevision,
    ModelConfigScope,
    ModelConnectivityCheck,
)
from comps.system_common.schema import (
    ModelConnectivityProbeResult,
    ModelConfigAdminPublic,
)
from comps.system_common.security import (
    decrypt_api_key,
    derive_secret_key_id,
    encrypt_api_key,
    mask_secret,
)

OPENAI_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
OPENAI_EMBEDDINGS_PATH = "/v1/embeddings"
OPENAI_ASR_PATH = "/v1/audio/transcriptions"
CONNECTIVITY_TIMEOUT_SECONDS = 20.0
EXPECTED_EMBEDDING_DIMENSION = 1024
SUPPORTED_TRANSPORTS = {"http", "local"}
LOCAL_ASR_RUNTIME_OPTION_KEYS = {"engine", "device", "model_path", "compute_type", "model_size"}


@dataclass(frozen=True)
class DraftConnectivityConfig:
    scope: ModelConfigScope
    model: str
    transport: str
    base_url: str | None
    api_key: str | None
    runtime_options: dict[str, object]


def _normalize_base_url(base_url: str | None) -> str:
    if not base_url:
        return ""
    return base_url.rstrip("/")


def _build_openai_compatible_url(base_url: str | None, endpoint_path: str) -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return ""
    if normalized.endswith("/v1") and endpoint_path.startswith("/v1/"):
        return f"{normalized}{endpoint_path[3:]}"
    return f"{normalized}{endpoint_path}"


def _build_auth_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _redact_sensitive_text(message: str, secrets: list[str]) -> str:
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "********")

    redacted = re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1********", redacted)
    redacted = re.sub(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s\"']+", r"\1********", redacted)
    return redacted


def _safe_error_summary(error: Exception, *, secrets: list[str]) -> str:
    summary = _redact_sensitive_text(str(error), secrets)
    return summary[:512]


def _is_scope_configured(current: ModelConfigCurrent, scope: ModelConfigScope) -> bool:
    transport = (current.transport or "http").strip().lower()
    has_model = bool((current.model or "").strip())
    has_base_url = bool((current.base_url or "").strip())
    if scope == ModelConfigScope.ASR:
        if transport == "local":
            return has_model
        return has_model and has_base_url
    return has_model and has_base_url


def _normalize_transport(transport: str | None) -> str:
    candidate = (transport or "http").strip().lower() or "http"
    if candidate not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"不支持的 transport：{transport}")
    return candidate


def _normalize_runtime_options(runtime_options: dict[str, object] | None) -> dict[str, object]:
    if runtime_options is None:
        return {}
    if not isinstance(runtime_options, dict):
        raise ValueError("runtime_options 必须为对象。")
    unknown_keys = set(runtime_options) - LOCAL_ASR_RUNTIME_OPTION_KEYS
    if unknown_keys:
        unknown = ", ".join(sorted(unknown_keys))
        raise ValueError(f"runtime_options 包含不支持的字段：{unknown}")
    return runtime_options


def _serialize_runtime_options(runtime_options: dict[str, object]) -> str | None:
    if not runtime_options:
        return None
    return json.dumps(runtime_options, ensure_ascii=False, sort_keys=True)


def _validate_model_config_inputs(
    *,
    scope: ModelConfigScope,
    model: str,
    transport: str,
    runtime_options: dict[str, object],
) -> None:
    if not model.strip():
        raise ValueError("model 不能为空。")
    if transport == "local" and scope != ModelConfigScope.ASR:
        raise ValueError("仅 ASR 作用域支持 local transport。")
    if transport == "local" and runtime_options.get("engine") not in {None, "faster_whisper"}:
        raise ValueError("当前仅支持 faster_whisper 本地引擎。")


def _validate_test_status_for_upsert(*, last_test_status: str | None) -> str:
    status = (last_test_status or "").strip()
    if not status:
        raise ValueError("保存前必须先完成连通性测试，并在请求中传入 last_test_status。")
    normalized = status.lower()
    if normalized not in {"success", "failed", "timeout", "skipped"}:
        raise ValueError("last_test_status 仅支持：success / failed / timeout / skipped。")
    return status


def _run_local_asr_probe(current: ModelConfigCurrent) -> tuple[int | None, dict[str, object]]:
    runtime_options = current.runtime_options
    return None, {
        "transport": "local",
        "probe_mode": "static_validation_only",
        "engine": runtime_options.get("engine", "faster_whisper"),
        "runtime_options_keys": sorted(runtime_options.keys()),
    }


def _load_asr_fixture_bytes() -> tuple[str, bytes, str]:
    env_fixture = MODEL_CONFIG_ASR_PROBE_AUDIO_PATH
    fixture_candidates = [
        Path(str(Path.cwd())),
        Path(__file__).resolve().parents[3],
    ]

    fixture_override = None
    if env_fixture:
        fixture_override = Path(env_fixture).expanduser().resolve()
    if fixture_override and fixture_override.is_file():
        suffix = fixture_override.suffix.lower()
        media_type = "audio/mpeg" if suffix == ".mp3" else "audio/wav"
        return fixture_override.name, fixture_override.read_bytes(), media_type

    for root in fixture_candidates:
        candidate = root / "scripts/dify-plugins/eap-llm-service/_assets/audio.mp3"
        if candidate.is_file():
            return "audio.mp3", candidate.read_bytes(), "audio/mpeg"

    sample_rate = 16_000
    duration_seconds = 0.25
    frame_count = int(sample_rate * duration_seconds)
    amplitude = 9_000
    buf = BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for idx in range(frame_count):
            sample = int(amplitude * math.sin(2.0 * math.pi * 440.0 * idx / sample_rate))
            wav_file.writeframesraw(struct.pack("<h", sample))
    return "probe.wav", buf.getvalue(), "audio/wav"


def _run_chat_probe(client: httpx.Client, current: ModelConfigCurrent, api_key: str | None) -> tuple[int, dict[str, object]]:
    """
    执行 LLM Chat 模型连通性测试
    
    向模型发送简单的 "ping" 消息，验证：
    1. 服务端点是否可达
    2. API Key 是否有效
    3. 模型是否正常响应
    
    Returns:
        tuple[int, dict]: (延迟毫秒数，响应元数据)
    """
    probe_url = _build_openai_compatible_url(current.base_url, OPENAI_CHAT_COMPLETIONS_PATH)
    if not probe_url:
        raise ValueError("Chat 探测 base_url 未配置。")

    payload = {
        "model": current.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }

    started_at = time.perf_counter()
    response = client.post(probe_url, headers=_build_auth_headers(api_key), json=payload)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    response.raise_for_status()

    body = response.json()
    choices = body.get("choices", []) if isinstance(body, dict) else []
    if not choices:
        raise ValueError("Chat 探测响应不包含选择项。")

    metadata: dict[str, object] = {
        "response_id": body.get("id") if isinstance(body, dict) else None,
    }
    return latency_ms, metadata


def _run_embedding_probe(client: httpx.Client, current: ModelConfigCurrent, api_key: str | None) -> tuple[int, dict[str, object]]:
    """
    执行 Embedding 模型连通性测试
    
    向模型发送简单文本，验证：
    1. 服务端点是否可达
    2. API Key 是否有效
    3. 返回的向量维度是否为预期的 1024 维
    
    Returns:
        tuple[int, dict]: (延迟毫秒数，包含维度信息的元数据)
    """
    probe_url = _build_openai_compatible_url(current.base_url, OPENAI_EMBEDDINGS_PATH)
    if not probe_url:
        raise ValueError("Embedding 探测 base_url 未配置。")

    payload = {
        "model": current.model,
        "input": "ping",
        "dimensions": EXPECTED_EMBEDDING_DIMENSION,
    }

    started_at = time.perf_counter()
    response = client.post(probe_url, headers=_build_auth_headers(api_key), json=payload)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    response.raise_for_status()

    body = response.json()
    data = body.get("data", []) if isinstance(body, dict) else []
    if not data:
        raise ValueError("Embedding 探测响应不包含数据。")

    embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
    if not isinstance(embedding, list):
        raise ValueError("Embedding 探测响应缺少向量数据。")

    observed_dimension = len(embedding)
    if observed_dimension != EXPECTED_EMBEDDING_DIMENSION:
        raise ValueError(
            "Embedding 探测维度不匹配："
            f"预期={EXPECTED_EMBEDDING_DIMENSION}, 实际={observed_dimension}。"
        )

    metadata: dict[str, object] = {
        "expected_dimension": EXPECTED_EMBEDDING_DIMENSION,
        "observed_dimension": observed_dimension,
    }
    return latency_ms, metadata


def _run_asr_probe(client: httpx.Client, current: ModelConfigCurrent, api_key: str | None) -> tuple[int, dict[str, object]]:
    """
    执行 ASR（语音识别）模型连通性测试
    
    播放预置的测试音频文件，验证：
    1. 服务端点是否可达
    2. API Key 是否有效
    3. 是否能正确识别音频内容并返回文本
    
    Returns:
        tuple[int, dict]: (延迟毫秒数，包含识别文本预览的元数据)
    """
    probe_url = _build_openai_compatible_url(current.base_url, OPENAI_ASR_PATH)
    if not probe_url:
        raise ValueError("ASR 探测 base_url 未配置。")

    fixture_name, fixture_bytes, media_type = _load_asr_fixture_bytes()
    files = {"file": (fixture_name, fixture_bytes, media_type)}
    data = {"model": current.model}

    started_at = time.perf_counter()
    response = client.post(probe_url, headers=_build_auth_headers(api_key), data=data, files=files)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    response.raise_for_status()

    body = response.json()
    text = (body.get("text") if isinstance(body, dict) else "") or ""
    transcript = str(text).strip()
    if not transcript:
        raise ValueError("ASR 探测响应无有效文本识别结果。")

    metadata: dict[str, object] = {
        "fixture": fixture_name,
        "transcript_preview": transcript[:64],
    }
    return latency_ms, metadata


def _persist_connectivity_check(
    db: Session,
    *,
    scope: ModelConfigScope,
    provider: str | None,
    model: str,
    base_url: str | None,
    version: int,
    trigger_type: str,
    status: str,
    latency_ms: int | None,
    summary: str | None,
    metadata: dict[str, object] | None,
    checked_by: str,
    current: ModelConfigCurrent | None,
) -> ModelConnectivityProbeResult:
    """
    持久化连通性测试结果到数据库
    
    功能：
    1. 创建测试记录存入 model_connectivity_check 表
    2. 更新当前配置的最近测试状态、时间和错误信息
    3. 返回测试结果对象供 API 使用
    
    Args:
        db: 数据库会话
        scope: 配置作用域
        provider: 服务提供商
        model: 模型名称
        base_url: 服务端点
        version: 配置版本号
        trigger_type: 触发方式（manual/auto）
        status: 测试状态（success/failed/timeout/skipped）
        latency_ms: 请求延迟（毫秒）
        summary: 错误摘要（已脱敏）
        metadata: 测试元数据 JSON
        checked_by: 执行测试的用户
        current: 当前配置记录（可选）
    
    Returns:
        ModelConnectivityProbeResult: 测试结果对象
    """
    now = datetime.now(timezone.utc)
    summary_safe = summary[:512] if summary else None
    metadata_payload = json.dumps(metadata, ensure_ascii=False) if metadata else None
    check = ModelConnectivityCheck(
        scope=scope.value,
        provider=provider,
        model=model,
        base_url=base_url,
        version=version,
        trigger_type=trigger_type,
        status=status,
        latency_ms=latency_ms,
        error_message=summary_safe,
        metadata_json=metadata_payload,
        checked_by=checked_by,
        checked_at=now,
    )
    db.add(check)

    if current is not None:
        current.last_test_status = status
        current.last_tested_at = now
        current.last_test_error = summary_safe

    db.commit()
    db.refresh(check)

    return ModelConnectivityProbeResult(
        scope=scope,
        status=status,
        version=version,
        is_configured=current is not None and _is_scope_configured(current, scope),
        latency_ms=latency_ms,
        summary=summary_safe,
        check_id=check.id,
    )


def run_model_connectivity_probe(
    db: Session,
    scope: ModelConfigScope,
    checked_by: str,
    *,
    trigger_type: str = "manual",
) -> ModelConnectivityProbeResult:
    """
    执行单个作用域的模型连通性测试
    
    测试流程：
    1. 查询当前配置，未配置则标记为 skipped/failed
    2. 检查配置完整性（model + base_url 必填）
    3. 解密 API Key（如果有）
    4. 根据 scope 类型调用对应的探测函数（chat/embedding/asr）
    5. 捕获超时和异常，记录错误日志（自动脱敏）
    6. 持久化测试结果
    
    Args:
        db: 数据库会话
        scope: 配置作用域
        checked_by: 执行测试的用户
        trigger_type: 触发方式，默认 "manual"（手动）
    
    Returns:
        ModelConnectivityProbeResult: 测试结果
    """
    current = db.query(ModelConfigCurrent).filter(ModelConfigCurrent.scope == scope.value).first()

    if current is None:
        missing_status = "skipped" if scope == ModelConfigScope.ASR else "failed"
        missing_summary = "该作用域的模型配置未设置。"
        return _persist_connectivity_check(
            db,
            scope=scope,
            provider="unconfigured",
            model="",
            base_url=None,
            version=0,
            trigger_type=trigger_type,
            status=missing_status,
            latency_ms=None,
            summary=missing_summary,
            metadata={"is_configured": False},
            checked_by=checked_by,
            current=None,
        )

    configured = _is_scope_configured(current, scope)
    if not configured and scope == ModelConfigScope.ASR:
        return _persist_connectivity_check(
            db,
            scope=scope,
            provider=current.provider,
            model=current.model,
            base_url=current.base_url,
            version=current.version,
            trigger_type=trigger_type,
            status="skipped",
            latency_ms=None,
            summary="ASR 未配置或已禁用。",
            metadata={"is_configured": False},
            checked_by=checked_by,
            current=current,
        )

    if not configured:
        return _persist_connectivity_check(
            db,
            scope=scope,
            provider=current.provider,
            model=current.model,
            base_url=current.base_url,
            version=current.version,
            trigger_type=trigger_type,
            status="failed",
            latency_ms=None,
            summary="模型配置不完整，无法进行连通性测试。",
            metadata={"is_configured": False},
            checked_by=checked_by,
            current=current,
        )

    api_key_plaintext: str | None = None
    if current.secret_encrypted:
        decrypted = decrypt_api_key(current.secret_encrypted)
        api_key_plaintext = decrypted.get_secret_value() if decrypted else None

    secrets_for_redaction: list[str] = [api_key_plaintext] if api_key_plaintext else []

    status = "success"
    latency_ms: int | None = None
    summary: str | None = None
    metadata: dict[str, object] | None = {"is_configured": True}

    try:
        if scope == ModelConfigScope.ASR and (current.transport or "http").strip().lower() == "local":
            latency_ms, probe_metadata = _run_local_asr_probe(current)
            metadata.update(probe_metadata)
            summary = "本地 ASR 配置校验通过（未执行远程 HTTP 连通性测试）。"
        else:
            with httpx.Client(timeout=CONNECTIVITY_TIMEOUT_SECONDS) as client:
                if scope in {ModelConfigScope.DATAPREP_LLM, ModelConfigScope.SMART_PRACTICE_LLM}:
                    latency_ms, probe_metadata = _run_chat_probe(client, current, api_key_plaintext)
                elif scope == ModelConfigScope.EMBEDDING:
                    latency_ms, probe_metadata = _run_embedding_probe(client, current, api_key_plaintext)
                else:
                    latency_ms, probe_metadata = _run_asr_probe(client, current, api_key_plaintext)
                metadata.update(probe_metadata)
    except httpx.TimeoutException as exc:
        status = "timeout"
        summary = _safe_error_summary(exc, secrets=secrets_for_redaction)
    except Exception as exc:  # noqa: BLE001 - normalize all probe failures
        status = "failed"
        summary = _safe_error_summary(exc, secrets=secrets_for_redaction)

    return _persist_connectivity_check(
        db,
        scope=scope,
        provider=current.provider,
        model=current.model,
        base_url=current.base_url,
        version=current.version,
        trigger_type=trigger_type,
        status=status,
        latency_ms=latency_ms,
        summary=summary,
        metadata=metadata,
        checked_by=checked_by,
        current=current,
    )


def run_all_model_connectivity_probes(
    db: Session,
    checked_by: str,
    *,
    trigger_type: str = "manual",
) -> list[ModelConnectivityProbeResult]:
    return [
        run_model_connectivity_probe(db, scope=scope, checked_by=checked_by, trigger_type=trigger_type)
        for scope in ModelConfigScope
    ]


def run_model_connectivity_probe_for_draft(
    scope: ModelConfigScope,
    *,
    model: str,
    transport: str,
    base_url: str | None,
    api_key: str | None,
    runtime_options: dict[str, object] | None,
) -> ModelConnectivityProbeResult:
    normalized_transport = _normalize_transport(transport)
    normalized_runtime_options = _normalize_runtime_options(runtime_options)
    _validate_model_config_inputs(
        scope=scope,
        model=model,
        transport=normalized_transport,
        runtime_options=normalized_runtime_options,
    )

    has_model = bool((model or "").strip())
    has_base_url = bool((base_url or "").strip())
    if scope == ModelConfigScope.ASR:
        is_configured = has_model if normalized_transport == "local" else (has_model and has_base_url)
    else:
        is_configured = has_model and has_base_url
    if scope == ModelConfigScope.ASR and not is_configured:
        return ModelConnectivityProbeResult(
            scope=scope,
            status="skipped",
            version=0,
            is_configured=False,
            summary="ASR 未配置或已禁用。",
            check_id=None,
        )
    if not is_configured:
        return ModelConnectivityProbeResult(
            scope=scope,
            status="failed",
            version=0,
            is_configured=False,
            summary="模型配置不完整，无法进行连通性测试。",
            check_id=None,
        )

    current = ModelConfigCurrent(
        scope=scope.value,
        provider=None,
        model=model,
        transport=normalized_transport,
        base_url=base_url,
        runtime_options_json=_serialize_runtime_options(normalized_runtime_options),
        secret_encrypted=None,
        secret_key_id=None,
        version=0,
        last_test_status=None,
        last_tested_at=None,
        last_test_error=None,
        activated_by=None,
        activated_at=None,
        is_active=True,
    )

    status = "success"
    latency_ms: int | None = None
    summary: str | None = None
    secrets_for_redaction: list[str] = [api_key] if api_key else []

    try:
        if scope == ModelConfigScope.ASR and normalized_transport == "local":
            latency_ms, _ = _run_local_asr_probe(current)
            summary = "本地 ASR 配置校验通过（未执行远程 HTTP 连通性测试）。"
        else:
            with httpx.Client(timeout=CONNECTIVITY_TIMEOUT_SECONDS) as client:
                if scope in {ModelConfigScope.DATAPREP_LLM, ModelConfigScope.SMART_PRACTICE_LLM}:
                    latency_ms, _ = _run_chat_probe(client, current, api_key)
                elif scope == ModelConfigScope.EMBEDDING:
                    latency_ms, _ = _run_embedding_probe(client, current, api_key)
                else:
                    latency_ms, _ = _run_asr_probe(client, current, api_key)
    except httpx.TimeoutException as exc:
        status = "timeout"
        summary = _safe_error_summary(exc, secrets=secrets_for_redaction)
    except Exception as exc:  # noqa: BLE001 - normalize all probe failures
        status = "failed"
        summary = _safe_error_summary(exc, secrets=secrets_for_redaction)

    return ModelConnectivityProbeResult(
        scope=scope,
        status=status,
        version=0,
        is_configured=True,
        latency_ms=latency_ms,
        summary=summary,
        check_id=None,
    )


def run_all_model_connectivity_probes_with_draft(
    db: Session,
    checked_by: str,
    draft_configs: list[DraftConnectivityConfig],
    *,
    trigger_type: str = "manual",
) -> list[ModelConnectivityProbeResult]:
    _ = db
    _ = checked_by
    _ = trigger_type
    results: list[ModelConnectivityProbeResult] = []
    for draft in draft_configs:
        results.append(
            run_model_connectivity_probe_for_draft(
                draft.scope,
                model=draft.model,
                transport=draft.transport,
                base_url=draft.base_url,
                api_key=draft.api_key,
                runtime_options=draft.runtime_options,
            )
        )
    return results


def to_admin_public_model_config(
    current: ModelConfigCurrent,
    *,
    reveal_api_key: bool = True,
) -> ModelConfigAdminPublic:
    public = ModelConfigAdminPublic.model_validate(current)
    try:
        scope_enum = ModelConfigScope(current.scope)
    except ValueError:
        scope_enum = None
    public.is_configured = _is_scope_configured(current, scope_enum) if scope_enum else bool((current.model or "").strip())
    if current.secret_encrypted:
        try:
            secret = decrypt_api_key(current.secret_encrypted)
            public.api_key_masked = mask_secret(secret)
            if reveal_api_key:
                public.api_key_plain = secret.get_secret_value()
        except Exception:
            public.api_key_masked = "********"
            public.api_key_plain = None
    return public


def list_model_configs(db: Session, *, reveal_api_key: bool = True) -> list[ModelConfigAdminPublic]:
    configs = db.query(ModelConfigCurrent).all()
    return [to_admin_public_model_config(c, reveal_api_key=reveal_api_key) for c in configs]


def upsert_model_config(
    db: Session,
    scope: ModelConfigScope,
    model: str,
    transport: str,
    base_url: str | None,
    api_key: str | None,
    runtime_options: dict[str, object] | None,
    last_test_status: str | None,
    actor: str,
    auto_commit: bool = True,
) -> ModelConfigAdminPublic:
    """
    新增或更新模型配置（核心业务逻辑）
    
    关键特性：
    1. **版本控制**: 每次更新前自动将当前配置保存为历史版本
    2. **加密存储**: API Key 使用 Fernet 算法加密后入库
    3. **版本号自增**: 首次创建 version=1，每次更新 +1
    4. **重置测试状态**: 更新后清空上次测试结果，需重新测试
    
    Args:
        db: 数据库会话
        scope: 配置作用域
        model: 模型名称（如 "gpt-4", "qwen-turbo"）
        base_url: API 端点地址（可选）
        api_key: API 密钥（明文传入，加密存储）
        actor: 操作者用户名
    
    Returns:
        ModelConfigAdminPublic: 更新后的配置对象（含脱敏的 API Key）
    """
    current = (
        db.query(ModelConfigCurrent)
        .filter(ModelConfigCurrent.scope == scope.value)
        .with_for_update()
        .first()
    )
    normalized_transport = _normalize_transport(transport)
    normalized_runtime_options = _normalize_runtime_options(runtime_options)
    validated_status = _validate_test_status_for_upsert(last_test_status=last_test_status)
    _validate_model_config_inputs(
        scope=scope,
        model=model,
        transport=normalized_transport,
        runtime_options=normalized_runtime_options,
    )

    next_version: int | None = None
    if current:
        current_version = int(current.version)
        latest_revision_version = (
            db.query(func.max(ModelConfigRevision.version))
            .filter(ModelConfigRevision.scope == scope.value)
            .scalar()
        )
        existing_revision = (
            db.query(ModelConfigRevision.id)
            .filter(ModelConfigRevision.scope == scope.value, ModelConfigRevision.version == current_version)
            .first()
        )
        if existing_revision is None:
            revision = create_model_config_revision(current, changed_by=actor, change_reason="配置更新")
            db.add(revision)
        next_version = _calculate_next_current_version(
            current_version=current_version,
            latest_revision_version=latest_revision_version,
        )

    secret_encrypted = encrypt_api_key(api_key) if api_key else (current.secret_encrypted if current else None)
    secret_key_id = derive_secret_key_id() if api_key else (current.secret_key_id if current else None)

    updated = upsert_current_model_config(
        db,
        current=current,
        scope=scope,
        provider=current.provider if current else None,
        model=model,
        transport=normalized_transport,
        base_url=base_url,
        runtime_options_json=_serialize_runtime_options(normalized_runtime_options),
        secret_encrypted=secret_encrypted,
        secret_key_id=secret_key_id,
        actor=actor,
        next_version=next_version,
    )

    updated.last_test_status = validated_status
    updated.last_tested_at = datetime.now(timezone.utc)
    updated.last_test_error = None

    if auto_commit:
        db.commit()
    else:
        db.flush()
    db.refresh(updated)
    return to_admin_public_model_config(updated)


def create_model_config_revision(
    current: ModelConfigCurrent,
    changed_by: str | None = None,
    change_reason: str | None = None,
) -> ModelConfigRevision:
    return ModelConfigRevision(
        scope=current.scope,
        provider=current.provider,
        model=current.model,
        transport=current.transport,
        base_url=current.base_url,
        runtime_options_json=current.runtime_options_json,
        secret_encrypted=current.secret_encrypted,
        secret_key_id=current.secret_key_id,
        version=current.version,
        last_test_status=current.last_test_status,
        last_tested_at=current.last_tested_at,
        last_test_error=current.last_test_error,
        activated_by=current.activated_by,
        activated_at=current.activated_at,
        changed_by=changed_by,
        change_reason=change_reason,
    )


def _calculate_next_current_version(*, current_version: int, latest_revision_version: int | None) -> int:
    baseline = current_version + 1
    if latest_revision_version is None:
        return baseline
    return max(baseline, int(latest_revision_version) + 1)


def upsert_current_model_config(
    db: Session,
    *,
    current: ModelConfigCurrent | None,
    scope: ModelConfigScope,
    provider: str | None,
    model: str,
    transport: str,
    base_url: str | None,
    runtime_options_json: str | None,
    secret_encrypted: str | None,
    secret_key_id: str | None,
    actor: str | None,
    next_version: int | None = None,
    activated_at: datetime | None = None,
) -> ModelConfigCurrent:
    if current is None:
        current = (
            db.query(ModelConfigCurrent)
            .filter(ModelConfigCurrent.scope == scope.value)
            .with_for_update()
            .first()
        )
    now = activated_at or datetime.now(timezone.utc)

    if current is None:
        current = ModelConfigCurrent(
            scope=scope.value,
            provider=provider,
            model=model,
            transport=transport,
            base_url=base_url,
            runtime_options_json=runtime_options_json,
            secret_encrypted=secret_encrypted,
            secret_key_id=secret_key_id,
            version=1,
            activated_by=actor,
            activated_at=now,
            is_active=True,
        )
        db.add(current)
    else:
        current.provider = provider
        current.model = model
        current.transport = transport
        current.base_url = base_url
        current.runtime_options_json = runtime_options_json
        current.secret_encrypted = secret_encrypted
        current.secret_key_id = secret_key_id
        current.version = next_version if next_version is not None else int(current.version) + 1
        current.activated_by = actor
        current.activated_at = now
        current.is_active = True

    db.flush()
    return current
