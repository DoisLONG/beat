# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import pymysql
from typing import Dict, List

from comps import CustomLogger
from mysql_client import MySQLClient
from config import MYSQL_CONFIG

logger = CustomLogger("prepare_execl_milvus", os.getenv("LOG_LEVEL", "INFO"))
async def add_company(
        company_name: str,
        tenant_id: int,
        establish_time: str = None,
        address: str = None,
        contact_phone: str = None,
        remark: str = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    # 参数验证
    if not tenant_id:
        return {
            "status": 400,
            "message": "租户ID不能为空",
            "results": None
        }

    try:
        # 验证租户是否存在
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

        # 检查同一租户内公司名称是否重复
        existing = db_client.query_company_by_name_and_tenant(
            company_name=company_name,
            tenant_id=tenant_id,
            lang=lang,
        )
        if existing:
            return {
                "status": 400,
                "message": f"租户【{tenant_id}】下公司【{company_name}】已存在",
                "results": None
            }

        # 创建公司并同时创建默认部门和岗位
        result = db_client.insert_company(
            company_name=company_name,
            tenant_id=tenant_id,
            establish_time=establish_time,
            address=address,
            contact_phone=contact_phone,
            remark=remark,
            create_default_entities=True,  # 默认为True
            lang=lang,
        )

        # 根据是否创建了默认实体返回不同的消息
        if result.get("department_id") and result.get("position_id"):
            message = f"租户【{tenant_id}】公司【{company_name}】新增成功，已创建默认部门和通用岗位"
        else:
            message = f"租户【{tenant_id}】公司【{company_name}】新增成功"

        return {
            "status": 200,
            "message": message,
            "results": {
                "company_id": result["company_id"],
                "company_name": company_name,
                "tenant_id": tenant_id,
                "default_department_id": result.get("department_id"),
                "default_department_name": result.get("default_department_name"),
                "default_position_id": result.get("position_id"),
                "default_position_name": result.get("default_position_name")
            }
        }

    except Exception as e:
        return {
            "status": 500,
            "message": f"新增公司失败: {str(e)}",
            "results": None
        }


async def add_company_with_auto_tenant(
        company_name: str,
        establish_time: str = None,
        address: str = None,
        contact_phone: str = None,
        remark: str = None,
        lang: str = "zh",
):
    """
    创建公司并自动创建新租户（租户信息完全自动生成）
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    company_name = (company_name or "").strip()
    if not company_name:
        return {
            "status": 400,
            "message": "公司名称不能为空",
            "results": None
        }

    existing_company = db_client.query_company_by_name(company_name, lang=lang)
    if existing_company:
        return {
            "status": 400,
            "message": f"已有同名公司：{company_name}",
            "results": {
                "company_id": existing_company.get("company_id"),
                "company_name": existing_company.get("company_name")
            }
        }

    try:
        import time
        import random
        import string
        from datetime import datetime, timedelta

        # 1. 自动生成租户编码（格式：TENANT_时间戳_随机数）
        timestamp = int(time.time())
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        tenant_code = f"TENANT_{timestamp}_{random_suffix}"

        # 2. 自动生成租户名称（格式：公司名称+的租户）
        tenant_name = f"{company_name}的租户"

        # 3. 自动生成其他租户信息
        # 过期时间：默认1年后
        expire_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")

        # 最大用户数：随机生成10-1000
        max_user_count = random.randint(10, 1000)

        # 4. 先创建租户
        try:
                tenant_id = db_client.insert_tenant(
                    tenant_code=tenant_code,
                    tenant_name=tenant_name,
                    status=1,  # 默认启用
                    expire_time=expire_date,
                    max_user_count=max_user_count,
                    remark=f"系统自动创建的租户，关联公司：{company_name}",
                    lang=lang,
                )

        except Exception as e:
            # 如果租户编码重复，重新生成
            if "Duplicate" in str(e) or "已存在" in str(e):
                # 重新生成租户编码
                timestamp = int(time.time())
                random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                tenant_code = f"TENANT_{timestamp}_{random_suffix}"

                tenant_id = db_client.insert_tenant(
                    tenant_code=tenant_code,
                    tenant_name=tenant_name,
                    status=1,
                    expire_time=expire_date,
                    max_user_count=max_user_count,
                    remark=f"系统自动创建的租户（重试），关联公司：{company_name}",
                    lang=lang,
                )
                logger.warning(f"租户编码重复，使用新编码创建：{tenant_code}")
            else:
                logger.error(f"创建租户失败: {str(e)}")
                raise

        # 5. 使用新创建的租户ID创建公司
        result = db_client.insert_company(
            company_name=company_name,
            tenant_id=tenant_id,
            establish_time=establish_time,
            address=address,
            contact_phone=contact_phone,
            remark=remark,
            create_default_entities=True,  # 默认为True
            lang=lang,
        )

        # 6. 根据是否创建了默认实体返回不同的消息
        if result.get("department_id") and result.get("position_id"):
            message = f"公司【{company_name}】新增成功，已自动创建租户【{tenant_name}】和默认部门、岗位"
        else:
            message = f"公司【{company_name}】新增成功，已自动创建租户【{tenant_name}】"

        return {
            "status": 200,
            "message": message,
            "results": {
                "company_id": result["company_id"],
                "company_name": company_name,
                "tenant_info": {
                    "tenant_id": tenant_id,
                    "tenant_code": tenant_code,
                    "tenant_name": tenant_name,
                    "expire_time": expire_date,
                    "max_user_count": max_user_count,
                    "status": 1
                },
                "default_department_id": result.get("department_id"),
                "default_department_name": result.get("default_department_name"),
                "default_position_id": result.get("position_id"),
                "default_position_name": result.get("default_position_name")
            }
        }

    except pymysql.err.IntegrityError as e:
        error_text = str(e)
        if "Duplicate entry" in error_text or "uk_company_name" in error_text:
            return {
                "status": 400,
                "message": f"已有同名公司：{company_name}",
                "results": None
            }

        logger.error(f"创建公司及租户失败: {str(e)}")
        return {
            "status": 500,
            "message": f"创建公司及租户失败: {str(e)}",
            "results": None
        }
    
    except Exception as e:
        logger.error(f"创建公司及租户失败: {str(e)}")
        return {
            "status": 500,
            "message": f"创建公司及租户失败: {str(e)}",
            "results": None
        }


async def delete_company(
        company_id: int,
        tenant_id: int = None,  # 可选：用于租户验证
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 查询公司信息
        company = db_client.query_company_by_id(company_id=company_id, lang=lang)
        if not company:
            return {
                "status": 404,
                "message": f"公司ID不存在: {company_id}",
                "results": None
            }

        # 如果提供了租户ID（ADMIN），验证公司是否属于该租户
        if tenant_id and company.get('tenant_id') != tenant_id:
            return {
                "status": 403,
                "message": f"无权删除此公司，公司属于租户{company.get('tenant_id')}",
                "results": None
            }

        # 检查是否存在下属部门
        departments = db_client.query_departments_by_company_id(company_id, lang=lang)
        if departments:
            department_names = [dept.get('department_name', '未知部门') for dept in departments[:3]]
            message = f"公司ID【{company_id}】存在下属部门"
            if len(departments) > 3:
                message += f"（{department_names[0]}等共{len(departments)}个部门）"
            else:
                message += f"（{'、'.join(department_names)}）"
            message += "，无法删除（请先删除关联部门）"
            return {
                "status": 400,
                "message": message,
                "results": None
            }

        db_client.delete_company(company_id=company_id, lang=lang)

        return {
            "status": 200,
            "message": f"公司ID【{company_id}】删除成功",
            "results": {
                "company_id": company_id,
                "tenant_id": company.get('tenant_id')
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
            "message": f"删除公司失败: {str(e)}",
            "results": None
        }


async def update_company(
        company_id: int,
        tenant_id: int = None,  # 可选：用于租户验证
        company_name: str = None,
        establish_time: str = None,
        address: str = None,
        contact_phone: str = None,
        remark: str = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 查询公司信息
        company = db_client.query_company_by_id(company_id=company_id, lang=lang)
        if not company:
            return {
                "status": 404,
                "message": f"公司ID不存在: {company_id}",
                "results": None
            }

        # 如果提供了租户ID，验证公司是否属于该租户
        if tenant_id and company.get('tenant_id') != tenant_id:
            return {
                "status": 403,
                "message": f"无权更新此公司，公司属于租户{company.get('tenant_id')}",
                "results": None
            }

        current_tenant_id = company.get('tenant_id')

        # 如果要修改公司名称，需要检查同一租户内是否重复
        if company_name and company_name != company.get('company_name'):
            existing = db_client.query_company_by_name_and_tenant(
                company_name=company_name,
                tenant_id=current_tenant_id,
                lang=lang,
            )
            if existing and existing.get('company_id') != company_id:
                return {
                    "status": 400,
                    "message": f"租户【{current_tenant_id}】下公司名称【{company_name}】已存在",
                    "results": None
                }

        update_data = {
            k: v for k, v in {
                "company_name": company_name,
                "establish_time": establish_time,
                "address": address,
                "contact_phone": contact_phone,
                "remark": remark
            }.items() if v is not None
        }

        if not update_data:
            return {
                "status": 400,
                "message": "未提供任何更新字段",
                "results": None
            }

        db_client.update_company(
            company_id=company_id,
            tenant_id=current_tenant_id,  # 传递当前租户ID用于验证
            lang=lang,
            **update_data
        )

        return {
            "status": 200,
            "message": f"公司ID【{company_id}】更新成功",
            "results": {
                "company_id": company_id,
                "tenant_id": current_tenant_id,
                "updated_fields": list(update_data.keys())
            }
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"更新公司失败: {str(e)}",
            "results": None
        }


async def query_company(
        tenant_id: int,  # 新增：租户ID（必填）
        company_id: int = None,
        company_name: str = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER (tenant_id=None) 不验证租户，直接查全局；ADMIN 必须有租户
        if tenant_id is not None:
            tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
            if not tenant:
                return {
                    "status": 400,
                    "message": f"租户ID【{tenant_id}】不存在",
                    "results": None
                }

        # 构建查询条件
        conditions = {}
        if tenant_id is not None:
            conditions['tenant_id'] = tenant_id  # OWNER 不加此条件，查全局

        if company_id is not None:
            conditions['company_id'] = company_id
        if company_name is not None:
            conditions['company_name__like'] = f'%{company_name}%'

        # 多条件并联查询
        results = db_client.query_companies_by_multiple_conditions(lang=lang, **conditions)

        return {
            "status": 200,
            "message": f"查询成功，共找到{len(results)}条公司记录",
            "results": results
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询公司失败: {str(e)}",
            "results": None
        }


# ------------------------------
# 公司表（company）分页查询（添加租户支持）
# ------------------------------
async def query_company_paginated(
        tenant_id: int,  # OWNER 传 None，ADMIN 传自身租户 ID
        company_id: int = None,
        company_name: str = None,
        address: str = None,
        contact_phone: str = None,
        page: int = 1,
        page_size: int = 10,
        lang: str = "zh",
) -> Dict:
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # OWNER (tenant_id=None) 查全局；ADMIN 必须验证租户
        if tenant_id is not None:
            tenant = db_client.query_tenant_by_id(tenant_id, lang=lang)
            if not tenant:
                return {
                    "status": 400,
                    "message": f"租户ID【{tenant_id}】不存在",
                    "results": None
                }

        # 校验分页参数
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        # 构建查询条件（OWNER 不加租户过滤）
        conditions = {}
        if tenant_id is not None:
            conditions['tenant_id'] = tenant_id

        if company_id is not None:
            conditions['company_id'] = company_id
        if company_name is not None:
            conditions['company_name__like'] = f'%{company_name}%'
        if address is not None:
            conditions['address__like'] = f'%{address}%'
        if contact_phone is not None:
            conditions['contact_phone__like'] = f'%{contact_phone}%'

        records: List[Dict] = db_client.query_companies_paginated(
            conditions=conditions,
            offset=offset,
            limit=page_size,
            lang=lang,
        )

        total = db_client.count_companies_by_conditions(lang=lang, **conditions)
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
            "message": f"查询公司失败: {str(e)}",
            "results": None
        }
