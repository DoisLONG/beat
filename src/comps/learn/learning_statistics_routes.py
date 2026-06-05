# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, Optional
from datetime import datetime, timedelta

from mysql_client import MySQLClient
from config import MYSQL_CONFIG


def _resolve_lang(current_user: Optional[Dict]) -> str:
    lang = (current_user or {}).get('lang') or 'zh'
    if lang not in ('zh', 'en', 'th'):
        lang = 'zh'
    return lang


async def get_video_learning_statistics(
        start_date: str = None,
        end_date: str = None,
        course_id: str = None,
        current_user: Dict = None,  # 新增：当前用户信息
        page: int = 1,
        page_size: int = 20
):
    """视频学习统计分页查询（6.1 管理端 - 用户视频学习时长统计）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 从当前用户信息获取租户ID
        if not current_user:
            return {
                "code": 401,
                "message": "用户未认证",
                "data": {}
            }

        tenant_id = current_user.get('tenant_id')
        if not tenant_id:
            return {
                "code": 400,
                "message": "用户未关联租户",
                "data": {}
            }

        lang = _resolve_lang(current_user)

        offset = (page - 1) * page_size
        result = db_client.query_video_learning_statistics(
            start_date=start_date,
            end_date=end_date,
            course_id=course_id,
            tenant_id=tenant_id,  # 传递租户ID
            offset=offset,
            limit=page_size,
            lang=lang
        )

        return {
            "code": 0,
            "message": "success",
            "data": {
                "total": result.get("total", 0),
                "page": page,
                "page_size": page_size,
                "items": result.get("items", [])
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"查询学习统计失败: {str(e)}",
            "data": {}
        }


async def get_user_learning_summary(
        user_id: int = None,
        current_user: Dict = None  # 新增：当前用户信息
):
    """用户学习统计概览。

    - user_id 为空：查询当前登录用户
    - user_id 有值：查询指定用户
    - 不做租户归属校验（由上层可见性控制）
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 从当前用户信息获取租户ID
        if not current_user:
            return {
                "code": 401,
                "message": "用户未认证",
                "data": {}
            }

        tenant_id = current_user.get('tenant_id')
        if not tenant_id:
            return {
                "code": 400,
                "message": "用户未关联租户",
                "data": {}
            }

        auth_user_id = current_user.get('id')
        if not auth_user_id:
            return {
                "code": 401,
                "message": "用户身份缺失",
                "data": {}
            }

        lang = _resolve_lang(current_user)

        target_user_id = int(user_id) if user_id is not None else int(auth_user_id)

        result = db_client.query_user_learning_summary(
            user_id=target_user_id,
            tenant_id=None,
            lang=lang
        )

        return {
            "code": 0,
            "message": "success",
            "data": {
                **result,
                "tenant_id": tenant_id
            }
        }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"获取学习统计失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"获取学习统计失败: {str(e)}",
            "data": {}
        }


async def get_tenant_learning_summary(
        current_user: Dict = None,
        page: int = 1,
        page_size: int = 20,
):
    """管理端：查询当前租户（或全租户）全部用户学习汇总。"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        if not current_user:
            return {
                "code": 401,
                "message": "用户未认证",
                "data": {}
            }

        tenant_id = current_user.get('tenant_id')
        if not tenant_id:
            return {
                "code": 400,
                "message": "用户未关联租户",
                "data": {}
            }

        lang = _resolve_lang(current_user)

        effective_tenant_id = None if int(tenant_id) == 1 else int(tenant_id)
        offset = (page - 1) * page_size
        result = db_client.query_tenant_learning_summary(
            tenant_id=effective_tenant_id,
            offset=offset,
            limit=page_size,
            lang=lang,
        )

        return {
            "code": 0,
            "message": "success",
            "data": {
                "tenant_id": effective_tenant_id if effective_tenant_id is not None else 1,
                "total": result.get("total", 0),
                "page": page,
                "page_size": page_size,
                "items": result.get("items", []),
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"获取管理端学习统计失败: {str(e)}",
            "data": {}
        }
