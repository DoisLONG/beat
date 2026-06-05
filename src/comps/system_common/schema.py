# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from .model import ModelConfigScope


class ModelConfigUpsertRequest(BaseModel):
    """
    模型配置新增/更新请求体
    
    用于 API 接收用户提交的配置信息
    注意：api_key 为可选字段，允许仅更新其他配置而不修改密钥
    """
    model: str
    transport: str = "http"
    base_url: str | None = None
    api_key: str | None = None
    runtime_options: dict[str, Any] | None = None
    last_test_status: str | None = None


class ModelConfigScopedUpsertRequest(ModelConfigUpsertRequest):
    scope: ModelConfigScope


class ModelConfigCurrentPublic(BaseModel):
    """
    对外公开的模型配置响应（不含敏感信息）
    
    与内部模型的区别：
    - 排除 secret_encrypted 和 secret_key_id 等敏感字段
    - 用于前端展示和普通 API 响应
    """
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: int
    scope: ModelConfigScope
    provider: str | None
    model: str
    transport: str = "http"
    base_url: str | None = None
    runtime_options: dict[str, Any] = Field(default_factory=dict)
    version: int
    last_test_status: str | None = None
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    activated_by: str | None = None
    activated_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ModelConfigAdminPublic(ModelConfigCurrentPublic):
    """
    管理员专用的配置响应模型
    
    在 Public 基础上增加：
    - api_key_masked: 脱敏后的 API Key（如 "sk***********yz"）
    
    仅用于管理员界面，普通用户不应看到此信息
    """
    api_key_masked: str | None = None
    api_key_plain: str | None = None
    is_configured: bool = False


class ModelConnectivityProbeResult(BaseModel):
    """
    连通性测试执行结果（即时返回）
    
    用于测试 API 的响应结构：
    - check_id: 测试记录 ID（用于后续查询详细报告）
    - summary: 测试结果摘要（成功消息或错误简述）
    - latency_ms: 请求延迟（性能指标）
    
    这是单次测试的即时结果，不等价于数据库中的完整测试记录
    """
    scope: ModelConfigScope
    status: str
    version: int = 0
    is_configured: bool = False
    latency_ms: int | None = None
    summary: str | None = None
    check_id: int | None = None
