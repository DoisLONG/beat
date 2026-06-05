# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, List
from mysql_client import MySQLClient
from config import MYSQL_CONFIG


async def add_post(
        tenant_id: int,  # OWNER 传 None，从部门记录派生
        department_id: int,
        position_name: str,
        duty: str = None,
        requirement: str = None,
        remark: str = None,
        lang: str = "zh",
):
    """新增岗位（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER (tenant_id=None): 从部门记录派生租户ID
        if not tenant_id:
            dept = db_client.query_department_by_id(department_id, lang=lang)
            if not dept:
                return {
                    "status": 404,
                    "message": f"部门ID【{department_id}】不存在",
                    "results": None
                }
            tenant_id = dept.get('tenant_id')
            if not tenant_id:
                return {
                    "status": 400,
                    "message": "无法获取部门所属租户ID",
                    "results": None
                }
        else:
            # ADMIN: 校验 department_id 是否属于自身租户，防止跨租户写入
            dept = db_client.query_department_by_id(department_id, lang=lang)
            if not dept:
                return {
                    "status": 404,
                    "message": f"部门ID【{department_id}】不存在",
                    "results": None
                }
            if dept.get('tenant_id') != tenant_id:
                return {
                    "status": 403,
                    "message": f"部门ID【{department_id}】不属于租户【{tenant_id}】，无权在此部门下新增岗位",
                    "results": None
                }

        # 验证租户是否存在且有效
        tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
        if not tenant or tenant.get('status') != 1:
            return {
                "status": 400,
                "message": f"租户ID【{tenant_id}】不存在或已停用",
                "results": None
            }

        position_id = db_client.insert_post(
            tenant_id=tenant_id,
            department_id=department_id,
            position_name=position_name,
            duty=duty,
            requirement=requirement,
            remark=remark,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"租户【{tenant_id}】部门ID【{department_id}】新增岗位【{position_name}】成功",
            "results": {
                "tenant_id": tenant_id,
                "department_id": department_id,
                "position_name": position_name,
                "position_id": position_id
            }
        }
    except ValueError as ve:
        error_msg = str(ve)
        if "Duplicate entry" in error_msg and "uk_post_tenant_dept" in error_msg:
            return {
                "status": 400,
                "message": f"部门【{department_id}】下已存在同名岗位【{position_name}】",
                "results": None
            }
        return {
            "status": 400,
            "message": f"新增失败: {str(ve)}",
            "results": None
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"新增岗位失败: {str(e)}",
            "results": None
        }


async def delete_post(
        position_id: int,
        tenant_id: int,  # OWNER 传 None，从岗位记录派生
        lang: str = "zh",
):
    """删除岗位（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER (tenant_id=None): 从岗位记录派生租户ID
        if not tenant_id:
            positions = db_client.query_posts_by_multiple_conditions(lang=lang, position_id=position_id)
            if not positions:
                return {
                    "status": 404,
                    "message": f"岗位ID【{position_id}】不存在",
                    "results": None
                }
            tenant_id = positions[0].get('tenant_id')
        else:
            # ADMIN: 校验岗位是否属于自身租户
            positions = db_client.query_posts_by_multiple_conditions(lang=lang, position_id=position_id)
            if not positions:
                return {
                    "status": 404,
                    "message": f"岗位ID【{position_id}】不存在",
                    "results": None
                }
            if positions[0].get('tenant_id') != tenant_id:
                return {
                    "status": 403,
                    "message": f"岗位ID【{position_id}】不属于租户【{tenant_id}】，无权删除",
                    "results": None
                }

        course_count = db_client.count_courses_by_position(position_id, tenant_id, lang=lang)
        material_count = db_client.count_materials_by_position(position_id, tenant_id, lang=lang)
        user_count = db_client.count_users_by_position(position_id, tenant_id)
        if course_count > 0 or material_count > 0 or user_count > 0:
            return {
                "status": 400,
                "message": f"该岗位已关联{course_count}个课程、{material_count}个资料和{user_count}个用户，无法删除",
                "results": {
                    "course_count": course_count,
                    "material_count": material_count,
                    "user_count": user_count
                }
            }

        db_client.delete_post(
            position_id=position_id,
            tenant_id=tenant_id,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"租户【{tenant_id}】岗位ID【{position_id}】删除成功",
            "results": {"position_id": position_id, "tenant_id": tenant_id}
        }
    except ValueError as ve:
        return {
            "status": 404,
            "message": f"删除失败: {str(ve)}",
            "results": None
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"删除岗位失败: {str(e)}",
            "results": None
        }


async def update_post(
        position_id: int,
        tenant_id: int,  # OWNER 传 None，从岗位记录派生
        department_id: int = None,
        position_name: str = None,
        duty: str = None,
        requirement: str = None,
        remark: str = None,
        lang: str = "zh",
):
    """更新岗位信息（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER (tenant_id=None): 从岗位记录派生租户ID
        if not tenant_id:
            positions = db_client.query_posts_by_multiple_conditions(lang=lang, position_id=position_id)
            if not positions:
                return {
                    "status": 404,
                    "message": f"岗位ID【{position_id}】不存在",
                    "results": None
                }
            tenant_id = positions[0].get('tenant_id')
        else:
            # ADMIN: 校验岗位是否属于自身租户
            positions = db_client.query_posts_by_multiple_conditions(lang=lang, position_id=position_id)
            if not positions:
                return {
                    "status": 404,
                    "message": f"岗位ID【{position_id}】不存在",
                    "results": None
                }
            if positions[0].get('tenant_id') != tenant_id:
                return {
                    "status": 403,
                    "message": f"岗位ID【{position_id}】不属于租户【{tenant_id}】，无权修改",
                    "results": None
                }

        db_client.update_post(
            position_id=position_id,
            tenant_id=tenant_id,
            department_id=department_id,
            position_name=position_name,
            duty=duty,
            requirement=requirement,
            remark=remark,
            lang=lang,
        )

        updated_fields = [k for k, v in {
            "department_id": department_id,
            "position_name": position_name,
            "duty": duty,
            "requirement": requirement,
            "remark": remark
        }.items() if v is not None]

        return {
            "status": 200,
            "message": f"租户【{tenant_id}】岗位ID【{position_id}】更新成功",
            "results": {
                "position_id": position_id,
                "tenant_id": tenant_id,
                "updated_fields": updated_fields
            }
        }
    except ValueError as ve:
        error_msg = str(ve)
        if "Duplicate entry" in error_msg and "uk_post_tenant_dept" in error_msg:
            return {
                "status": 400,
                "message": f"部门【{department_id}】下已存在同名岗位【{position_name}】",
                "results": None
            }
        return {
            "status": 400,
            "message": f"更新失败: {str(ve)}",
            "results": None
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"更新岗位失败: {str(e)}",
            "results": None
        }


async def query_post(
        tenant_id: int,  # OWNER 传 None 查全局，ADMIN 传自身租户 ID
        position_id: int = None,
        department_id: int = None,
        position_name: str = None,
        lang: str = "zh",
):
    """查询岗位（单条/多条，OWNER 查全局，ADMIN 仅查本租户）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER 不加租户过滤
        conditions = {}
        if tenant_id is not None:
            conditions['tenant_id'] = tenant_id

        if position_id is not None:
            conditions['position_id'] = position_id
        if department_id is not None:
            conditions['department_id'] = department_id
        if position_name is not None:
            conditions['position_name'] = position_name

        results = db_client.query_posts_by_multiple_conditions(lang=lang, **conditions)

        for item in results:
            if 'position_id' in item:
                item['position_id'] = str(item['position_id'])

        return {
            "status": 200,
            "message": f"查询成功，共找到{len(results)}条岗位记录",
            "results": results
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询岗位失败: {str(e)}",
            "results": None
        }


async def query_post_paginated(
        tenant_id: int,  # OWNER 传 None 查全局，ADMIN 传自身租户 ID
        position_id: int = None,
        department_id: int = None,
        company_id: int = None,
        position_name: str = None,
        department_name: str = None,
        company_name: str = None,
        page: int = 1,
        page_size: int = 10,
        lang: str = "zh",
) -> Dict:
    """岗位表分页查询（OWNER 查全局，ADMIN 仅查本租户）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        # OWNER 不加租户过滤
        conditions = {}
        if tenant_id is not None:
            conditions['p.tenant_id'] = tenant_id

        if position_id is not None:
            conditions['p.position_id'] = position_id
        if department_id is not None:
            conditions['p.department_id'] = department_id
        if company_id is not None:
            conditions['d.company_id'] = company_id
        if position_name is not None:
            conditions['p.position_name__like'] = f'%{position_name}%'
        if department_name is not None:
            conditions['d.department_name__like'] = f'%{department_name}%'
        if company_name is not None:
            conditions['c.company_name__like'] = f'%{company_name}%'

        records: List[Dict] = db_client.query_posts_with_company_department(
            conditions=conditions,
            offset=offset,
            limit=page_size,
            lang=lang,
        )

        total = db_client.count_posts_with_company_department(lang=lang, **conditions)
        total_pages = (total + page_size - 1) // page_size

        return {
            "status": 200,
            "message": "成功",
            "results": {
                "tenant_id": tenant_id,
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询岗位失败: {str(e)}",
            "results": None
        }
