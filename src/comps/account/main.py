# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Dict

from fastapi import HTTPException, status, Depends, Request, Query
from sqlalchemy.orm import Session
import datetime

from comps import opea_microservices, register_microservice, CustomLogger, register_statistics
from comps.account.database import get_db
from comps.account.schema import LoginPayload, CreateUserPayload, GetUserParams, TokenData, UpdateUserPayload, \
    UpdatePasswordPayload, ExamRecordPayload, OnboardingStatusPayload
from comps.account import service, schema
from comps.account.model import UserRole, User, get_company_model
from comps.account.auth import require_auth, sign_token, require_auth_dict
from comps.account.session_service import SessionService
from comps.account.util import get_client_ip, get_user_agent

logger = CustomLogger("account", os.getenv("LOG_LEVEL", "INFO"))


def _validate_admin_manage_permission(operator: TokenData, target_user: User) -> None:
    """
    管理员管理用户时的权限控制：
    1) 非所有者不能操作超级管理员；
    2) 非所有者只能操作同租户用户。
    """
    if UserRole.is_owner(operator.role):
        return
    owner_role = int(UserRole.OWNER)
    if target_user.role_id == owner_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，不能操作超级管理员",
        )
    if operator.tenant_id != target_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，不能操作其他租户用户",
        )

@register_microservice(
    name="opea_service@account",
    endpoint="/v1/auth/register",
    host="0.0.0.0",
    port=9011,
    input_datatype=CreateUserPayload,
    methods=["POST"]
)
@register_statistics(names=["opea_service@account"])
async def register(payload: CreateUserPayload, db: Session = Depends(get_db)):
    try:
        # register 接口固定创建超级管理员，归属系统租户（tenant_id=1）
        payload.role_id = int(UserRole.OWNER)
        payload.tenant_id = 1
        lang = payload.lang or "zh"
        user = service.create_user(db, payload, tenant_id=1, lang=lang)
        token = sign_token(user)
        return {
            "status": 200,
            "is_success": True,
            "message": "成功",
            "data": schema.LoginData(**token.__dict__, data=service.format_user_data(db, user)),
            "timestamp": datetime.datetime.now(),
        }
    except HTTPException as e:
        logger.exception(f"注册失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"注册失败：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }

@register_microservice(
    name="opea_service@account",
    endpoint="/v1/auth/login",
    host="0.0.0.0",
    port=9011,
    input_datatype=LoginPayload,
    methods=["POST"]
)
@register_statistics(names=["opea_service@account"])
async def login(payload: LoginPayload, db: Session = Depends(get_db)):
    try:
        user = service.login(db, payload)
        token = sign_token(user)
        return {
            "status": 200,
            "is_success": True,
            "message": "成功",
            "data": schema.LoginData(**token.__dict__, data=service.format_user_data(db, user)),
            "timestamp": datetime.datetime.now(),
        }
    except HTTPException as e:
        logger.exception(f"登录失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"登录失败：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }

@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/get",
    host="0.0.0.0",
    port=9011,
    input_datatype=GetUserParams,
    methods=["GET"]
)
@register_statistics(names=["opea_service@account"])
@require_auth()
async def get_user(
    request: Request,
    params: GetUserParams = Depends(),
    db: Session = Depends(get_db),
    user: TokenData = Depends(),
):
    try:
        if not UserRole.is_admin(user.role) or params is None or params.id is None:
            db_user = service.get_user_by_id(db, str(user.id))
            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="用户未找到",
                )
            return {
                "status": 200,
                "is_success": True,
                "message": "成功",
                "data": service.format_user_data(db, db_user),
                "timestamp": datetime.datetime.now(),
            }

        db_user = service.get_user_by_id(db, str(params.id))
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户未找到",
            )
        # ADMIN 只能查本租户用户，OWNER 可查全局
        if not UserRole.is_owner(user.role) and db_user.tenant_id != user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看其他租户的用户",
            )
        return {
            "status": 200,
            "message": "成功",
            "result": service.format_user_data(db, db_user),
        }
    except HTTPException as e:
        logger.exception(f"获取用户失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"获取用户失败：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/list",
    host="0.0.0.0",
    port=9011,
    input_datatype=GetUserParams,
    methods=["GET"]
)
@require_auth_dict(admin_only=True)
async def get_user_list(
        request: Request,
        params: GetUserParams = Depends(),
        user: Dict = None,  # 从装饰器注入的用户信息
        db: Session = Depends(get_db),
):
    try:
        # OWNER 传 None 查全局，ADMIN 传自身 tenant_id 只看本租户
        role = user.get('role') if user else None
        if UserRole.is_owner(role):
            tenant_id = None
        else:
            tenant_id = user.get('tenant_id') if user else None
        lang = user.get('lang', 'zh') if user else 'zh'

        # 计算分页参数
        skip = 0
        limit = 20
        if params is not None:
            # 方案A: 认定 page 是从 1 开始
            skip = (params.page - 1) * params.size if params.page > 0 else 0
            if params.size:
                limit = params.size

        # 调用服务层查询，传入租户ID和语种
        data = service.list_users(db, params, skip=skip, limit=limit, tenant_id=tenant_id, lang=lang)

        return {
            "status": 200,
            "is_success": True,
            "message": "成功",
            "data": data,
            "timestamp": datetime.datetime.now(),
        }
    except HTTPException as e:
        logger.exception(f"获取用户失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"获取用户失败：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/create",
    host="0.0.0.0",
    port=9011,
    input_datatype=CreateUserPayload,
    methods=["POST"]
)
@register_statistics(names=["opea_service@account"])
@require_auth(admin_only=True)
async def create_user(
        request: Request,
        payload: CreateUserPayload,
        user: TokenData = Depends(),
        db: Session = Depends(get_db),
):
    """创建用户
    - 超级管理员(OWNER)：可在任意租户创建 ADMIN / USER，必须指定 tenant_id
    - 管理员(ADMIN)：只能在本租户创建 ADMIN / USER，不得指定其他租户
    权限已由 @require_auth(admin_only=True) 统一在 JWT 层拦截，此处不再重复校验。
    """
    try:
        # 任何人都不能通过此接口创建超级管理员
        if payload.role_id == int(UserRole.OWNER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权创建超级管理员",
            )

        if UserRole.is_owner(user.role):
            # OWNER：优先用显式 tenant_id，否则从 company_id 派生
            if not payload.tenant_id:
                if payload.company_id:
                    CompanyModel = get_company_model(user.lang)
                    company = db.query(CompanyModel).filter(CompanyModel.company_id == payload.company_id).first()
                    if not company:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"公司ID【{payload.company_id}】不存在，无法派生租户ID",
                        )
                    payload.tenant_id = company.tenant_id
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="超级管理员创建用户时必须指定 tenant_id 或 company_id",
                    )
            target_tenant_id = payload.tenant_id
        else:
            # 管理员：只能在本租户创建，忽略或拦截跨租户请求
            if payload.tenant_id is not None and payload.tenant_id != user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权在其他租户创建用户",
                )
            payload.tenant_id = user.tenant_id
            target_tenant_id = user.tenant_id

        created_user = service.create_user(db, payload, tenant_id=target_tenant_id, lang=user.lang)

        return {
            "status": 200,
            "is_success": True,
            "message": "用户创建成功",
            "data": service.format_user_data(db, created_user),
            "timestamp": datetime.datetime.now(),
        }

    except HTTPException as e:
        logger.exception(f"创建用户失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"创建用户时发生意外错误：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": f"服务器错误: {str(e)}",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }

@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/update",
    host="0.0.0.0",
    port=9011,
    input_datatype=UpdateUserPayload,
    methods=["POST"],
)
@register_statistics(names=["opea_service@account"])
@require_auth()
async def update_user(
    request: Request,
    payload: UpdateUserPayload,
    user: TokenData = Depends(),
    db: Session = Depends(get_db),
):
    try:
        if UserRole.is_admin(user.role):
            target_user = service.get_user_by_id(db, str(payload.id))
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="用户不存在",
                )
            _validate_admin_manage_permission(user, target_user)
            if payload.role_id == int(UserRole.OWNER):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权设置超级管理员角色",
                )
            # OWNER 账号的密码只能由本人通过 change_password 接口修改
            if target_user.role_id == int(UserRole.OWNER) and target_user.id != user.id:
                if payload.password is not None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="不能修改其他超级管理员的密码",
                    )
        elif payload.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            )

        if not UserRole.is_admin(user.role):
            if payload.role_id is not None:
                payload.role_id = None
            if payload.password is not None:
                payload.password = None
        updated_user = service.update_user(db, payload.id, payload, lang=user.lang)
        return {
            "status": 200,
            "is_success": True,
            "message": "成功",
            "data": service.format_user_data(db, updated_user),
            "timestamp": datetime.datetime.now(),
        }
    except HTTPException as e:
        logger.exception(f"更新用户失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"更新用户时发生意外错误：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }

@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/delete",
    host="0.0.0.0",
    port=9011,
    input_datatype=UpdateUserPayload,
    methods=["POST"]
)
@register_statistics(names=["opea_service@account"])
@require_auth(admin_only=True)
async def delete_user(
    request: Request,
    payload: UpdateUserPayload,
    user: TokenData = Depends(),
    db: Session = Depends(get_db),
):
    try:
        target_user = service.get_user_by_id(db, str(payload.id))
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )
        _validate_admin_manage_permission(user, target_user)
        service.delete_user(db, payload.id, user.id)
        return {
            "status": 200,
            "is_success": True,
            "message": "成功",
            "data": "用户已删除。",
            "timestamp": datetime.datetime.now(),
        }
    except HTTPException as e:
        logger.exception(f"删除用户失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"删除用户时发生意外错误：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }

@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/change_password",
    host="0.0.0.0",
    port=9011,
    input_datatype=UpdatePasswordPayload,
)
@register_statistics(names=["opea_service@account"])
@require_auth()
async def change_password(
    request: Request,
    payload: UpdatePasswordPayload,
    user: TokenData = Depends(),
    db: Session = Depends(get_db),
):
    try:
        service.change_password(db, user.id, payload.old_password, payload.new_password)
        return {
            "status": 200,
            "is_success": True,
            "message": "成功",
            "data": "密码已修改。",
            "timestamp": datetime.datetime.now(),
        }
    except HTTPException as e:
        logger.exception(f"修改密码失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"修改密码错误：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }

@register_microservice(
    name="opea_service@account",
    endpoint="/v1/roles/list",
    host="0.0.0.0",
    port=9011,
)
@register_statistics(names=["opea_service@account"])
@require_auth_dict()
async def list_roles(
    request: Request,
    user: Dict = None,
):
    lang = user.get("lang", "zh") if user else "zh"
    roles = [
        schema.Role.from_role_id(UserRole.ADMIN, lang=lang),
        schema.Role.from_role_id(UserRole.USER, lang=lang),
    ]
    # OWNER 角色仅对 OWNER 自身可见（隐藏账号，不出现在角色选择器）
    if UserRole.is_owner(user.get('role') if user else None):
        roles.insert(0, schema.Role.from_role_id(UserRole.OWNER, lang=lang))
    return {
        "status": 200,
        "is_success": True,
        "message": "成功",
        "data": roles,
        "timestamp": datetime.datetime.now(),
    }


@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/exams/records",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
async def get_exam_records_by_user(
        request: Request,
        user_id: str = Query(..., description="用户ID"),
        start_date: str | None = Query(None, description="起始日期 (YYYY-MM-DD)"),
        end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
        page: int = Query(0, description="页码，从0开始"),
        page_size: int = Query(10, description="每页数量"),
        lang: str = Query("zh", description="业务语种（zh/en/th）"),
        db: Session = Depends(get_db),
):
    try:
        details = service.get_exam_records_by_user(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
            lang=lang,
        )
        return {
            "code": 200,
            "message": "success",
            "data": details,
        }
    except HTTPException as e:
        logger.exception(f"获取用户陪练明细失败：{e.detail}")
        return {
            "code": e.status_code,
            "message": e.detail,
            "data": None,
        }
    except Exception as e:
        logger.exception(f"获取用户陪练明细失败：{str(e)}---{e.__traceback__}")
        return {
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "服务器错误",
            "data": None,
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/exams/summary",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
async def get_exam_summary(
    request: Request,
    user_id: str = Query(..., description="用户ID"),
    lang: str = Query("zh", description="业务语种（zh/en/th）"),
    db: Session = Depends(get_db),
):
    """
    个人中心中展示考试数量与通过情况。
    """
    try:
        data = service.get_exam_summary(db=db, user_id=user_id, lang=lang)
        return {
            "code": 200,
            "message": "success",
            "data": data,
        }
    except HTTPException as e:
        logger.exception(f"获取用户陪练总结失败：{e.detail}")
        return {
            "code": e.status_code,
            "message": e.detail,
            "data": None,
        }
    except Exception as e:
        logger.exception(f"获取用户陪练总结失败：{str(e)}---{e.__traceback__}")
        return {
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "服务器错误",
            "data": None,
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/v1/exams/statistics",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
async def get_exam_statistics(
    request: Request,
    user_id: str | None = Query(None, description="用户ID（选填，不传则返回全部用户汇总）"),
    start_date: str | None = Query(None, description="起始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(0, description="页码，从0开始"),
    page_size: int = Query(10, description="每页数量"),
    lang: str = Query("zh", description="业务语种（zh/en/th）"),
    db: Session = Depends(get_db),
):
    try:
        data = service.get_exam_statistics(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
            lang=lang,
        )
        return {
            "code": 200,
            "message": "success",
            "data": data,
        }
    except HTTPException as e:
        return {
            "code": e.status_code,
            "message": e.detail,
            "data": None,
        }
    except Exception as e:
        logger.exception(f"获取用户陪练统计失败：{str(e)}---{e.__traceback__}")
        return {
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "服务器错误",
            "data": None,
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/statistics",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
async def get_user_statistics(
    request: Request,
    tenant_id: int | None = Query(None, description="租户ID，不传则统计全部"),
    lang: str = Query("zh", description="业务语种（zh/en/th），决定统计哪张会话表"),
    db: Session = Depends(get_db),
):
    """
    获取用户统计信息（总人数、活跃用户数、活跃率）

    活跃用户定义：近7天累计在线时长 ≥ 30分钟
    """
    try:
        session_service = SessionService(db, lang=lang)
        data = session_service.get_user_statistics(tenant_id=tenant_id)
        return {
            "status": 200,
            "message": "success",
            "data": data,
        }
    except Exception as e:
        logger.exception(f"获取用户统计失败：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "服务器错误",
            "data": None,
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/api/v1/exams/records",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
async def api_get_exam_records_by_user(
        request: Request,
        user_id: str = Query(..., description="用户ID"),
        start_date: str | None = Query(None, description="起始日期 (YYYY-MM-DD)"),
        end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
        page: int = Query(0, description="页码，从0开始"),
        page_size: int = Query(10, description="每页数量"),
        lang: str = Query("zh", description="业务语种（zh/en/th）"),
        db: Session = Depends(get_db),
):
    return await get_exam_records_by_user(
        request, user_id, start_date, end_date, page, page_size, lang, db
    )


@register_microservice(
    name="opea_service@account",
    endpoint="/api/v1/users/exams/summary",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
async def api_get_exam_summary(
    request: Request,
    user_id: str = Query(..., description="用户ID"),
    lang: str = Query("zh", description="业务语种（zh/en/th）"),
    db: Session = Depends(get_db),
):
    return await get_exam_summary(request, user_id, lang, db)


@register_microservice(
    name="opea_service@account",
    endpoint="/api/v1/exams/statistics",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
async def api_get_exam_statistics(
    request: Request,
    user_id: str | None = Query(None, description="用户ID（选填，不传则返回全部用户汇总）"),
    start_date: str | None = Query(None, description="起始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(0, description="页码，从0开始"),
    page_size: int = Query(10, description="每页数量"),
    lang: str = Query("zh", description="业务语种（zh/en/th）"),
    db: Session = Depends(get_db),
):
    return await get_exam_statistics(
        request, user_id, start_date, end_date, page, page_size, lang, db
    )


@register_microservice(
    name="opea_service@account",
    endpoint="/v1/users/get_exam_records",
    host="0.0.0.0",
    port=9011,
)
async def get_exam_records(
    request: Request,
    payload: ExamRecordPayload,
    user: TokenData = Depends(),
    db: Session = Depends(get_db),
):
    try:
        details = service.get_exam_records(db, payload, lang=user.lang)
        return {
            "status": 200,
            "is_success": True,
            "message": "成功",
            "data": details,
            "timestamp": datetime.datetime.now(),
        }
    except HTTPException as e:
        logger.exception(f"获取陪练明细失败：{e.detail}")
        return {
            "status": e.status_code,
            "is_success": False,
            "message": e.detail,
            "data": None,
            "timestamp": datetime.datetime.now(),
        }
    except Exception as e:
        logger.exception(f"获取陪练明细时发生意外错误：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "is_success": False,
            "message": "服务器错误",
            "data": None,
            "timestamp": datetime.datetime.now(),
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/api/users/heartbeat",
    host="0.0.0.0",
    port=9011,
    methods=["POST"],
)
@require_auth_dict()
async def user_heartbeat(
        request: Request,
        db: Session = Depends(get_db),
        user: dict = None
):
    """
    用户心跳接口

    说明：
        - 前端在页面可见时，每分钟调用一次
        - 用于更新用户的最后活跃时间
        - 自动创建或更新会话记录
    """
    try:
        user_id = user.get("id")
        tenant_id = user.get("tenant_id")
        lang = user.get("lang", "zh")

        if not user_id or not tenant_id:
            raise HTTPException(status_code=400, detail="无效的用户信息")

        # 获取客户端信息
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # 调用会话服务（按语种路由到对应表）
        session_service = SessionService(db, lang=lang)

        # 获取或创建会话
        session = session_service.get_or_create_session(
            user_id,
            tenant_id,
            ip_address,
            user_agent
        )

        # 更新心跳
        success = session_service.update_heartbeat(user_id, tenant_id)

        if success:
            logger.info(f"用户 {user_id}-{user.get('name', '')} 心跳更新成功")
            return {
                "status": 200,
                "message": "心跳更新成功",
                "data": {
                    "session_id": session.session_id
                }
            }
        else:
            return {
                "status": 500,
                "message": "心跳更新失败"
            }

    except Exception as e:
        logger.exception(f"心跳更新失败: {str(e)}")
        db.rollback()
        return {
            "status": 500,
            "message": f"心跳更新失败: {str(e)}"
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/api/users/onboarding",
    host="0.0.0.0",
    port=9011,
    methods=["GET"],
)
@require_auth_dict()
async def get_user_onboarding(
        request: Request,
        db: Session = Depends(get_db),
        user: dict = None
):
    try:
        user_id_raw = user.get("id") if user else None
        if user_id_raw is None:
            raise HTTPException(status_code=400, detail="无效的用户信息")
        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="无效的用户ID")

        onboarding_status = service.get_user_onboarding_status(db, user_id)
        return {
            "status": 200,
            "message": "成功",
            "data": onboarding_status,
        }
    except HTTPException as e:
        logger.exception(f"获取引导状态失败：{e.detail}")
        return {
            "status": e.status_code,
            "message": e.detail,
            "data": None
        }
    except Exception as e:
        logger.exception(f"获取引导状态失败：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "服务器错误",
            "data": None
        }


@register_microservice(
    name="opea_service@account",
    endpoint="/api/users/onboard/update",
    host="0.0.0.0",
    port=9011,
    input_datatype=OnboardingStatusPayload,
    methods=["POST"],
)
@require_auth_dict()
async def update_user_onboarding(
        request: Request,
        payload: OnboardingStatusPayload,
        db: Session = Depends(get_db),
        user: dict = None
):
    try:
        user_id_raw = user.get("id") if user else None
        if user_id_raw is None:
            raise HTTPException(status_code=400, detail="无效的用户信息")
        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="无效的用户ID")

        onboarding_status = service.update_user_onboarding_status(
            db,
            user_id,
            payload.welcome_guide_pending,
            payload.dashboard_welcome_guide_pending,
        )
        return {
            "status": 200,
            "message": "成功",
            "data": onboarding_status
        }
    except HTTPException as e:
        logger.exception(f"更新引导状态失败：{e.detail}")
        return {
            "status": e.status_code,
            "message": e.detail,
            "data": None
        }
    except Exception as e:
        logger.exception(f"更新引导状态失败：{str(e)}")
        return {
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "服务器错误",
            "data": None
        }

@register_microservice(
    name="opea_service@account",
    endpoint="/api/users/session/logout",
    host="0.0.0.0",
    port=9011,
    methods=["POST"],
)
@require_auth_dict()
async def user_logout(
        request: Request,
        db: Session = Depends(get_db),
        user: dict = None
):
    """
    用户登出接口

    说明：
        - 标记用户所有活跃会话结束
        - 记录登出时间
    """
    try:
        user_id = user.get("id")
        tenant_id = user.get("tenant_id")
        lang = user.get("lang", "zh")

        if not user_id or not tenant_id:
            raise HTTPException(status_code=400, detail="无效的用户信息")

        # 调用会话服务（按语种路由到对应表）
        session_service = SessionService(db, lang=lang)
        closed_count = session_service.logout_user(user_id, tenant_id)

        logger.info(f"用户 {user_id}-{user.get('name', '')} 登出，关闭 {closed_count} 个会话")

        return {
            "status": 200,
            "message": "登出成功",
            "data": {
                "closed_sessions": closed_count
            }
        }

    except Exception as e:
        logger.exception(f"登出失败: {str(e)}")
        db.rollback()
        return {
            "code": 500,
            "message": f"登出失败: {str(e)}"
        }


if __name__ == "__main__":
    opea_microservices["opea_service@account"].start()
    # 在本地运行的时候，使用run方法运行，不开启多进程
    # opea_microservices["opea_service@account"].run()
