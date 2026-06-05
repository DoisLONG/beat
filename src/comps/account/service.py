# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, String, cast as sa_cast, case, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import traceback

from starlette.requests import Request

from comps import CustomLogger
from comps.account.database import get_db
from comps.account.model import (
    User, UserRole,
    get_company_model, get_department_model, get_position_model,
    get_exam_record_model,
    Company, Department, Position, ExamRecord,
)
from comps.account.schema import CreateUserPayload, UpdateUserPayload, LoginPayload, ListUsersResponse, GetUserParams, \
    Role, ExamRecordPayload
from comps.account import schema
from comps.account.auth import hash_password
from comps.account.util import normalize_email, normalize_username
from comps.account.config import PASSING_SCORE

logger = CustomLogger("account_service", "info")

def _resolve_lang(lang: str) -> str:
    return lang if lang in ("zh", "en", "th") else "zh"

def _normalize_onboarding_flag(value: Optional[int]) -> int:
    if value is None:
        return 0
    return int(value)


def _resolve_data_lang(db: Session, lang: Optional[str], user_id: Optional[str] = None) -> str:
    if lang:
        return _resolve_lang(lang)
    if user_id is not None:
        db_user = get_user_by_id(db, str(user_id))
        if db_user and getattr(db_user, "lang", None):
            return _resolve_lang(db_user.lang)
    return "zh"


def get_user_onboarding_status(db: Session, user_id: int) -> dict[str, int]:
    db_user = get_user_by_id(db, str(user_id))
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return {
        "welcome_guide_pending": _normalize_onboarding_flag(db_user.welcome_guide_pending),
        "dashboard_welcome_guide_pending": _normalize_onboarding_flag(db_user.dashboard_welcome_guide_pending),
    }


def update_user_onboarding_status(
        db: Session,
        user_id: int,
        welcome_guide_pending: Optional[int] = None,
        dashboard_welcome_guide_pending: Optional[int] = None,
) -> dict[str, int]:
    db_user = db.query(User).filter(User.is_active == True, User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    if welcome_guide_pending is None and dashboard_welcome_guide_pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要更新一个引导状态字段",
        )
    if welcome_guide_pending is not None:
        if welcome_guide_pending not in (0, 1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="welcome_guide_pending 仅支持 0 或 1",
            )
        db_user.welcome_guide_pending = welcome_guide_pending

    if dashboard_welcome_guide_pending is not None:
        if dashboard_welcome_guide_pending not in (0, 1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dashboard_welcome_guide_pending 仅支持 0 或 1",
            )
        db_user.dashboard_welcome_guide_pending = dashboard_welcome_guide_pending

    db.commit()
    db.refresh(db_user)
    return {
        "welcome_guide_pending": _normalize_onboarding_flag(db_user.welcome_guide_pending),
        "dashboard_welcome_guide_pending": _normalize_onboarding_flag(db_user.dashboard_welcome_guide_pending),
    }

def get_user_by_email_or_name(db: Session, email: Optional[str], name: Optional[str]) -> Optional[User]:
    """
    根据邮箱或用户名获取用户，如果两个参数都提供，则通过"或"条件查询
    仅返回第一个匹配且未被删除的用户
    """
    query = db.query(User).filter(User.is_active == True)
    if email and name:
        query = query.filter(or_(User.email == email, User.name == name))
    elif email:
        query = query.filter(User.email == email)
    elif name:
        query = query.filter(User.name == name)
    else:
        return None
    return query.first()

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """
    根据用户ID获取未被删除的用户
    """
    return db.query(User).filter(User.is_active == True).filter(User.id == user_id).first()

def get_company_by_id(db: Session, company_id: int, lang: str = "zh"):
    """
    根据公司ID获取公司（按语种路由到对应表）
    """
    model = get_company_model(lang)
    return db.query(model).filter(model.company_id == company_id).first()

def get_companies(db: Session, company_ids: list[int], lang: str = "zh") -> list:
    """
    根据公司ID列表获取多个公司（按语种路由到对应表）
    """
    model = get_company_model(lang)
    return db.query(model).filter(model.company_id.in_(company_ids)).all()

def validate_company_id(db: Session, company_id: int, lang: str = "zh") -> bool:
    """
    验证公司ID是否存在
    """
    return get_company_by_id(db, company_id, lang=lang) is not None

def get_department_by_id(db: Session, department_id: int, company_id: int = None, lang: str = "zh"):
    """
    根据部门ID获取部门（按语种路由到对应表）
    """
    model = get_department_model(lang)
    query = db.query(model).filter(model.department_id == department_id)
    if company_id is not None:
        query = query.filter(model.company_id == company_id)
    return query.first()

def get_departments(db: Session, department_ids: list[int], lang: str = "zh") -> list:
    """
    根据部门ID列表获取多个部门（按语种路由到对应表）
    """
    model = get_department_model(lang)
    return db.query(model).filter(model.department_id.in_(department_ids)).all()

def validate_department_id(db: Session, department_id: int, company_id: int = None, lang: str = "zh") -> bool:
    """
    验证部门ID是否存在
    """
    return get_department_by_id(db, department_id, company_id=company_id, lang=lang) is not None

def get_position_by_id(db: Session, position_id: int, department_id: int = None, lang: str = "zh"):
    """
    根据职位ID获取职位（按语种路由到对应表）
    """
    model = get_position_model(lang)
    query = db.query(model).filter(model.position_id == position_id)
    if department_id is not None:
        query = query.filter(model.department_id == department_id)
    return query.first()

def get_positions(db: Session, position_ids: list[int], lang: str = "zh") -> list:
    """
    根据职位ID列表获取多个职位（按语种路由到对应表）
    """
    model = get_position_model(lang)
    return db.query(model).filter(model.position_id.in_(position_ids)).all()

def validate_position_id(db: Session, position_id: int, department_id: int = None, lang: str = "zh") -> bool:
    """
    验证职位ID是否存在
    """
    return get_position_by_id(db, position_id, department_id=department_id, lang=lang) is not None


def list_users(
        db: Session,
        params: GetUserParams,
        skip: int = 0,
        limit: int = 100,
        tenant_id: int = None,
        lang: str = "zh",
) -> ListUsersResponse:
    """
    列出所有未被删除的用户，支持分页，可根据用户名、邮箱模糊匹配，或部门ID和职位ID过滤
    添加租户ID过滤，确保数据隔离
    """
    lang = _resolve_lang(lang)

    # 构建基础查询：永远排除超级管理员账号（tenant_id=1 的系统账号不对外暴露）
    query = db.query(User).filter(
        User.is_active == True,
        User.role_id != int(UserRole.OWNER),
    )

    # 添加租户ID过滤（OWNER 传 None 看全局，ADMIN 传自身 tenant_id 仅看本租户）
    if tenant_id is not None:
        query = query.filter(User.tenant_id == tenant_id)
        logger.info(f"查询用户列表，租户ID过滤: {tenant_id}")

    # 用户名模糊匹配
    if params.name:
        query = query.filter(User.name.ilike(f"%{params.name}%"))

    # 邮箱模糊匹配
    if params.email:
        query = query.filter(User.email.ilike(f"%{params.email}%"))

    # 公司ID筛选
    if params.company_id is not None:
        query = query.filter(User.company_id == params.company_id)

    # 部门ID筛选
    if params.department_id is not None:
        query = query.filter(User.department_id == params.department_id)

    # 岗位ID筛选
    if params.position_id is not None:
        query = query.filter(User.position_id == params.position_id)

    query = query.filter(User.lang == lang)

    # 排序和分页
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()

    # 格式化用户数据
    formatted_users = format_users_data(db, users, lang=lang)

    # 返回结果
    page_size = limit
    page = params.page if params is not None and params.page else 1
    return ListUsersResponse(
        data=formatted_users,
        total=total,
        page=page,
        page_size=page_size,
        tenant_id=tenant_id
    )


def create_user(db: Session, user: CreateUserPayload, tenant_id: int, lang: str = "zh") -> User:
    """
    创建新用户。
    Args:
        db: 数据库会话
        user: 用户创建数据（role_id 由调用方负责权限校验后传入）
        tenant_id: 目标租户ID（OWNER 传指定租户，ADMIN 传自身租户，register 传 1）
        lang: 业务语种（用于路由组织信息表）
    Returns:
        User: 创建的用户对象
    """
    lang = _resolve_lang(lang)

    # 数据标准化
    name = normalize_username(user.name)
    email = normalize_email(user.email)

    # 验证用户名和邮箱在目标租户内唯一
    exist_user = get_user_by_email_or_name_in_tenant(db, email=email, name=name, tenant_id=tenant_id)
    if exist_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱在该租户内已被使用",
        )

    # 密码哈希处理
    password = hash_password(user.password)

    # 角色验证和默认值：调用方已完成权限校验，service 只负责兜底非法值
    if not user.role_id or not UserRole.is_valid_role(user.role_id):
        user.role_id = UserRole.USER.value

    if user.company_id is not None:
        if not validate_company_id(db, user.company_id, lang=lang):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="公司ID不存在",
            )

    if user.department_id is not None:
        if not validate_department_id(db, user.department_id, company_id=user.company_id, lang=lang):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="部门ID不存在",
            )

    if user.position_id is not None:
        if not validate_position_id(db, user.position_id, department_id=user.department_id, lang=lang):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="职位ID不存在",
            )

    company = get_company_by_id(db, user.company_id, lang=lang) if user.company_id else None

    # 确定最终租户ID：优先使用 company 归属的租户，否则使用传入的目标租户
    resolved_tenant_id = company.tenant_id if company else tenant_id

    # 用户的业务语种与当前操作者保持一致
    user_lang = getattr(user, "lang", None) or lang
    user_lang = _resolve_lang(user_lang)

    db_user = User(
        name=name,
        email=email,
        full_name=user.full_name,
        telephone=user.telephone,
        role_id=user.role_id,
        password=password,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        tenant_id=resolved_tenant_id,
        company_id=user.company_id,
        department_id=user.department_id,
        position_id=user.position_id,
        lang=user_lang,
    )

    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱在该租户内已被使用",
        )
    db.refresh(db_user)

    logger.info(f"租户【{resolved_tenant_id}】创建用户【{name}】成功，用户ID: {db_user.id}")

    return db_user


def get_user_by_email_or_name_in_tenant(
        db: Session,
        tenant_id: int,
        email: Optional[str] = None,
        name: Optional[str] = None

) -> Optional[User]:
    """
    在指定租户内通过邮箱或用户名查询用户
    """
    query = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.deleted_at.is_(None)
    )

    conditions = []
    if email:
        conditions.append(User.email == email)
    if name:
        conditions.append(User.name == name)
    if conditions:
        query = query.filter(or_(*conditions))
    else:
        return None

    return query.first()




def update_user(db: Session, user_id: str, payload: UpdateUserPayload, lang: str = "zh") -> User:
    """
    更新用户信息，支持修改全名、头像URL、电话、部门ID、职位ID
    仅所有者可修改用户角色和用户密码
    仅更新提供的字段，未提供的字段保持不变
    """
    lang = _resolve_lang(lang)
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    if payload.role_id is not None:
        if not UserRole.is_valid_role(payload.role_id) or (db_user.role_id != UserRole.OWNER
                                                           and payload.role_id == UserRole.OWNER):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户角色错误",
            )
        db_user.role_id = payload.role_id

    if payload.company_id is not None and payload.company_id != db_user.company_id:
        if not validate_company_id(db, payload.company_id, lang=lang):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="公司ID不存在",
            )
        db_user.company_id = payload.company_id

    if payload.department_id is not None and payload.department_id != db_user.department_id:
        if not validate_department_id(db, payload.department_id, company_id=db_user.company_id, lang=lang):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="部门ID不存在",
            )
        db_user.department_id = payload.department_id

    if payload.position_id is not None and payload.position_id != db_user.position_id:
        if not validate_position_id(db, payload.position_id, department_id=db_user.department_id, lang=lang):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="职位ID不存在",
            )
        db_user.position_id = payload.position_id

    for field in ['full_name', 'avatar_url', 'telephone']:
        value = getattr(payload, field)
        if value is not None:
            setattr(db_user, field, value)

    if payload.password is not None:
        db_user.password = hash_password(payload.password)

    db.commit()
    db.refresh(db_user)
    return db_user

def change_password(db: Session, user_id: str, old_password: str, new_password: str) -> None:
    """
    修改用户密码，需提供旧密码进行验证
    """
    from .auth import verify_password
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    if not verify_password(old_password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误",
        )
    db_user.password = hash_password(new_password)
    db.commit()

def delete_user(db: Session, user_id: str, deleted_by: int) -> None:
    """
    软删除用户，设置 is_active=False，并记录删除时间和删除者ID
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    db_user.is_active = False
    db_user.deleted_at = datetime.now(timezone.utc)
    db_user.deleted_by = deleted_by
    db.commit()

def login(db: Session, payload: LoginPayload) -> User:
    """
    用户登录，支持用户名或邮箱登录
    验证用户名/邮箱和密码，成功则返回用户信息
    """
    email = normalize_email(payload.email)
    user = get_user_by_email_or_name(db, email=email, name=payload.name)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    from .auth import verify_password
    if not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    return user

def format_user_data(db: Session, user: User) -> schema.UserData:
    """
    将 User 模型转换为 UserData schema。
    组织信息（Company/Department/Position）按 user.lang 路由到对应语种表。
    """
    lang = _resolve_lang(getattr(user, "lang", None) or "zh")
    user_data = dict(user.__dict__)
    user_data["welcome_guide_pending"] = _normalize_onboarding_flag(user.welcome_guide_pending)
    user_data["dashboard_welcome_guide_pending"] = _normalize_onboarding_flag(user.dashboard_welcome_guide_pending)
    data = schema.UserData(**user_data)
    if data.role_id is not None:
        data.role = schema.Role.from_role_id(data.role_id, lang=lang)
    if user.company_id is not None:
        data.company = get_company_by_id(db, user.company_id, lang=lang)
    if user.department_id is not None:
        data.department = get_department_by_id(db, user.department_id, lang=lang)
    if user.position_id is not None:
        data.position = get_position_by_id(db, user.position_id, lang=lang)
    return data

def format_users_data(db: Session, users: list[User], lang: str = "zh") -> list[schema.UserData]:
    """
    将 User 模型列表转换为 UserData schema 列表。
    组织信息按 lang 参数路由到对应语种表（批量查询优化）。
    """

    lang = _resolve_lang(lang)

    company_ids = {user.company_id for user in users if user.company_id is not None}
    department_ids = {user.department_id for user in users if user.department_id is not None}
    position_ids = {user.position_id for user in users if user.position_id is not None}

    companies = {comp.company_id: comp for comp in get_companies(db, list(company_ids), lang=lang)} if company_ids else {}
    departments = {dept.department_id: dept for dept in get_departments(db, list(department_ids), lang=lang)} if department_ids else {}
    positions = {pos.position_id: pos for pos in get_positions(db, list(position_ids), lang=lang)} if position_ids else {}

    result = []
    for user in users:
        user_data = dict(user.__dict__)
        user_data["welcome_guide_pending"] = _normalize_onboarding_flag(user.welcome_guide_pending)
        user_data["dashboard_welcome_guide_pending"] = _normalize_onboarding_flag(user.dashboard_welcome_guide_pending)
        data = schema.UserData(**user_data)
        if data.role_id is not None:
            data.role = schema.Role.from_role_id(data.role_id, lang=_resolve_lang(getattr(user, "lang", None) or "zh"))
        if user.company_id is not None:
            data.company = companies.get(user.company_id)
        if user.department_id is not None:
            data.department = departments.get(user.department_id)
        if user.position_id is not None:
            data.position = positions.get(user.position_id)
        result.append(data)
    return result

def get_position_company_department_by_id(db: Session, position_id: int, lang: str = "zh"):
    """
    通过 position_id 获取职位名称、部门名称、公司名称（按语种路由）
    返回 dict: {position_name, department_name, company_name}
    """
    lang = _resolve_lang(lang)
    position_model = get_position_model(lang)
    department_model = get_department_model(lang)
    company_model = get_company_model(lang)

    position = db.query(position_model).filter(position_model.position_id == position_id).first()
    if not position:
        return None
    department = db.query(department_model).filter(department_model.department_id == position.department_id).first()
    company = db.query(company_model).filter(company_model.company_id == department.company_id).first() if department else None
    return {
        "position_name": position.position_name if position else None,
        "department_name": department.department_name if department else None,
        "company_name": company.company_name if company else None
    }


async def create_exam_record(exam_record=None, lang: str = "zh"):
    try:
        db_gen = get_db()
        db = next(db_gen)
        # 使用 merge 实现 upsert：如果存在则更新，否则插入
        persistent_obj = db.merge(exam_record)
        db.commit()
        db.refresh(persistent_obj)
        logger.info(f"新增考试记录: {persistent_obj.__dict__}")
        return persistent_obj
    except Exception as e:
        logger.error(f"创建陪练明细失败: {traceback.format_exc()}")
        logger.info("---------------------------------------")
        logger.info(exam_record.__str__())
        raise HTTPException(status_code=500, detail=str(e))


def get_exam_records(
    db: Session,
    payload: ExamRecordPayload,
    lang: Optional[str] = None,
):
    """分页查询陪练明细，按语种路由到对应表，可按用户名称、公司、部门和岗位过滤"""
    lang = _resolve_data_lang(db, lang, user_id=str(payload.user_id) if payload.user_id is not None else None)
    exam_model = get_exam_record_model(lang)
    position_model = get_position_model(lang)
    department_model = get_department_model(lang)
    company_model = get_company_model(lang)

    # --------------------------
    # 构造动态过滤条件
    # --------------------------
    filters = []

    if payload.user_id is not None:
        filters.append(User.id == payload.user_id)

    if payload.username is not None:
        filters.append(User.name.contains(payload.username))

    if payload.company_id is not None:
        filters.append(company_model.company_id == payload.company_id)

    if payload.department_id is not None:
        filters.append(department_model.department_id == payload.department_id)

    if payload.position_id is not None:
        filters.append(sa_cast(position_model.position_id, String) == payload.position_id)

    # --------------------------
    # 通用 JOIN 语句
    # --------------------------
    join_user = User, exam_model.user_id == User.id
    join_position = position_model, sa_cast(position_model.position_id, String) == exam_model.position_id
    join_department = department_model, position_model.department_id == department_model.department_id
    join_company = company_model, department_model.company_id == company_model.company_id

    # --------------------------
    # 统计 total
    # --------------------------
    total = (
        db.query(func.count(exam_model.id))
        .join(*join_user, isouter=True)
        .join(*join_position, isouter=True)
        .join(*join_department, isouter=True)
        .join(*join_company, isouter=True)
        .filter(*filters)
        .scalar()
    )

    # --------------------------
    # 主查询
    # --------------------------
    base_query = (
        db.query(exam_model, User, position_model, department_model, company_model)
        .join(*join_user, isouter=True)
        .join(*join_position, isouter=True)
        .join(*join_department, isouter=True)
        .join(*join_company, isouter=True)
        .filter(*filters)
    )

    # --------------------------
    # 排序 & 分页
    # --------------------------
    ordered = base_query.order_by(
        func.coalesce(department_model.department_id, "~~~").asc()
    )

    offset_val = (payload.page - 1) * payload.page_size if payload.page > 0 else 0
    rows = ordered.offset(offset_val).limit(payload.page_size).all()

    # --------------------------
    # 数据构造
    # --------------------------
    data = {
        "total": total,
        "page": payload.page,
        "page_size": payload.page_size,
    }
    items = []

    for rec, user_row, pos_row, dept_row, comp_row in rows:
        role_obj = (
            Role.from_role_id(user_row.role_id, lang=lang)
            if user_row and user_row.role_id is not None
            else None
        )

        # rec.position_id 若为字符串并含有 ":"，拆分
        position_name = None
        department_name = None
        company_name = None
        if isinstance(rec.position_id, str) and ":" in rec.position_id:
            company_name, department_name, position_name = [
                p.strip() for p in rec.position_id.split(":", 2)
            ]

        items.append({
            "id": rec.id,
            "user_id": rec.user_id,
            "user_name": user_row.name if user_row else None,
            "role_id": user_row.role_id if user_row else None,
            "role": role_obj,
            "position_id": rec.position_id,
            "position_name": pos_row.position_name if pos_row else position_name,
            "department_id": dept_row.department_id if dept_row else None,
            "department_name": dept_row.department_name if dept_row else department_name,
            "company_id": comp_row.company_id if comp_row else None,
            "company_name": comp_row.company_name if comp_row else company_name,
            "start_time": rec.start_time,
            "end_time": rec.end_time.strftime("%Y-%m-%d %H:%M:%S") if rec.end_time else None,
            "answered_question_num": rec.answered_questions,
            "total_question_num": rec.total_questions,
            "accumulated_score": rec.accumulated_score,
            "total_score": rec.total_score,
        })
        data["items"] = items

    return data


def get_exam_records_by_user(
    db: Session,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 0,
    page_size: int = 10,
    lang: Optional[str] = None,
):
    """
    查询当前登录用户的考试历史记录（按语种路由到对应表）
    """
    lang = _resolve_data_lang(db, lang, user_id=user_id)
    exam_model = get_exam_record_model(lang)

    start_date_str = start_date
    end_date_str = end_date

    filters = []
    if user_id is None:
        raise HTTPException(status_code=400, detail="用户ID不能为空")

    filters.append(exam_model.user_id == user_id)

    start_dt = None
    end_dt = None

    if start_date_str is not None:
        start_dt = parse_date_ymd(start_date_str, "start_date")
        filters.append(exam_model.start_time >= start_dt)

    if end_date_str is not None:
        end_dt = parse_date_ymd(end_date_str, "end_date", end_of_day=True)
        filters.append(exam_model.end_time <= end_dt)

    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    # 统计 total
    total = (
        db.query(func.count(exam_model.id))
        .filter(*filters)
        .scalar()
    )

    # 主查询
    base_query = db.query(exam_model).filter(*filters)

    # 排序 & 分页
    ordered = base_query.order_by(exam_model.start_time.asc())
    rows = ordered.offset(page * page_size).limit(page_size).all()

    # 数据构造
    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
    }
    items = []
    for rec in rows:
        items.append({
            "exam_id": rec.id,
            "user_id": rec.user_id,
            "exam_name": rec.filename,
            "score": rec.accumulated_score,
            "is_passed": rec.accumulated_score >= PASSING_SCORE if rec.accumulated_score is not None else False,
            "start_time": rec.start_time.strftime("%Y-%m-%dT%H:%M:%S%z") if rec.start_time else None,
            "end_time": rec.end_time.strftime("%Y-%m-%dT%H:%M:%S%z") if rec.end_time else None,
        })
    data["items"] = items
    return data


def get_exam_summary(db: Session, user_id: str, lang: Optional[str] = None):
    """
    获取用户考试总结信息（按语种路由到对应表）
    return {
        "total_exam_count": 10,
        "passed_exam_count": 8,
        "failed_exam_count": 2,
        "pass_rate": 0.8,
        "last_exam_time": "2025-12-09T11:00:00+08:00"
    }
    """
    lang = _resolve_data_lang(db, lang, user_id=user_id)
    exam_model = get_exam_record_model(lang)

    if user_id is None:
        raise HTTPException(status_code=400, detail="用户ID不能为空")

    filters = [exam_model.user_id == user_id]

    # 总考试数
    total_exam_count = db.query(func.count(exam_model.id)).filter(*filters).scalar() or 0

    # 通过考试数
    passed_exam_count = db.query(func.count(exam_model.id)).filter(
        *filters, exam_model.accumulated_score >= PASSING_SCORE
    ).scalar() or 0

    failed_exam_count = max(total_exam_count - passed_exam_count, 0)

    # 最近一次考试开始时间
    last_exam_row = (
        db.query(exam_model.start_time)
        .filter(*filters)
        .order_by(exam_model.start_time.desc())
        .first()
    )
    last_exam_time = None
    if last_exam_row and last_exam_row[0]:
        last_dt = last_exam_row[0]
        last_exam_time = last_dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    # 通过率
    pass_rate = (passed_exam_count / total_exam_count) if total_exam_count > 0 else 0.0

    return {
        "total_exam_count": total_exam_count,
        "passed_exam_count": passed_exam_count,
        "failed_exam_count": failed_exam_count,
        "pass_rate": round(pass_rate, 4),
        "last_exam_time": last_exam_time,
    }


def get_exam_statistics(
    db: Session,
    user_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 0,
    page_size: int = 10,
    lang: Optional[str] = None,
):
    """
    按用户维度汇总考试次数与通过情况（按语种路由到对应表）
    params:
        user_id（选填；不传则返回全部用户汇总）
        start_date，end_date（选填）
        page，page_size
    """
    lang = _resolve_data_lang(db, lang, user_id=user_id)
    exam_model = get_exam_record_model(lang)

    start_date_str = start_date
    end_date_str = end_date

    start_dt = parse_date_ymd(start_date_str, "start_date")
    end_dt = parse_date_ymd(end_date_str, "end_date", end_of_day=True)

    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    filters = []
    if user_id:
        filters.append(exam_model.user_id == user_id)
    if start_dt is not None:
        filters.append(exam_model.start_time >= start_dt)
    if end_dt is not None:
        filters.append(exam_model.end_time <= end_dt)

    # 统计用户总数（分组后计数）
    total_users = (
        db.query(exam_model.user_id)
        .filter(*filters)
        .group_by(exam_model.user_id)
        .count()
    )

    # 每用户最近考试时间子查询
    last_time_sub_query = (
        db.query(
            exam_model.user_id.label("uid"),
            func.max(exam_model.start_time).label("last_time"),
        )
        .filter(*filters)
        .group_by(exam_model.user_id)
        .subquery()
    )

    agg_query = (
        db.query(
            exam_model.user_id.label("uid"),
            func.count(exam_model.id).label("total_exam_count"),
            func.sum(case((exam_model.accumulated_score >= PASSING_SCORE, 1), else_=0)).label("passed_exam_count"),
            func.sum(case((exam_model.accumulated_score < PASSING_SCORE, 1), else_=0)).label("failed_exam_count"),
            last_time_sub_query.c.last_time.label("last_exam_time"),
        )
        .outerjoin(User, sa_cast(User.id, String) == sa_cast(exam_model.user_id, String))
        .outerjoin(
            last_time_sub_query,
            and_(
                sa_cast(last_time_sub_query.c.uid, String) == sa_cast(exam_model.user_id, String)
            )
        )
        .filter(*filters)
        .group_by(exam_model.user_id, last_time_sub_query.c.last_time)
        .order_by(exam_model.user_id.asc())
        .offset(page * page_size)
        .limit(page_size)
    )

    rows = agg_query.all()

    items = []
    for r in rows:
        total_count = int(r.total_exam_count or 0)
        passed_count = int(r.passed_exam_count or 0)
        failed_count = int(
            r.failed_exam_count if r.failed_exam_count is not None else max(total_count - passed_count, 0))
        pass_rate = round((passed_count / total_count), 4) if total_count > 0 else 0.0

        last_exam_time = None
        if r.last_exam_time:
            last_exam_time = r.last_exam_time.strftime("%Y-%m-%dT%H:%M:%S%z")

        items.append({
            "user_id": r.uid,
            "total_exam_count": total_count,
            "passed_exam_count": passed_count,
            "failed_exam_count": failed_count,
            "pass_rate": pass_rate,
            "last_exam_time": last_exam_time,
        })

    return {
        "total": total_users,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def parse_date_ymd(dstr: str | None, field: str, end_of_day: bool = False) -> datetime | None:
    if not dstr:
        return None
    try:
        dt = datetime.strptime(dstr, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} 格式必须为 YYYY-MM-DD")
    if end_of_day:
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt
