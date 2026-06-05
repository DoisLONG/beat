# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from typing import Any, Dict, List

from fastapi import Body, Request, UploadFile, File, Query
from pydantic import TypeAdapter, ValidationError

from comps import opea_microservices, register_microservice
from company_routes import add_company, delete_company, update_company, query_company, query_company_paginated, add_company_with_auto_tenant
from comps.system_common.config import SYSTEM_COMMON_PORT
from comps.system_common.app_version_routes import (
    get_app_version_current,
    publish_app_version,
    revoke_app_version,
    list_app_versions,
    upload_app_version_package,
    download_app_version_package,
)
# from comps.system_common.sop_version_routes import (
#     create_sop_version,
#     delete_sop_version,
#     update_sop_version,
#     get_sop_version,
# )
from department_routes import add_department, delete_department, update_department, query_department, query_department_paginated
from post_routes import add_post, delete_post, update_post, query_post, query_post_paginated
from comps.account.auth import require_auth_dict
from comps.account.model import UserRole


def _effective_tenant_id(user: dict) -> int | None:
    """OWNER（role=1）不受租户限制，返回 None；ADMIN/USER 返回自身租户 ID。"""
    if UserRole.is_owner(user.get('role')):
        return None
    return user.get('tenant_id')
from comps.system_common.database import get_db
from comps.system_common.model import ModelConfigScope
from comps.system_common.schema import (
    ModelConfigScopedUpsertRequest,
)
from comps.system_common.service import (
    DraftConnectivityConfig,
    list_model_configs,
    run_all_model_connectivity_probes_with_draft,
    upsert_model_config,
)

# 在现有导入基础上添加
from tenant_routes import add_tenant, delete_tenant, update_tenant, query_tenant, query_tenant_paginated


def _parse_model_config_items(payload: Any) -> tuple[list[ModelConfigScopedUpsertRequest], bool]:
    if isinstance(payload, list):
        items = TypeAdapter(list[ModelConfigScopedUpsertRequest]).validate_python(payload)
        return items, True
    if isinstance(payload, dict) and isinstance(payload.get("configs"), list):
        items = TypeAdapter(list[ModelConfigScopedUpsertRequest]).validate_python(payload["configs"])
        return items, True
    if isinstance(payload, dict):
        return [ModelConfigScopedUpsertRequest.model_validate(payload)], False
    raise ValueError("请求体格式错误。")


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/tenant/add",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(owner_only=True)
async def add_tenant_route(
        request: Request,
        tenant_code: str = Body(..., embed=True, description="租户编码（唯一，必填）"),
        tenant_name: str = Body(..., embed=True, description="租户名称（必填）"),
        status: int = Body(1, embed=True, description="状态：1-启用，0-停用（默认1）"),
        expire_time: str = Body(None, embed=True, description="过期时间（格式：YYYY-MM-DD HH:MM:SS，可选）"),
        max_user_count: int = Body(None, embed=True, description="最大用户数（可选）"),
        remark: str = Body(None, embed=True, description="备注信息（可选）"),
        user: Dict = None
):
    """新增租户（仅 OWNER 可操作）"""
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    return await add_tenant(
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        status=status,
        expire_time=expire_time,
        max_user_count=max_user_count,
        remark=remark,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/tenant/delete",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(owner_only=True)
async def delete_tenant_route(
        request: Request,
        tenant_id: int = Body(..., embed=True, description="租户ID（必填）"),
        user: Dict = None
):
    """删除租户（仅 OWNER 可操作）"""
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    return await delete_tenant(tenant_id=tenant_id, lang=user.get("lang", "zh"))


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/tenant/update",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(owner_only=True)
async def update_tenant_route(
        request: Request,
        tenant_id: int = Body(..., embed=True, description="租户ID（必填）"),
        tenant_code: str = Body(None, embed=True, description="新租户编码（可选，需唯一）"),
        tenant_name: str = Body(None, embed=True, description="新租户名称（可选）"),
        status: int = Body(None, embed=True, description="新状态：1-启用，0-停用（可选）"),
        expire_time: str = Body(None, embed=True, description="新过期时间（可选）"),
        max_user_count: int = Body(None, embed=True, description="新最大用户数（可选）"),
        remark: str = Body(None, embed=True, description="新备注（可选）"),
        user: Dict = None
):
    """更新租户信息（仅 OWNER 可操作）"""
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    return await update_tenant(
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        status=status,
        expire_time=expire_time,
        max_user_count=max_user_count,
        remark=remark,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/tenant/query",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)
async def query_tenant_route(
        request: Request,
        tenant_id: int = Body(None, embed=True, description="租户ID（OWNER 可选；ADMIN 自动锁定本租户）"),
        tenant_code: str = Body(None, embed=True, description="租户编码（精确查询，可选）"),
        tenant_name: str = Body(None, embed=True, description="租户名称（模糊查询，可选）"),
        status: int = Body(None, embed=True, description="状态：1-启用，0-停用（可选）"),
        user: Dict = None
):
    """查询租户（OWNER 可查全局，ADMIN 只能查本租户）"""
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    # ADMIN 强制锁定本租户，忽略请求体中的 tenant_id
    if not UserRole.is_owner(user.get('role')):
        tenant_id = _effective_tenant_id(user)

    return await query_tenant(
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        status=status,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/tenant/paginated",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)
async def query_tenant_paginated_route(
        request: Request,
        tenant_id: int = Body(None, embed=True, description="租户ID（OWNER 可选；ADMIN 自动锁定本租户）"),
        tenant_code: str = Body(None, embed=True, description="租户编码（模糊匹配，可选）"),
        tenant_name: str = Body(None, embed=True, description="租户名称（模糊匹配，可选）"),
        status: int = Body(None, embed=True, description="状态：1-启用，0-停用（可选）"),
        page: int = Body(1, embed=True, description="页码（默认第1页）"),
        page_size: int = Body(10, embed=True, description="每页条数（默认10条，最大100条）"),
        user: Dict = None
):
    """租户分页查询（OWNER 可查全局，ADMIN 只能查本租户）"""
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    # ADMIN 强制锁定本租户，忽略请求体中的 tenant_id
    if not UserRole.is_owner(user.get('role')):
        tenant_id = _effective_tenant_id(user)

    return await query_tenant_paginated(
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        status=status,
        page=page,
        page_size=page_size,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/company/add",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def add_company_route(
        request: Request,
        company_name: str = Body(..., embed=True, description="公司名称（必填）"),
        establish_time: str = Body(None, embed=True, description="成立时间（格式：YYYY-MM-DD，可选）"),
        address: str = Body(None, embed=True, description="公司地址（可选）"),
        contact_phone: str = Body(None, embed=True, description="联系电话（可选）"),
        remark: str = Body(None, embed=True, description="备注信息（可选）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    lang = user.get("lang", "zh")

    if UserRole.is_owner(user.get('role')):
        # OWNER: 自动创建新租户 + 公司
        return await add_company_with_auto_tenant(
            company_name=company_name,
            establish_time=establish_time,
            address=address,
            contact_phone=contact_phone,
            remark=remark,
            lang=lang,
        )
    else:
        # ADMIN: 在自身租户下新建公司
        tenant_id = _effective_tenant_id(user)
        return await add_company(
            company_name=company_name,
            tenant_id=tenant_id,
            establish_time=establish_time,
            address=address,
            contact_phone=contact_phone,
            remark=remark,
            lang=lang,
        )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/company/delete",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def delete_company_route(
        request: Request,
        company_id: int = Body(..., embed=True, description="公司ID（必填）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await delete_company(
        company_id=company_id,
        tenant_id=tenant_id,  # 传递租户ID进行验证
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/company/update",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def update_company_route(
        request: Request,
        company_id: int = Body(..., embed=True, description="公司ID（必填）"),
        company_name: str = Body(None, embed=True, description="新公司名称（可选）"),
        establish_time: str = Body(None, embed=True, description="新成立时间（格式：YYYY-MM-DD，可选）"),
        address: str = Body(None, embed=True, description="新地址（可选）"),
        contact_phone: str = Body(None, embed=True, description="新联系电话（可选）"),
        remark: str = Body(None, embed=True, description="新备注（可选）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await update_company(
        company_id=company_id,
        tenant_id=tenant_id,  # 传递租户ID进行验证
        company_name=company_name,
        establish_time=establish_time,
        address=address,
        contact_phone=contact_phone,
        remark=remark,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/company/query",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def query_company_route(
        request: Request,
        company_id: int = Body(None, embed=True, description="公司ID（精确查询，可选）"),
        company_name: str = Body(None, embed=True, description="公司名称（模糊查询，可选）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await query_company(
        tenant_id=tenant_id,  # 传递租户ID
        company_id=company_id,
        company_name=company_name,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/department/add",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def add_department_route(
        request: Request,
        company_id: int = Body(..., embed=True, description="所属公司ID（必填，需存在）"),
        department_name: str = Body(..., embed=True, description="部门名称（必填，同一公司内不可重复）"),
        manager: str = Body(None, embed=True, description="部门负责人（可选）"),
        manager_phone: str = Body(None, embed=True, description="负责人电话（可选）"),
        remark: str = Body(None, embed=True, description="备注信息（可选）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await add_department(
        company_id=company_id,
        department_name=department_name,
        tenant_id=tenant_id,  # 传递租户ID
        manager=manager,
        manager_phone=manager_phone,
        remark=remark,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/department/delete",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def delete_department_route(
        request: Request,
        department_id: int = Body(..., embed=True, description="部门ID（必填）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await delete_department(
        department_id=department_id,
        tenant_id=tenant_id,  # 传递租户ID进行验证
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/department/update",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def update_department_route(
        request: Request,
        department_id: int = Body(..., embed=True, description="部门ID（必填，定位更新记录）"),
        company_id: int = Body(None, embed=True, description="新所属公司ID（可选，需存在）"),
        department_name: str = Body(None, embed=True, description="新部门名称（可选，同一公司内不可重复）"),
        manager: str = Body(None, embed=True, description="新负责人（可选）"),
        manager_phone: str = Body(None, embed=True, description="新负责人电话（可选）"),
        remark: str = Body(None, embed=True, description="新备注（可选）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await update_department(
        department_id=department_id,
        tenant_id=tenant_id,  # 传递租户ID进行验证
        company_id=company_id,
        department_name=department_name,
        manager=manager,
        manager_phone=manager_phone,
        remark=remark,
        lang=user.get("lang", "zh"),
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/department/query",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def query_department_route(
        request: Request,
        department_id: int = Body(None, embed=True, description="部门ID（精确查询，可选）"),
        company_id: int = Body(None, embed=True, description="所属公司ID（查询该公司下所有部门，可选）"),
        department_name: str = Body(None, embed=True, description="部门名称（模糊查询，可选）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await query_department(
        tenant_id=tenant_id,  # 传递租户ID
        department_id=department_id,
        company_id=company_id,
        department_name=department_name,
        lang=user.get("lang", "zh"),
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/position/add",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器（与其他接口保持一致）
async def add_position_route(
    request: Request,
    department_id: int = Body(..., embed=True, description="所属部门ID（必填，需存在）"),
    position_name: str = Body(..., embed=True, description="岗位名称（必填，同一部门内不可重复）"),
    duty: str = Body(None, embed=True, description="岗位职责（可选）"),
    requirement: str = Body(None, embed=True, description="任职要求（可选）"),
    remark: str = Body(None, embed=True, description="备注信息（可选）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """新增岗位（包含租户验证）"""
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await add_post(
        tenant_id=tenant_id,  # 传递租户ID
        department_id=department_id,
        position_name=position_name,
        duty=duty,
        requirement=requirement,
        remark=remark,
        lang=user.get("lang", "zh"),
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/position/delete",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def delete_position_route(
    request: Request,
    position_id: int = Body(..., embed=True, description="岗位ID（必填）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """删除岗位（包含租户验证）"""
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await delete_post(
        position_id=position_id,
        tenant_id=tenant_id,  # 传递租户ID进行验证
        lang=user.get("lang", "zh"),
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/position/update",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def update_position_route(
    request: Request,
    position_id: int = Body(..., embed=True, description="岗位ID（必填，定位更新记录）"),
    department_id: int = Body(None, embed=True, description="新所属部门ID（可选，需存在）"),
    position_name: str = Body(None, embed=True, description="新岗位名称（可选，同一部门内不可重复）"),
    duty: str = Body(None, embed=True, description="新岗位职责（可选）"),
    requirement: str = Body(None, embed=True, description="新任职要求（可选）"),
    remark: str = Body(None, embed=True, description="新备注（可选）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """更新岗位信息（包含租户验证）"""
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await update_post(
        position_id=position_id,
        tenant_id=tenant_id,  # 传递租户ID进行验证
        department_id=department_id,
        position_name=position_name,
        duty=duty,
        requirement=requirement,
        remark=remark,
        lang=user.get("lang", "zh"),
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/position/query",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def query_position_route(
    request: Request,
    position_id: int = Body(None, embed=True, description="岗位ID（精确查询，可选）"),
    department_id: int = Body(None, embed=True, description="所属部门ID（查询该部门下所有岗位，可选）"),
    position_name: str = Body(None, embed=True, description="岗位名称（模糊查询，可选）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """查询岗位（单条/多条，包含租户筛选）"""
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await query_post(
        tenant_id=tenant_id,  # 传递租户ID
        position_id=position_id,
        department_id=department_id,
        position_name=position_name,
        lang=user.get("lang", "zh"),
    )

# NOTE: 暂时停用 system-common 的 SOP Version 接口。
# 当前业务主链路走 dataprep（本地 sop_version_util + dataprep.mysql_client），
# 这里先不再注册以下 endpoints：
# - /v1/sop_version/create
# - /v1/sop_version/delete
# - /v1/sop_version/update
# - /v1/sop_version/get


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/app_version/current",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
async def get_app_version_current_route(
    current_version_code: int = Body(None, embed=True, description="客户端当前版本号（可选）"),
):
    return await get_app_version_current(current_version_code=current_version_code)


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/app_version/publish",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)
async def publish_app_version_route(
    request: Request,
    edition_name: str = Body(..., embed=True, description="版本名称（展示用）"),
    edition_version_code: int = Body(..., embed=True, description="版本号（程序比较用）"),
    describe_zh: str = Body("", embed=True, description="中文更新说明"),
    describe_en: str = Body("", embed=True, description="英文更新说明"),
    describe_th: str = Body("", embed=True, description="泰文更新说明"),
    edition_url: str = Body(..., embed=True, description="安装包或wgt下载地址"),
    edition_force: int = Body(0, embed=True, description="是否强制更新：0否1是"),
    package_type: int = Body(1, embed=True, description="包类型：0整包 1wgt"),
    edition_issue: int = Body(1, embed=True, description="是否发行：0否1是"),
    edition_silence: int = Body(0, embed=True, description="是否静默更新：0否1是"),
    user: Dict = None,
):
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    publisher = user.get("name") or user.get("username") or "unknown"
    return await publish_app_version(
        edition_name=edition_name,
        edition_version_code=edition_version_code,
        describe_zh=describe_zh,
        describe_en=describe_en,
        describe_th=describe_th,
        edition_url=edition_url,
        edition_force=edition_force,
        package_type=package_type,
        edition_issue=edition_issue,
        edition_silence=edition_silence,
        published_by=publisher,
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/app_version/revoke",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)
async def revoke_app_version_route(
    request: Request,
    id: int = Body(..., embed=True, description="版本ID"),
    revoke_reason: str = Body(None, embed=True, description="撤销原因"),
    user: Dict = None,
):
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    revoker = user.get("name") or user.get("username") or "unknown"
    return await revoke_app_version(
        version_id=id,
        revoke_reason=revoke_reason,
        revoked_by=revoker,
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/app_version/list",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)
async def list_app_versions_route(
    request: Request,
    page: int = Body(1, embed=True, description="页码"),
    page_size: int = Body(10, embed=True, description="每页条数"),
    status: int = Body(None, embed=True, description="状态：1已发布 2已撤销"),
    edition_name: str = Body(None, embed=True, description="版本名称模糊查询"),
    edition_version_code: int = Body(None, embed=True, description="版本号精确查询"),
    user: Dict = None,
):
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    return await list_app_versions(
        page=page,
        page_size=page_size,
        status=status,
        edition_name=edition_name,
        edition_version_code=edition_version_code,
    )


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/app_version/upload",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)
async def upload_app_version_package_route(
    request: Request,
    file: UploadFile = File(...),
    user: Dict = None,
):
    if not user:
        return {"status": 401, "message": "用户未认证", "results": None}

    uploader = user.get("name") or user.get("username") or "unknown"
    return await upload_app_version_package(file=file, uploader=uploader)


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/app_version/download",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
    methods=["GET"],
)
async def download_app_version_package_route(
    request: Request,
    id: int = Query(..., description="版本ID（publish 返回的 results.id）"),
):
    return await download_app_version_package(
        version_id=id,
        range_header=request.headers.get("range"),
    )

# ------------------------------
# 公司表分页查询接口
# ------------------------------
@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/company/paginated",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def query_company_paginated_route(
        request: Request,
        company_id: int = Body(None, embed=True, description="公司ID（精确匹配，可选）"),
        company_name: str = Body(None, embed=True, description="公司名称（模糊匹配，可选）"),
        address: str = Body(None, embed=True, description="公司地址（模糊匹配，可选）"),
        contact_phone: str = Body(None, embed=True, description="联系电话（模糊匹配，可选）"),
        page: int = Body(1, embed=True, description="页码（默认第1页）"),
        page_size: int = Body(10, embed=True, description="每页条数（默认10条，最大100条）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    """公司表分页查询接口（支持多条件筛选，包含租户过滤）"""
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await query_company_paginated(
        tenant_id=tenant_id,  # 传递租户ID
        company_id=company_id,
        company_name=company_name,
        address=address,
        contact_phone=contact_phone,
        page=page,
        page_size=page_size,
        lang=user.get("lang", "zh"),
    )

# ------------------------------
# 部门表分页查询接口（含公司名称）
# ------------------------------
@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/department/paginated",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器
async def query_department_paginated_route(
        request: Request,
        department_id: int = Body(None, embed=True, description="部门ID（精确匹配，可选）"),
        company_id: int = Body(None, embed=True, description="所属公司ID（精确匹配，可选）"),
        department_name: str = Body(None, embed=True, description="部门名称（模糊匹配，可选）"),
        manager: str = Body(None, embed=True, description="部门负责人（模糊匹配，可选）"),
        company_name: str = Body(None, embed=True, description="公司名称（模糊匹配，可选）"),
        page: int = Body(1, embed=True, description="页码（默认第1页）"),
        page_size: int = Body(10, embed=True, description="每页条数（默认10条，最大100条）"),
        user: Dict = None  # 从装饰器注入的用户信息
):
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await query_department_paginated(
        tenant_id=tenant_id,  # 传递租户ID
        department_id=department_id,
        company_id=company_id,
        department_name=department_name,
        manager=manager,
        company_name=company_name,
        page=page,
        page_size=page_size,
        lang=user.get("lang", "zh"),
    )

# ------------------------------
# 岗位表分页查询接口（含公司+部门名称）
# ------------------------------
@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/position/paginated",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
)
@require_auth_dict(admin_only=True)  # 添加认证装饰器（与其他接口保持一致）
async def query_post_paginated_route(
    request: Request,
    position_id: int = Body(None, embed=True, description="岗位ID（精确匹配，可选）"),
    department_id: int = Body(None, embed=True, description="所属部门ID（精确匹配，可选）"),
    company_id: int = Body(None, embed=True, description="所属公司ID（精确匹配，可选）"),
    position_name: str = Body(None, embed=True, description="岗位名称（模糊匹配，可选）"),
    department_name: str = Body(None, embed=True, description="部门名称（模糊匹配，可选）"),
    company_name: str = Body(None, embed=True, description="公司名称（模糊匹配，可选）"),
    page: int = Body(1, embed=True, description="页码（默认第1页）"),
    page_size: int = Body(10, embed=True, description="每页条数（默认10条，最大100条）"),
    user: Dict = None  # 从装饰器注入的用户信息
):
    """岗位表分页查询接口（关联部门+公司表，返回部门/公司名称，支持多条件筛选，包含租户过滤）"""
    if not user:
        return {
            "status": 401,
            "message": "用户未认证",
            "results": None
        }

    tenant_id = _effective_tenant_id(user)
    if tenant_id is None and not UserRole.is_owner(user.get('role')):
        return {
            "status": 400,
            "message": "用户未关联租户",
            "results": None
        }

    return await query_post_paginated(
        tenant_id=tenant_id,  # 传递租户ID
        position_id=position_id,
        department_id=department_id,
        company_id=company_id,
        position_name=position_name,
        department_name=department_name,
        company_name=company_name,
        page=page,
        page_size=page_size,
        lang=user.get("lang", "zh"),
    )

@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/system/model-config/list",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
    methods=["GET"]
)
@require_auth_dict(admin_only=True)
async def list_model_configs_route(request: Request, user: Dict[str, Any] = None):
    reveal_api_key = str(request.query_params.get("reveal_api_key", "true")).lower() in {"1", "true", "yes", "on"}
    with get_db() as db:
        results = list_model_configs(db, reveal_api_key=reveal_api_key)
        return {"status": 200, "message": "获取成功", "results": results}


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/system/model-config/upsert",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
    methods=["POST"]
)
@require_auth_dict(admin_only=True)
async def upsert_model_config_route(
    request: Request,
    user: Dict[str, Any] = None,
):
    actor = user.get("name", "unknown") if user else "unknown"
    try:
        payload = await request.json()
    except Exception:
        return {"status": 400, "message": "请求体必须是合法 JSON。", "results": None}

    try:
        upsert_items, is_batch_request = _parse_model_config_items(payload)
    except (ValidationError, ValueError) as e:
        return {"status": 400, "message": f"参数校验失败：{str(e)}", "results": None}

    with get_db() as db:
        results = []
        try:
            for item in upsert_items:
                result = upsert_model_config(
                    db,
                    scope=item.scope,
                    model=item.model,
                    transport=item.transport,
                    base_url=item.base_url,
                    api_key=item.api_key,
                    runtime_options=item.runtime_options,
                    last_test_status=item.last_test_status,
                    actor=actor,
                    auto_commit=False,
                )
                results.append(result)
            db.commit()
            if is_batch_request:
                return {"status": 200, "message": "批量配置保存成功", "results": results}
            return {"status": 200, "message": "配置保存成功", "results": results[0]}
        except ValueError as e:
            db.rollback()
            return {"status": 400, "message": str(e), "results": None}
        except Exception as e:
            db.rollback()
            return {"status": 500, "message": f"配置保存失败：{str(e)}", "results": None}


@register_microservice(
    name="opea_service@prepare_company_mysql",
    endpoint="/v1/system/model-config/test-all",
    host="0.0.0.0",
    port=SYSTEM_COMMON_PORT,
    methods=["POST"]
)
@require_auth_dict(admin_only=True)
async def test_model_config_all_scopes_route(
    request: Request,
    user: Dict[str, Any] | None = None,
):
    actor = user.get("name", "unknown") if user else "unknown"
    try:
        payload = await request.json()
    except Exception:
        return {"status": 400, "message": "请求体必须是合法 JSON。", "results": None}

    try:
        draft_items, _ = _parse_model_config_items(payload)
    except (ValidationError, ValueError) as e:
        return {"status": 400, "message": f"参数校验失败：{str(e)}", "results": None}

    with get_db() as db:
        draft_configs = [
            DraftConnectivityConfig(
                scope=item.scope,
                model=item.model,
                transport=item.transport,
                base_url=item.base_url,
                api_key=item.api_key,
                runtime_options=item.runtime_options or {},
            )
            for item in draft_items
        ]
        results = run_all_model_connectivity_probes_with_draft(db, checked_by=actor, draft_configs=draft_configs)
        has_failures = any(item.status in {"failed", "timeout"} for item in results)
        status_code = 207 if has_failures else 200
        message = "连通性测试部分失败" if has_failures else "连通性测试全部通过"
        return {"status": status_code, "message": message, "results": results}


if __name__ == "__main__":
    opea_microservices["opea_service@prepare_company_mysql"].start()
