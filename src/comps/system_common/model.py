# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ModelConfigScope(str, Enum):
    DATAPREP_LLM = "dataprep_llm"
    SMART_PRACTICE_LLM = "smart_practice_llm"
    EMBEDDING = "embedding"
    ASR = "asr"

    @classmethod
    def _missing_(cls, value: str) -> "ModelConfigScope | None":
        """
        支持大小写不敏感的枚举值匹配

        功能：
        - 当传入大写、小写或混合大小写时，自动转换为小写匹配
        - 例如："EMBEDDING"、"Embedding"、"embedding" 都能匹配到 EMBEDDING

        Args:
            value: 输入的字符串值

        Returns:
            ModelConfigScope | None: 匹配的枚举值或 None
        """
        value_lower = value.lower()
        for member in cls:
            if member.value.lower() == value_lower:
                return member
        return None


SCOPE_CHECK_SQL = "scope IN ('dataprep_llm', 'smart_practice_llm', 'embedding', 'asr')"
TRANSPORT_CHECK_SQL = "transport IN ('http', 'local')"


class ModelConfigCurrent(Base):
    """
    当前激活的模型配置表（每个 scope 仅一条记录）
    
    用途：
    - 存储各业务场景正在使用的模型配置
    - 包含完整的连接信息、测试状态和审计字段
    - 通过 version 字段实现乐观锁和版本追踪
    
    关键字段说明：
    - scope: 配置作用域（唯一索引，确保每个 scope 只有一条记录）
    - provider: 服务提供商（如 "openai", "qwen", "azure"）
    - model: 具体模型名称（如 "gpt-4", "qwen-turbo"）
    - base_url: API 端点地址（支持自定义部署）
    - secret_encrypted: 加密存储的 API Key（不保存明文）
    - last_test_status: 最近连通性测试结果（success/failed/timeout/skipped）
    - is_active: 是否激活（用于软删除或临时禁用）
    
    约束条件：
    - uq_model_config_current_scope: scope 唯一性约束
    - ck_model_config_current_scope: scope 值必须在枚举范围内
    - ck_model_config_current_is_active: is_active 只能是 0 或 1
    """
    __tablename__: str = "sp_model_config_current"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="全局模型配置作用域")
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="模型服务提供商")
    model: Mapped[str] = mapped_column(String(256), nullable=False, comment="模型名称")
    transport: Mapped[str] = mapped_column(String(16), nullable=False, default="http", comment="模型接入方式")
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="模型服务地址")
    runtime_options_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="本地运行时配置JSON")
    secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加密后的密钥，不保存明文")
    secret_key_id: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="密钥管理系统标识")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="配置版本")
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="最近连通性测试状态")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近连通性测试时间")
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近测试错误")
    activated_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="激活操作者")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="激活时间")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, comment="是否当前激活")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    @property
    def runtime_options(self) -> dict[str, object]:
        if not self.runtime_options_json:
            return {}
        try:
            payload = json.loads(self.runtime_options_json)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    __table_args__: tuple[UniqueConstraint, CheckConstraint, CheckConstraint, CheckConstraint] = (
        UniqueConstraint("scope", name="uq_model_config_current_scope"),
        CheckConstraint(SCOPE_CHECK_SQL, name="ck_model_config_current_scope"),
        CheckConstraint(TRANSPORT_CHECK_SQL, name="ck_model_config_current_transport"),
        CheckConstraint("is_active IN (0, 1)", name="ck_model_config_current_is_active"),
    )


class ModelConfigRevision(Base):
    """
    模型配置历史版本表（审计和回滚）
    
    用途：
    - 每次配置变更时自动创建历史记录
    - 支持版本回滚和时间点恢复
    - 记录变更原因和操作者
    
    与 Current 表的区别：
    - 允许同一 scope 存在多个版本（通过 version 区分）
    - 不包含 created_at 的自动更新（历史记录不可变）
    - 增加了 changed_by 和 change_reason 审计字段
    
    典型使用场景：
    1. 新版本配置测试失败 → 回滚到上一个稳定版本
    2. 审计追踪 → 查看谁在什么时候修改了什么配置
    3. 故障排查 → 对比不同版本的差异
    
    约束条件：
    - uq_model_config_revision_scope_version: (scope, version) 唯一组合
    - ck_model_config_revision_scope: scope 值必须在枚举范围内
    """
    __tablename__: str = "sp_model_config_revision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="全局模型配置作用域")
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="模型服务提供商")
    model: Mapped[str] = mapped_column(String(256), nullable=False, comment="模型名称")
    transport: Mapped[str] = mapped_column(String(16), nullable=False, default="http", comment="模型接入方式")
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="模型服务地址")
    runtime_options_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="本地运行时配置JSON")
    secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加密后的密钥")
    secret_key_id: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="密钥管理系统标识")
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号")
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="测试状态")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="测试时间")
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="测试错误")
    activated_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="激活操作者")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="激活时间")
    changed_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="修改操作者")
    change_reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="变更原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="记录创建时间")

    @property
    def runtime_options(self) -> dict[str, object]:
        if not self.runtime_options_json:
            return {}
        try:
            payload = json.loads(self.runtime_options_json)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    __table_args__: tuple[UniqueConstraint, CheckConstraint, CheckConstraint] = (
        UniqueConstraint("scope", "version", name="uq_model_config_revision_scope_version"),
        CheckConstraint(SCOPE_CHECK_SQL, name="ck_model_config_revision_scope"),
        CheckConstraint(TRANSPORT_CHECK_SQL, name="ck_model_config_revision_transport"),
    )


class ModelConnectivityCheck(Base):
    """
    模型连通性测试记录表（健康检查日志）
    
    用途：
    - 记录每次手动或自动触发的连通性测试结果
    - 追踪模型服务的可用性和性能趋势
    - 为故障诊断提供历史数据
    
    测试类型（trigger_type）：
    - manual: 用户手动触发测试
    - auto: 系统定时任务自动执行
    
    测试状态（status）：
    - success: 测试成功，模型响应正常
    - failed: 测试失败（认证错误、参数错误等）
    - timeout: 请求超时（超过 20 秒无响应）
    - skipped: 跳过测试（配置不完整或服务未启用）
    
    性能指标：
    - latency_ms: 请求延迟（毫秒），用于监控服务性能
    - metadata_json: 详细测试元数据（如向量维度、识别文本预览）
    
    约束条件：
    - ck_model_connectivity_check_scope: scope 值必须在枚举范围内
    - ck_model_connectivity_check_status: status 必须是合法枚举值
    """
    __tablename__: str = "sp_model_connectivity_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="全局模型配置作用域")
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="测试时提供商")
    model: Mapped[str] = mapped_column(String(256), nullable=False, comment="测试时模型")
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="测试时地址")
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="测试对应配置版本")
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", comment="测试触发方式")
    status: Mapped[str] = mapped_column(String(32), nullable=False, comment="测试状态")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="请求时延（毫秒）")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误描述")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="测试元数据JSON")
    checked_by: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="测试执行者")
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="测试时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="记录创建时间")

    __table_args__: tuple[CheckConstraint, CheckConstraint] = (
        CheckConstraint(SCOPE_CHECK_SQL, name="ck_model_connectivity_check_scope"),
        CheckConstraint("status IN ('success', 'failed', 'timeout', 'skipped')", name="ck_model_connectivity_check_status"),
    )
