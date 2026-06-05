# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# learning_progress_routes.py

from typing import Dict, Optional
from datetime import datetime
import uuid

from mysql_client import MySQLClient
from config import MYSQL_CONFIG


def _extract_auth(current_user: Dict):
    """从 JWT 注入的用户信息中提取 tenant_id / user_id / lang（lang 非法降级为 zh）"""
    if not current_user:
        return None, None, None, {
            "code": 401,
            "message": "用户未认证",
            "data": {}
        }

    tenant_id = current_user.get('tenant_id')
    user_id = current_user.get('id')

    if not tenant_id:
        return None, None, None, {
            "code": 400,
            "message": "用户未关联租户",
            "data": {}
        }

    if not user_id:
        return None, None, None, {
            "code": 401,
            "message": "用户身份缺失",
            "data": {}
        }

    lang = current_user.get('lang') or 'zh'
    if lang not in ('zh', 'en', 'th'):
        lang = 'zh'

    return tenant_id, user_id, lang, None


async def start_learning_video(
        course_id: str,
        video_id: str,
        from_position: int = 0,
        current_user: Dict = None
):
    """5.1 开始学习（视频）。用户信息统一从 JWT 取"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, user_id, lang, err = _extract_auth(current_user)
        if err:
            return err

        # 生成会话ID
        session_id = f"SESSION_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

        result = db_client.insert_learning_session(
            session_id=session_id,
            user_id=user_id,
            course_id=course_id,
            video_id=video_id,
            from_position=from_position,
            tenant_id=tenant_id,
            lang=lang
        )

        return {
            "code": 0,
            "message": "success",
            "data": result
        }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"开始学习失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"开始学习失败: {str(e)}",
            "data": {}
        }


async def heartbeat_learning_video(
        session_id: str,
        session_watch_seconds: int,
        position: int = 0,
        is_completed: bool = False,
        current_user: Dict = None
):
    """5.2 视频学习心跳上报。

    session_watch_seconds 语义为“本次会话累计观看时长”，
    服务端按差值累计学习时长，避免重复计时。
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, user_id, lang, err = _extract_auth(current_user)
        if err:
            return err

        if session_watch_seconds is None or int(session_watch_seconds) < 0:
            return {
                "code": 400,
                "message": "session_watch_seconds 非法",
                "data": {}
            }

        if position is None or int(position) < 0:
            return {
                "code": 400,
                "message": "position 非法",
                "data": {}
            }

        result = db_client.heartbeat_learning_session(
            session_id=session_id,
            session_watch_seconds=int(session_watch_seconds),
            position=int(position),
            is_completed=bool(is_completed),
            tenant_id=tenant_id,
            user_id=user_id,
            lang=lang,
        )

        return {
            "code": 0,
            "message": "success",
            "data": result
        }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"心跳上报失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"心跳上报失败: {str(e)}",
            "data": {}
        }


async def end_learning_video(
        session_id: str,
        session_watch_seconds: int,
        position: int = 0,
        is_completed: bool = False,
        current_user: Dict = None
):
    """5.3 结束学习（视频）。session_watch_seconds 为“本次会话累计观看时长”，按差值收尾"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, user_id, lang, err = _extract_auth(current_user)
        if err:
            return err

        if session_watch_seconds is None or int(session_watch_seconds) < 0:
            return {
                "code": 400,
                "message": "session_watch_seconds 非法",
                "data": {}
            }

        if position is None or int(position) < 0:
            return {
                "code": 400,
                "message": "position 非法",
                "data": {}
            }

        result = db_client.end_learning_session(
            session_id=session_id,
            session_watch_seconds=int(session_watch_seconds),
            position=int(position),
            is_completed=bool(is_completed),
            tenant_id=tenant_id,
            user_id=user_id,
            lang=lang,
        )

        return {
            "code": 0,
            "message": "success",
            "data": result
        }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"结束学习失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"结束学习失败: {str(e)}",
            "data": {}
        }


async def get_user_course_progress(
        course_id: str,
        current_user: Dict = None
):
    """5.4 查询课程学习进度（个人）。固定查询当前登录用户的进度"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, user_id, lang, err = _extract_auth(current_user)
        if err:
            return err

        result = db_client.query_course_learning_progress(
            user_id=user_id,
            course_id=course_id,
            tenant_id=tenant_id,
            lang=lang
        )

        return {
            "code": 0,
            "message": "success",
            "data": result
        }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"查询学习进度失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"查询学习进度失败: {str(e)}",
            "data": {}
        }


async def get_user_learning_progress_list(
        course_id: str = None,
        user_id: int = None,
        current_user: Dict = None,
        page: int = 1,
        page_size: int = 20
):
    """5.5 查询用户课程学习进度列表。

    - user_id 为空：查询当前登录用户
    - user_id 有值：查询指定用户
    - 不做租户归属校验（由上层可见性控制）
    """
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, auth_user_id, lang, err = _extract_auth(current_user)
        if err:
            return err

        target_user_id = int(user_id) if user_id is not None else int(auth_user_id)

        offset = (page - 1) * page_size
        result = db_client.query_user_course_progress_list(
            user_id=target_user_id,
            course_id=course_id,
            tenant_id=None,
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
                "tenant_id": tenant_id,
                "items": result.get("items", [])
            }
        }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"查询用户学习进度失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"查询用户学习进度失败: {str(e)}",
            "data": {}
        }


async def get_tenant_learning_progress_list(
        current_user: Dict = None,
        page: int = 1,
        page_size: int = 20,
):
    """管理端：查询当前租户（或全租户）全部用户课程学习进度列表。"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, _, lang, err = _extract_auth(current_user)
        if err:
            return err

        effective_tenant_id = None if int(tenant_id) == 1 else int(tenant_id)
        offset = (page - 1) * page_size
        result = db_client.query_tenant_course_progress_list(
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
            "message": f"查询管理端学习进度失败: {str(e)}",
            "data": {}
        }
