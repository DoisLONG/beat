# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Literal, Protocol

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .model import ModelConfigCurrent, ModelConfigScope
from .security import SecretDecryptionError, decrypt_api_key


class ConfigResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedModelConfig:
    scope: ModelConfigScope
    provider: str | None
    model: str
    base_url: str | None
    api_key: SecretStr | None
    version: int
    source: Literal["db", "env"]
    transport: Literal["http", "local"] = "http"
    runtime_options: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _CacheEntry:
    config: ResolvedModelConfig
    expires_at: float


class ConfigResolverContract(Protocol):
    def resolve(self, scope: ModelConfigScope, *, refresh: bool = False) -> ResolvedModelConfig:
        ...


class ConfigResolver:
    """
    模型配置解析器（支持缓存和降级）
    
    核心设计理念：
    1. **优先级**: 数据库配置 > 环境变量
    2. **缓存机制**: 避免频繁查询数据库，默认 TTL=300 秒
    3. **优雅降级**: 数据库不可用时自动 fallback 到环境变量
    4. **版本校验**: 缓存期内定期检查数据库版本是否变化
    
    Attributes:
        _session_factory: 数据库会话工厂
        _ttl_seconds: 缓存过期时间（秒）
        _time_provider: 时间获取函数（用于单元测试）
        _cache: 内存缓存字典
    """
    _session_factory: Callable[[], Session]
    _ttl_seconds: int
    _time_provider: Callable[[], float]
    _cache: dict[ModelConfigScope, _CacheEntry]

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        ttl_seconds: int = 300,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._session_factory = session_factory
        self._ttl_seconds = ttl_seconds
        self._time_provider = time_provider or time.monotonic
        self._cache = {}

    def resolve(self, scope: ModelConfigScope, *, refresh: bool = False) -> ResolvedModelConfig:
        """
        解析指定作用域的模型配置（带缓存）
        
        解析逻辑：
        1. 检查缓存是否命中且未过期 → 直接返回
        2. 如果是 DB 来源配置，检查版本是否变化 → 未变则刷新缓存
        3. 重新加载配置（优先 DB，失败则 ENV）→ 更新缓存
        
        Args:
            scope: 配置作用域
            refresh: 是否强制刷新（忽略缓存）
        
        Returns:
            ResolvedModelConfig: 解析后的配置对象
        """
        now = self._time_provider()
        cached = self._cache.get(scope)

        if not refresh and cached is not None and now < cached.expires_at:
            return cached.config

        if not refresh and cached is not None and cached.config.source == "db":
            latest_version = self._try_fetch_db_version(scope)
            if latest_version is not None and latest_version == cached.config.version:
                self._cache[scope] = _CacheEntry(config=cached.config, expires_at=now + self._ttl_seconds)
                return cached.config

        resolved = self._load_config(scope)
        self._cache[scope] = _CacheEntry(config=resolved, expires_at=now + self._ttl_seconds)
        return resolved

    def refresh(self, scope: ModelConfigScope) -> ResolvedModelConfig:
        return self.resolve(scope, refresh=True)

    def invalidate(self, scope: ModelConfigScope | None = None) -> None:
        if scope is None:
            self._cache.clear()
            return
        _ = self._cache.pop(scope, None)

    def _load_config(self, scope: ModelConfigScope) -> ResolvedModelConfig:
        """
        加载配置的核心方法（DB 优先策略）
        
        加载流程：
        1. 尝试从数据库查询激活的配置
        2. 如果 DB 查询失败或无记录 → 使用环境变量
        3. 解密 API Key（如果配置了加密密钥）
        4. 返回完整的配置对象
        
        异常处理：
        - 数据库连接失败、表不存在等异常会被捕获并降级到环境变量
        - 解密失败会抛出 ConfigResolutionError 阻止启动
        
        Returns:
            ResolvedModelConfig: 配置对象（source 标记为 "db" 或 "env"）
        """
        try:
            record = self._fetch_db_record(scope)
        except Exception:  # noqa: BLE001 - degrade to env if system_common DB path unavailable
            return self._load_env_config(scope)

        if record is None:
            return self._load_env_config(scope)

        if getattr(record, "last_test_status", None) != "success":
            return self._load_env_config(scope)

        secret = None
        if record.secret_encrypted:
            try:
                secret = decrypt_api_key(record.secret_encrypted)
            except SecretDecryptionError as exc:
                raise ConfigResolutionError("模型配置密钥解密失败。") from exc

        return ResolvedModelConfig(
            scope=scope,
            provider=record.provider,
            model=record.model,
            transport=(record.transport or "http"),
            base_url=record.base_url,
            api_key=secret,
            runtime_options=record.runtime_options,
            version=record.version,
            source="db",
        )

    def _try_fetch_db_version(self, scope: ModelConfigScope) -> int | None:
        """
        安全地获取数据库配置版本（不抛异常）
        
        用途：在缓存校验时快速判断配置是否已更新
        如果数据库不可用，返回 None 触发环境变量降级
        
        Returns:
            int | None: 当前激活的版本号，失败返回 None
        """
        try:
            return self._fetch_db_version(scope)
        except Exception:  # noqa: BLE001 - unavailable DB should not block env fallback
            return None

    def _fetch_db_record(self, scope: ModelConfigScope) -> ModelConfigCurrent | None:
        session = self._session_factory()
        try:
            stmt = (
                select(ModelConfigCurrent)
                .where(ModelConfigCurrent.scope == scope.value)
                .where(ModelConfigCurrent.is_active.is_(True))
            )
            return session.execute(stmt).scalar_one_or_none()
        finally:
            session.close()

    def _fetch_db_version(self, scope: ModelConfigScope) -> int | None:
        session = self._session_factory()
        try:
            stmt = (
                select(ModelConfigCurrent.version)
                .where(ModelConfigCurrent.scope == scope.value)
                .where(ModelConfigCurrent.is_active.is_(True))
            )
            return session.execute(stmt).scalar_one_or_none()
        finally:
            session.close()

    def _load_env_config(self, scope: ModelConfigScope) -> ResolvedModelConfig:
        """
        从环境变量加载配置（降级方案）
        
        环境变量映射关系：
        ┌─────────────────────┬──────────────┬─────────────┬──────────────┬─────────────┐
        │ Scope               │ Provider     │ Model       │ Endpoint     │ API Key     │
        ├─────────────────────┼──────────────┼─────────────┼──────────────┼─────────────┤
        │ DATAPREP_LLM        │ DATAPREP_    │ DATAPREP_   │ DATAPREP_    │ DATAPREP_   │
        │                     │ LLM_PROVIDER │ LLM_MODEL   │ LLM_ENDPOINT │ LLM_API_KEY │
        ├─────────────────────┼──────────────┼─────────────┼──────────────┼─────────────┤
        │ SMART_PRACTICE_LLM  │ SMART_       │ SMART_      │ SMART_       │ SMART_      │
        │                     │ PRACTICE_    │ PRACTICE_   │ PRACTICE_    │ PRACTICE_   │
        │                     │ LLM_PROVIDER │ LLM_MODEL   │ LLM_ENDPOINT │ LLM_API_KEY │
        ├─────────────────────┼──────────────┼─────────────┼──────────────┼─────────────┤
        │ EMBEDDING           │ EMBEDDING_   │ BAILIAN_    │ BAILIAN_     │ BAILIAN_    │
        │                     │ PROVIDER     │ EMBEDDING_  │ EMBEDDING_   │ EMBEDDING_  │
        │                     │              │ MODEL       │ ENDPOINT     │ API_KEY     │
        ├─────────────────────┼──────────────┼─────────────┼──────────────┼─────────────┤
        │ ASR                 │ ASR_         │ ASR_        │ ASR_         │ ASR_        │
        │                     │ PROVIDER     │ MODEL       │ ENDPOINT     │ API_KEY     │
        └─────────────────────┴──────────────┴─────────────┴──────────────┴─────────────┘
        
        默认值策略：
        - 如果环境变量未设置，使用预定义的默认值（见代码中的 default_map）
        - version 固定为 0（表示来自环境变量）
        - source 标记为 "env"
        
        Returns:
            ResolvedModelConfig: 从环境变量解析的配置对象
        """
        env_map: dict[ModelConfigScope, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
            ModelConfigScope.DATAPREP_LLM: (
                ("DATAPREP_LLM_PROVIDER",),
                ("DATAPREP_LLM_MODEL",),
                ("DATAPREP_LLM_ENDPOINT",),
                ("DATAPREP_LLM_API_KEY",),
            ),
            ModelConfigScope.SMART_PRACTICE_LLM: (
                ("SMART_PRACTICE_LLM_PROVIDER",),
                ("SMART_PRACTICE_LLM_MODEL",),
                ("SMART_PRACTICE_LLM_ENDPOINT",),
                ("SMART_PRACTICE_LLM_API_KEY",),
            ),
            ModelConfigScope.EMBEDDING: (
                ("EMBEDDING_PROVIDER",),
                ("BAILIAN_EMBEDDING_MODEL",),
                ("BAILIAN_EMBEDDING_ENDPOINT",),
                ("BAILIAN_EMBEDDING_API_KEY",),
            ),
            ModelConfigScope.ASR: (
                ("ASR_PROVIDER",),
                ("ASR_MODEL",),
                ("ASR_ENDPOINT",),
                ("ASR_API_KEY",),
            ),
        }
        provider_envs, model_envs, endpoint_envs, secret_envs = env_map[scope]

        provider_default_map: dict[ModelConfigScope, str] = {
            ModelConfigScope.DATAPREP_LLM: "dashscope",
            ModelConfigScope.SMART_PRACTICE_LLM: "dashscope",
            ModelConfigScope.EMBEDDING: "env",
            ModelConfigScope.ASR: "env",
        }
        model_default_map: dict[ModelConfigScope, str] = {
            ModelConfigScope.DATAPREP_LLM: "Qwen/Qwen3-32B",
            ModelConfigScope.SMART_PRACTICE_LLM: "qwen-turbo",
            ModelConfigScope.EMBEDDING: "text-embedding-v4",
            ModelConfigScope.ASR: "",
        }
        endpoint_default_map: dict[ModelConfigScope, str] = {
            ModelConfigScope.DATAPREP_LLM: "",
            ModelConfigScope.SMART_PRACTICE_LLM: "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ModelConfigScope.EMBEDDING: "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ModelConfigScope.ASR: "",
        }
        secret_default_map: dict[ModelConfigScope, str] = {
            ModelConfigScope.DATAPREP_LLM: "your-key",
            ModelConfigScope.SMART_PRACTICE_LLM: "",
            ModelConfigScope.EMBEDDING: "",
            ModelConfigScope.ASR: "",
        }

        transport_env_map: dict[ModelConfigScope, str] = {
            ModelConfigScope.DATAPREP_LLM: "DATAPREP_LLM_TRANSPORT",
            ModelConfigScope.SMART_PRACTICE_LLM: "TRAIN_LLM_TRANSPORT",
            ModelConfigScope.EMBEDDING: "EMBEDDING_TRANSPORT",
            ModelConfigScope.ASR: "ASR_TRANSPORT",
        }
        runtime_options_env_map: dict[ModelConfigScope, str] = {
            ModelConfigScope.DATAPREP_LLM: "DATAPREP_LLM_RUNTIME_OPTIONS_JSON",
            ModelConfigScope.SMART_PRACTICE_LLM: "TRAIN_LLM_RUNTIME_OPTIONS_JSON",
            ModelConfigScope.EMBEDDING: "EMBEDDING_RUNTIME_OPTIONS_JSON",
            ModelConfigScope.ASR: "ASR_RUNTIME_OPTIONS_JSON",
        }

        transport_raw = os.getenv(transport_env_map[scope], "http").strip().lower() or "http"
        transport: Literal["http", "local"] = "local" if transport_raw == "local" else "http"
        if scope != ModelConfigScope.ASR:
            transport = "http"
        runtime_options_raw = os.getenv(runtime_options_env_map[scope], "").strip()
        runtime_options: dict[str, object] = {}
        if runtime_options_raw:
            try:
                payload = json.loads(runtime_options_raw)
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                runtime_options = payload

        secret = self._read_env_aliases(secret_envs, secret_default_map[scope])
        return ResolvedModelConfig(
            scope=scope,
            provider=self._read_env_aliases(provider_envs, provider_default_map[scope]),
            model=self._read_env_aliases(model_envs, model_default_map[scope]),
            transport=transport,
            base_url=self._read_env_aliases(endpoint_envs, endpoint_default_map[scope]),
            api_key=SecretStr(secret) if secret else None,
            runtime_options=runtime_options,
            version=0,
            source="env",
        )

    @staticmethod
    def _read_env_aliases(names: tuple[str, ...], default: str) -> str:
        for name in names:
            value = os.getenv(name)
            if value is not None and value != "":
                return value
        return default


@lru_cache(maxsize=1)
def get_cached_config_resolver() -> ConfigResolverContract:
    return ConfigResolver(session_factory=SessionLocal, ttl_seconds=300)
