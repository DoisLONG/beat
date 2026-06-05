# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, BigInteger, UniqueConstraint
from sqlalchemy.sql import func
from comps.account.database import Base

# =============================================================================
# 语种路由辅助
# =============================================================================
_VALID_LANGS = ("zh", "en", "th")


def _resolve_lang(lang: str) -> str:
    """将非法语种值降级为 zh。"""
    return lang if lang in _VALID_LANGS else "zh"


# =============================================================================
# Tenant — sp_tenant / sp_tenant_en / sp_tenant_th
# =============================================================================

class _TenantBase(Base):
    __abstract__ = True

    tenant_id = Column(Integer, primary_key=True, autoincrement=True, comment='租户ID（主键）')
    tenant_code = Column(String(50), nullable=False, comment='租户编码（唯一）')
    tenant_name = Column(String(200), nullable=False, comment='租户名称')
    status = Column(Integer, nullable=False, default=1, comment='状态：1-启用，0-停用')
    expire_time = Column(DateTime, nullable=True, comment='过期时间')
    max_user_count = Column(Integer, nullable=True, comment='最大用户数')
    remark = Column(Text, nullable=True, comment='备注信息')
    create_time = Column(DateTime, nullable=False, server_default=func.now(), comment='记录创建时间')
    update_time = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment='记录更新时间')


class Tenant(_TenantBase):
    __tablename__ = "sp_tenant"


class TenantEn(_TenantBase):
    __tablename__ = "sp_tenant_en"


class TenantTh(_TenantBase):
    __tablename__ = "sp_tenant_th"


_TENANT_MODEL_MAP = {"zh": Tenant, "en": TenantEn, "th": TenantTh}


def get_tenant_model(lang: str):
    return _TENANT_MODEL_MAP[_resolve_lang(lang)]


# =============================================================================
# UserRole
# =============================================================================

class UserRole(int, Enum):
    OWNER = 1
    ADMIN = 2
    USER = 3

    @staticmethod
    def is_valid_role(role: int) -> bool:
        if not role:
            return False
        return role in (
            UserRole.OWNER,
            UserRole.ADMIN,
            UserRole.USER,
        )

    @staticmethod
    def is_owner(role: int) -> bool:
        if not role:
            return False
        return role == UserRole.OWNER

    @staticmethod
    def is_admin(role: int) -> bool:
        if not role:
            return False
        return role in (UserRole.OWNER, UserRole.ADMIN)

    @staticmethod
    def is_grantable_role(role: int) -> bool:
        if not role:
            return False
        return role in (UserRole.ADMIN, UserRole.USER)


# =============================================================================
# User — sp_user（单表，增加 lang 字段）
# =============================================================================

class User(Base):
    __tablename__ = "sp_user"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uk_user_tenant_name"),
        UniqueConstraint("tenant_id", "email", name="uk_user_tenant_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    email = Column(String(256), index=True, nullable=False)
    tenant_id = Column(Integer, nullable=True)
    full_name = Column(String(256), nullable=True)
    telephone = Column(String(32), nullable=True)
    password = Column(String(256), nullable=False)
    avatar_url = Column(String(512), nullable=True)
    role_id = Column(Integer, default=UserRole.USER, nullable=False)
    company_id = Column(Integer, nullable=True)
    position_id = Column(Integer, nullable=True)
    department_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, nullable=True)
    welcome_guide_pending = Column(Integer, nullable=False, default=0)
    dashboard_welcome_guide_pending = Column(Integer, nullable=False, default=0)
    lang = Column(String(8), nullable=False, default="zh", comment='业务语种环境（zh/en/th）')


# =============================================================================
# Company — sp_company / sp_company_en / sp_company_th
# =============================================================================

class _CompanyBase(Base):
    __abstract__ = True

    company_id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(256), nullable=False)
    tenant_id = Column(Integer, nullable=True)


class Company(_CompanyBase):
    __tablename__ = "sp_company"


class CompanyEn(_CompanyBase):
    __tablename__ = "sp_company_en"


class CompanyTh(_CompanyBase):
    __tablename__ = "sp_company_th"


_COMPANY_MODEL_MAP = {"zh": Company, "en": CompanyEn, "th": CompanyTh}


def get_company_model(lang: str):
    return _COMPANY_MODEL_MAP[_resolve_lang(lang)]


# =============================================================================
# Department — sp_department / sp_department_en / sp_department_th
# =============================================================================

class _DepartmentBase(Base):
    __abstract__ = True

    department_id = Column(Integer, primary_key=True, index=True)
    department_name = Column(String(256), nullable=False)
    company_id = Column(Integer, nullable=True)


class Department(_DepartmentBase):
    __tablename__ = "sp_department"


class DepartmentEn(_DepartmentBase):
    __tablename__ = "sp_department_en"


class DepartmentTh(_DepartmentBase):
    __tablename__ = "sp_department_th"


_DEPARTMENT_MODEL_MAP = {"zh": Department, "en": DepartmentEn, "th": DepartmentTh}


def get_department_model(lang: str):
    return _DEPARTMENT_MODEL_MAP[_resolve_lang(lang)]


# =============================================================================
# Position — sp_position / sp_position_en / sp_position_th
# =============================================================================

class _PositionBase(Base):
    __abstract__ = True

    position_id = Column(Integer, primary_key=True, index=True)
    position_name = Column(String(256), nullable=False)
    department_id = Column(Integer, nullable=True)


class Position(_PositionBase):
    __tablename__ = "sp_position"


class PositionEn(_PositionBase):
    __tablename__ = "sp_position_en"


class PositionTh(_PositionBase):
    __tablename__ = "sp_position_th"


_POSITION_MODEL_MAP = {"zh": Position, "en": PositionEn, "th": PositionTh}


def get_position_model(lang: str):
    return _POSITION_MODEL_MAP[_resolve_lang(lang)]


# =============================================================================
# ExamRecord — sp_exam_record / sp_exam_record_en / sp_exam_record_th
# =============================================================================

class _ExamRecordBase(Base):
    __abstract__ = True

    id = Column(String(32), primary_key=True, index=True)
    user_id = Column(String(255), nullable=True)
    position_id = Column(String(255), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    exam_category = Column(String(64), nullable=True)
    filename = Column(String(256), nullable=True)
    conversation_id = Column(String(64), nullable=True)
    summary = Column(Text, nullable=True)
    total_score = Column(Float, nullable=True)
    accumulated_score = Column(Float, nullable=True)
    total_questions = Column(Integer, nullable=True)
    answered_questions = Column(Integer, nullable=True)


class ExamRecord(_ExamRecordBase):
    __tablename__ = "sp_exam_record"


class ExamRecordEn(_ExamRecordBase):
    __tablename__ = "sp_exam_record_en"


class ExamRecordTh(_ExamRecordBase):
    __tablename__ = "sp_exam_record_th"


_EXAM_RECORD_MODEL_MAP = {"zh": ExamRecord, "en": ExamRecordEn, "th": ExamRecordTh}


def get_exam_record_model(lang: str):
    return _EXAM_RECORD_MODEL_MAP[_resolve_lang(lang)]


# =============================================================================
# UserSession — sp_user_session / sp_user_session_en / sp_user_session_th
# =============================================================================

class _UserSessionBase(Base):
    """用户会话表 - 用于追踪用户在线时长"""
    __abstract__ = True

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True, comment='会话唯一标识')
    user_id = Column(Integer, nullable=False, index=True, comment='用户ID')
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    login_time = Column(DateTime, nullable=False, comment='登录时间')
    last_active_time = Column(DateTime, nullable=False, comment='最后活跃时间')
    logout_time = Column(DateTime, nullable=True, comment='登出时间')
    ip_address = Column(String(45), nullable=True, comment='登录IP地址')
    user_agent = Column(String(512), nullable=True, comment='浏览器标识')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserSession(_UserSessionBase):
    __tablename__ = "sp_user_session"


class UserSessionEn(_UserSessionBase):
    __tablename__ = "sp_user_session_en"


class UserSessionTh(_UserSessionBase):
    __tablename__ = "sp_user_session_th"


_USER_SESSION_MODEL_MAP = {"zh": UserSession, "en": UserSessionEn, "th": UserSessionTh}


def get_user_session_model(lang: str):
    return _USER_SESSION_MODEL_MAP[_resolve_lang(lang)]
