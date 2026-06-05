# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, List

from mysql_client import MySQLClient
from config import MYSQL_CONFIG


async def add_department(
        company_id: int,
        department_name: str,
        tenant_id: int,  # OWNER 传 None，此时从公司记录派生
        manager: str = None,
        manager_phone: str = None,
        remark: str = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 验证公司是否存在
        company = db_client.query_company_by_id(company_id, lang=lang)
        if not company:
            return {
                "status": 404,
                "message": f"公司ID【{company_id}】不存在",
                "results": None
            }

        # OWNER (tenant_id=None): 从公司记录派生租户ID
        if not tenant_id:
            tenant_id = company.get('tenant_id')
            if not tenant_id:
                return {
                    "status": 400,
                    "message": "无法获取公司所属租户ID",
                    "results": None
                }
        else:
            # ADMIN: 校验 company_id 是否属于自身租户，防止跨租户写入
            if company.get('tenant_id') != tenant_id:
                return {
                    "status": 403,
                    "message": f"公司ID【{company_id}】不属于租户【{tenant_id}】，无权在此公司下新增部门",
                    "results": None
                }

        # 验证租户是否有效
        tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
        if not tenant:
            return {
                "status": 400,
                "message": f"租户ID【{tenant_id}】不存在",
                "results": None
            }

        if tenant.get('status') != 1:
            return {
                "status": 400,
                "message": f"租户ID【{tenant_id}】已停用",
                "results": None
            }

        # 插入部门记录
        department_id = db_client.insert_department(
            company_id=company_id,
            department_name=department_name,
            tenant_id=tenant_id,
            manager=manager,
            manager_phone=manager_phone,
            remark=remark,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"租户【{tenant_id}】公司ID【{company_id}】新增部门【{department_name}】成功",
            "results": {
                "company_id": company_id,
                "department_name": department_name,
                "department_id": department_id,
                "tenant_id": tenant_id
            }
        }
    except ValueError as ve:
        return {
            "status": 400,
            "message": f"新增失败: {str(ve)}",
            "results": None
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"新增部门失败: {str(e)}",
            "results": None
        }


async def delete_department(
        department_id: int,
        tenant_id: int = None,  # 可选：用于租户验证
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 查询部门信息
        department = db_client.query_department_by_id(department_id, lang=lang)
        if not department:
            return {
                "status": 404,
                "message": f"部门ID不存在: {department_id}",
                "results": None
            }

        # 如果提供了租户ID（ADMIN），验证部门是否属于该租户
        if tenant_id and department.get('tenant_id') != tenant_id:
            return {
                "status": 403,
                "message": f"无权删除此部门，部门属于租户{department.get('tenant_id')}",
                "results": None
            }

        # 检查是否存在下属岗位
        positions = db_client.query_posts_by_department_id(department_id, lang=lang)
        if positions:
            position_count = len(positions)
            message = f"部门ID【{department_id}】包含{position_count}个岗位，请先删除关联岗位"
            return {
                "status": 400,
                "message": message,
                "results": None
            }

        db_client.delete_department(department_id=department_id, lang=lang)

        return {
            "status": 200,
            "message": f"部门ID【{department_id}】删除成功",
            "results": {
                "department_id": department_id,
                "tenant_id": department.get('tenant_id')
            }
        }
    except ValueError as ve:
        return {
            "status": 400,
            "message": f"删除失败: {str(ve)}",
            "results": None
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"删除部门失败: {str(e)}",
            "results": None
        }


async def update_department(
        department_id: int,
        tenant_id: int = None,  # 可选：用于租户验证
        company_id: int = None,
        department_name: str = None,
        manager: str = None,
        manager_phone: str = None,
        remark: str = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 查询部门信息
        department = db_client.query_department_by_id(department_id, lang=lang)
        if not department:
            return {
                "status": 404,
                "message": f"部门ID不存在: {department_id}",
                "results": None
            }

        # 如果提供了租户ID（ADMIN），验证部门是否属于该租户
        if tenant_id and department.get('tenant_id') != tenant_id:
            return {
                "status": 403,
                "message": f"无权更新此部门，部门属于租户{department.get('tenant_id')}",
                "results": None
            }

        current_tenant_id = department.get('tenant_id')

        # 如果要修改公司，验证新公司是否存在且属于同一租户
        if company_id is not None and company_id != department.get('company_id'):
            new_company = db_client.query_company_by_id(company_id, lang=lang)
            if not new_company:
                return {
                    "status": 404,
                    "message": f"新公司ID【{company_id}】不存在",
                    "results": None
                }

            if new_company.get('tenant_id') != current_tenant_id:
                return {
                    "status": 403,
                    "message": f"新公司ID【{company_id}】不属于租户【{current_tenant_id}】",
                    "results": None
                }

        # 更新部门记录
        db_client.update_department(
            department_id=department_id,
            tenant_id=current_tenant_id,  # 传递当前租户ID
            company_id=company_id,
            department_name=department_name,
            manager=manager,
            manager_phone=manager_phone,
            remark=remark,
            lang=lang,
        )

        updated_fields = [k for k, v in {
            "company_id": company_id,
            "department_name": department_name,
            "manager": manager,
            "manager_phone": manager_phone,
            "remark": remark
        }.items() if v is not None]

        return {
            "status": 200,
            "message": f"租户【{current_tenant_id}】部门ID【{department_id}】更新成功",
            "results": {
                "department_id": department_id,
                "tenant_id": current_tenant_id,
                "updated_fields": updated_fields
            }
        }
    except ValueError as ve:
        return {
            "status": 400,
            "message": f"更新失败: {str(ve)}",
            "results": None
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"更新部门失败: {str(e)}",
            "results": None
        }


async def query_department(
        tenant_id: int,  # OWNER 传 None 查全局，ADMIN 传自身租户 ID
        department_id: int = None,
        company_id: int = None,
        department_name: str = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER (tenant_id=None) 查全局；ADMIN 验证租户
        if tenant_id is not None:
            tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
            if not tenant:
                return {
                    "status": 400,
                    "message": f"租户ID【{tenant_id}】不存在",
                    "results": None
                }

        # 构建查询条件（OWNER 不加租户过滤）
        conditions = {}
        if tenant_id is not None:
            conditions['tenant_id'] = tenant_id

        if department_id is not None:
            conditions['department_id'] = department_id
        if company_id is not None:
            conditions['company_id'] = company_id
        if department_name is not None:
            conditions['department_name__like'] = f'%{department_name}%'

        results = db_client.query_departments_by_multiple_conditions(lang=lang, **conditions)

        return {
            "status": 200,
            "message": f"查询成功，共找到{len(results)}条部门记录",
            "results": results
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询部门失败: {str(e)}",
            "results": None
        }


# ------------------------------
# 部门表分页查询（添加租户支持）
# ------------------------------
async def query_department_paginated(
        tenant_id: int,  # OWNER 传 None 查全局，ADMIN 传自身租户 ID
        department_id: int = None,
        company_id: int = None,
        department_name: str = None,
        manager: str = None,
        company_name: str = None,
        page: int = 1,
        page_size: int = 10,
        lang: str = "zh",
) -> Dict:
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER (tenant_id=None) 查全局；ADMIN 验证租户
        if tenant_id is not None:
            tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
            if not tenant:
                return {
                    "status": 400,
                    "message": f"租户ID【{tenant_id}】不存在",
                    "results": None
                }

        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        # OWNER 不加租户过滤，ADMIN 加上
        conditions = {}
        if tenant_id is not None:
            conditions['d.tenant_id'] = tenant_id

        if department_id is not None:
            conditions['d.department_id'] = department_id
        if company_id is not None:
            conditions['d.company_id'] = company_id
        if department_name is not None:
            conditions['d.department_name__like'] = f'%{department_name}%'
        if manager is not None:
            conditions['d.manager__like'] = f'%{manager}%'
        if company_name is not None:
            conditions['c.company_name__like'] = f'%{company_name}%'

        records: List[Dict] = db_client.query_departments_with_company(
            conditions=conditions,
            offset=offset,
            limit=page_size,
            lang=lang,
        )

        total = db_client.count_departments_with_company(lang=lang, **conditions)
        total_pages = (total + page_size - 1) // page_size

        return {
            "status": 200,
            "message": "成功",
            "results": {
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "tenant_id": tenant_id
            }
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询部门失败: {str(e)}",
            "results": None
        }
