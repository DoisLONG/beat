# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, List, Optional

from mysql_client import MySQLClient
from config import MYSQL_CONFIG


async def add_tenant(
        tenant_code: str,
        tenant_name: str,
        status: int = 1,
        expire_time: str = None,
        max_user_count: int = None,
        remark: str = None,
        lang: str = "zh",
):
    """
    新增租户
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    # 参数验证
    if not tenant_code or not tenant_name:
        return {
            "status": 400,
            "message": "租户编码和名称不能为空",
            "results": None
        }

    if status not in [0, 1]:
        return {
            "status": 400,
            "message": "状态值无效（0-停用，1-启用）",
            "results": None
        }

    try:
        # 检查租户编码是否已存在
        existing = db_client.query_tenant_by_code(tenant_code, lang=lang)
        if existing:
            return {
                "status": 400,
                "message": f"租户编码【{tenant_code}】已存在",
                "results": None
            }

        # 插入租户记录
        tenant_id = db_client.insert_tenant(
            tenant_code=tenant_code,
            tenant_name=tenant_name,
            status=status,
            expire_time=expire_time,
            max_user_count=max_user_count,
            remark=remark,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"租户【{tenant_name}】新增成功",
            "results": {
                "tenant_id": tenant_id,
                "tenant_code": tenant_code,
                "tenant_name": tenant_name,
                "status": status
            }
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"新增租户失败: {str(e)}",
            "results": None
        }


async def delete_tenant(tenant_id: int, lang: str = "zh"):
    """
    删除租户
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 查询租户是否存在
        tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
        if not tenant:
            return {
                "status": 404,
                "message": f"租户ID不存在: {tenant_id}",
                "results": None
            }

        # 检查租户下是否有公司（业务关联检查）
        # 这里需要根据实际业务需求决定是否允许删除有数据的租户
        # 示例：检查租户下是否有公司
        companies = db_client.query_companies_by_tenant(tenant_id, lang=lang)
        if companies:
            return {
                "status": 400,
                "message": f"租户ID【{tenant_id}】存在关联公司，无法删除",
                "results": None
            }

        # 删除租户
        db_client.delete_tenant(tenant_id=tenant_id, lang=lang)

        return {
            "status": 200,
            "message": f"租户ID【{tenant_id}】删除成功",
            "results": {
                "tenant_id": tenant_id,
                "tenant_name": tenant.get('tenant_name')
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
            "message": f"删除租户失败: {str(e)}",
            "results": None
        }


async def update_tenant(
        tenant_id: int,
        tenant_code: str = None,
        tenant_name: str = None,
        status: int = None,
        expire_time: str = None,
        max_user_count: int = None,
        remark: str = None,
        lang: str = "zh",
):
    """
    更新租户信息
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 查询租户是否存在
        tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
        if not tenant:
            return {
                "status": 404,
                "message": f"租户ID不存在: {tenant_id}",
                "results": None
            }

        # 如果要修改租户编码，检查是否重复
        if tenant_code and tenant_code != tenant.get('tenant_code'):
            existing = db_client.query_tenant_by_code(tenant_code, lang=lang)
            if existing and existing.get('tenant_id') != tenant_id:
                return {
                    "status": 400,
                    "message": f"租户编码【{tenant_code}】已存在",
                    "results": None
                }

        # 验证状态值
        if status is not None and status not in [0, 1]:
            return {
                "status": 400,
                "message": "状态值无效（0-停用，1-启用）",
                "results": None
            }

        # 构建更新数据
        update_data = {
            k: v for k, v in {
                "tenant_code": tenant_code,
                "tenant_name": tenant_name,
                "status": status,
                "expire_time": expire_time,
                "max_user_count": max_user_count,
                "remark": remark
            }.items() if v is not None
        }

        if not update_data:
            return {
                "status": 400,
                "message": "未提供任何更新字段",
                "results": None
            }

        # 更新租户
        db_client.update_tenant(
            tenant_id=tenant_id,
            lang=lang,
            **update_data
        )

        return {
            "status": 200,
            "message": f"租户ID【{tenant_id}】更新成功",
            "results": {
                "tenant_id": tenant_id,
                "updated_fields": list(update_data.keys())
            }
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"更新租户失败: {str(e)}",
            "results": None
        }


async def query_tenant(
        tenant_id: int = None,
        tenant_code: str = None,
        tenant_name: str = None,
        status: int = None,
        lang: str = "zh",
):
    """
    查询租户（支持多条件）
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 构建查询条件
        conditions = {}
        if tenant_id is not None:
            conditions['tenant_id'] = tenant_id
        if tenant_code is not None:
            conditions['tenant_code'] = tenant_code
        if tenant_name is not None:
            conditions['tenant_name__like'] = f'%{tenant_name}%'
        if status is not None:
            conditions['status'] = status

        # 执行查询
        results = db_client.query_tenants_by_multiple_conditions(lang=lang, **conditions)

        return {
            "status": 200,
            "message": f"查询成功，共找到{len(results)}条租户记录",
            "results": {
                "items": results,
                "total": len(results)
            }
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"查询租户失败: {str(e)}",
            "results": None
        }


async def query_tenant_paginated(
        tenant_id: int = None,
        tenant_code: str = None,
        tenant_name: str = None,
        status: int = None,
        page: int = 1,
        page_size: int = 10,
        lang: str = "zh",
) -> Dict:
    """
    租户分页查询
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 校验分页参数
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        # 构建查询条件
        conditions = {}
        if tenant_id is not None:
            conditions['tenant_id'] = tenant_id
        if tenant_code is not None:
            conditions['tenant_code__like'] = f'%{tenant_code}%'
        if tenant_name is not None:
            conditions['tenant_name__like'] = f'%{tenant_name}%'
        if status is not None:
            conditions['status'] = status

        # 执行分页查询
        records: List[Dict] = db_client.query_tenants_paginated(
            conditions=conditions,
            offset=offset,
            limit=page_size,
            lang=lang,
        )

        # 查询总记录数
        total = db_client.count_tenants_by_conditions(lang=lang, **conditions)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return {
            "status": 200,
            "message": "成功",
            "results": {
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
            "message": f"查询租户失败: {str(e)}",
            "results": None
        }
