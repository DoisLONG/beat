# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, Optional
from datetime import datetime
import os

from mysql_client import MySQLClient
from config import MYSQL_CONFIG
from comps.learn.file_access import apply_proxy_urls_to_materials
from comps.account.model import UserRole


# 统一的 current_user 解析（与 course_routes._resolve_user_context 一致）
# 返回 (tenant_id, lang, effective_tenant_id, err_response)
#   - tenant_id: JWT 原始 tenant_id（OWNER 也保留）
#   - lang: JWT.lang（zh/en/th），非法降级为 zh
#   - effective_tenant_id: OWNER → None（mysql_client 跨租户查询），其它角色 → 原 tenant_id
def _resolve_user_context(current_user: Optional[Dict]):
    if not current_user:
        return None, None, None, {"code": 401, "message": "用户未认证", "data": {}}
    tenant_id = current_user.get('tenant_id')
    if not tenant_id:
        return None, None, None, {"code": 400, "message": "用户未关联租户或token中缺少tenant_id", "data": {}}
    lang = current_user.get('lang') or 'zh'
    if lang not in ('zh', 'en', 'th'):
        lang = 'zh'
    role = current_user.get('role')
    effective_tenant_id = None if (role is not None and UserRole.is_owner(int(role))) else int(tenant_id)
    return int(tenant_id), lang, effective_tenant_id, None


async def upload_material_file(
    title: str,
    file_url: str,
    description: str = None,
    category: str = None,
    course_id: str = None,
    position_id: int = None,
    file_type: str = None,
    size: int = None,
    current_user: Dict = None
):
    """上传学习资料文件（包含租户和岗位信息）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    tenant_id, lang, _effective_tenant_id, err = _resolve_user_context(current_user)
    if err:
        return err

    try:
        # 生成资料ID
        material_id = f"MAT_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 验证租户是否存在
        tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
        if not tenant or tenant.get('status') != 1:
            return {
                "code": 400,
                "message": f"租户ID【{tenant_id}】不存在或已停用",
                "data": {}
            }

        # 如果关联课程，检查课程是否存在且属于同一租户
        if course_id:
            course = db_client.query_course_info(course_id, tenant_id, lang=lang)
            if not course:
                return {
                    "code": 404,
                    "message": f"课程ID【{course_id}】不存在",
                    "data": {}
                }
            # 验证课程是否属于该租户
            # if course.get('tenant_id') != tenant_id:
            #     return {
            #         "code": 403,
            #         "message": f"课程ID【{course_id}】不属于租户【{tenant_id}】",
            #         "data": {}
            #     }

        # 如果关联岗位，检查岗位是否存在
        if position_id:
            position_info = db_client.query_position_by_id(position_id, lang=lang)
            tenant_id = position_info.get("tenant_id")

        # 获取文件类型
        if not file_type and file_url:
            file_type = file_url.split('.')[-1].lower() if '.' in file_url else None

        result = db_client.upload_material(
            material_id=material_id,
            title=title,
            file_url=file_url,
            description=description,
            category=category,
            course_id=course_id,
            position_id=position_id,
            file_type=file_type,
            size=size,
            tenant_id=tenant_id,  # 新增：租户ID
            lang=lang
        )

        return {
            "code": 0,
            "message": "success",
            "data": result
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"上传学习资料失败: {str(e)}",
            "data": {}
        }


async def update_material_info(
    material_id: int,
    title: str = None,
    description: str = None,
    category: str = None,
    course_id: str = None,
    position_id: int = None,
    current_user: Dict = None
):
    """更新学习资料信息（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    tenant_id, lang, _effective_tenant_id, err = _resolve_user_context(current_user)
    if err:
        return err

    try:
        # 首先验证资料是否存在且属于该租户
        material = db_client.query_material_by_id_and_tenant(material_id, tenant_id, lang=lang)
        if not material:
            return {
                "code": 404,
                "message": f"学习资料ID【{material_id}】不存在或无权访问",
                "data": {}
            }

        # 如果关联课程，检查课程是否存在且属于同一租户
        if course_id:
            course = db_client.query_course_info(course_id, tenant_id, lang=lang)
            if not course:
                return {
                    "code": 404,
                    "message": f"课程ID【{course_id}】不存在",
                    "data": {}
                }
            # 验证课程是否属于该租户
            if course.get('tenant_id') != tenant_id:
                return {
                    "code": 403,
                    "message": f"课程ID【{course_id}】不属于租户【{tenant_id}】",
                    "data": {}
                }

        # 如果关联岗位，检查岗位是否存在（position_id为0表示清除关联）
        if position_id is not None and position_id != 0:
            position = db_client.query_position_by_id(position_id, tenant_id, lang=lang)
            if not position:
                return {
                    "code": 400,
                    "message": f"岗位ID【{position_id}】不存在",
                    "data": {}
                }

        success = db_client.update_material_info(
            material_id=material_id,
            tenant_id=tenant_id,  # 新增：用于验证
            title=title,
            description=description,
            category=category,
            course_id=course_id,
            position_id=position_id,
            lang=lang
        )

        if success:
            return {
                "code": 0,
                "message": "success",
                "data": {}
            }
        else:
            return {
                "code": 500,
                "message": "更新学习资料失败",
                "data": {}
            }
    except Exception as e:
        return {
            "code": 500,
            "message": f"更新学习资料失败: {str(e)}",
            "data": {}
        }


async def delete_material(material_id: str, current_user: Dict = None):
    """删除学习资料（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    tenant_id, lang, _effective_tenant_id, err = _resolve_user_context(current_user)
    if err:
        return err

    try:
        success = db_client.delete_material_logic(
            material_id=material_id,
            tenant_id=tenant_id,  # 新增：用于验证
            lang=lang
        )

        if success:
            return {
                "code": 0,
                "message": "success",
                "data": {}
            }
        else:
            return {
                "code": 404,
                "message": f"学习资料ID【{material_id}】不存在或无权删除",
                "data": {}
            }
    except Exception as e:
        return {
            "code": 500,
            "message": f"删除学习资料失败: {str(e)}",
            "data": {}
        }


async def get_materials_list(
        category: str = None,
        keyword: str = None,
        course_id: str = None,
        position_id: int = None,
        department_id: int = None,
        company_id: int = None,
        position_name: str = None,
        department_name: str = None,
        company_name: str = None,
        page: int = 1,
        page_size: int = 20,
        current_user: Dict = None
):
    """学习资料列表查询（关联岗位+部门+公司表，包含租户筛选；OWNER 跨租户全量）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    tenant_id, lang, effective_tenant_id, err = _resolve_user_context(current_user)
    if err:
        return err

    try:
        offset = (page - 1) * page_size
        result = db_client.query_materials_list(
            tenant_id=effective_tenant_id,  # OWNER 传 None 跨租户全量，其他角色按自身 tenant_id 隔离
            category=category,
            keyword=keyword,
            course_id=course_id,
            position_id=position_id,
            department_id=department_id,
            company_id=company_id,
            position_name=position_name,
            department_name=department_name,
            company_name=company_name,
            offset=offset,
            limit=page_size,
            lang=lang
        )

        items = apply_proxy_urls_to_materials(result.get("items", []))

        return {
            "code": 0,
            "message": "success",
            "data": {
                "total": result.get("total", 0),
                "page": page,
                "page_size": page_size,
                "items": items
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"查询学习资料列表失败: {str(e)}",
            "data": {}
        }


# 新增：获取租户下的所有资料分类
async def get_material_categories(current_user: Dict = None):
    """获取指定租户下的所有资料分类（OWNER 跨租户全量）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    tenant_id, lang, effective_tenant_id, err = _resolve_user_context(current_user)
    if err:
        return err

    try:
        categories = db_client.query_material_categories_by_tenant(effective_tenant_id, lang=lang)
        return {
            "code": 0,
            "message": "success",
            "data": categories
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"查询资料分类失败: {str(e)}",
            "data": {}
        }
