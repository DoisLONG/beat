# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import string
import random

from fastapi import HTTPException, UploadFile

from comps import CustomLogger
from comps.oss_manager import oss_manager
from comps.oss_manager.config import FILES_STORED_TYPE
from comps.oss_manager.minio_utils import save_upload_file_minio, get_share_url_by_file_uri
from comps.learn.file_access import apply_proxy_urls_to_course, apply_proxy_urls_to_course_list

logger = CustomLogger("course_route", os.getenv("LOG_LEVEL", "INFO"))

from typing import Dict, List, Optional, Union
from datetime import datetime
import json

from mysql_client import MySQLClient
from config import MYSQL_CONFIG
from comps.account.model import UserRole


# 统一的 current_user 解析：返回 (tenant_id, lang, effective_tenant_id, err_response)
# - tenant_id: JWT 原始 tenant_id（OWNER 也保留，用于回显）
# - lang: JWT.lang（zh/en/th），非法降级为 zh
# - effective_tenant_id: OWNER → None（mysql_client 跨租户查询），ADMIN/USER → 原 tenant_id
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


# course_routes.py

async def add_course_with_videos(
        title: str,
        code: str = None,
        category: str = None,
        cover_url: str = None,
        description: str = None,
        tags: List[str] = None,
        status: str = "draft",
        videos: List[Dict] = None,
        keywordslist: List[Dict] = None,
        position_id: int = None,
        current_user: Dict = None  # 从装饰器注入的用户信息（包含tenant_id、role、lang）
):
    """新增课程（从JWT Token获取租户ID和业务语种）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, lang, _effective_tenant_id, err = _resolve_user_context(current_user)
        if err:
            return err

        # 生成课程ID
        random_chars = ''.join(random.choices(string.ascii_uppercase, k=3))
        random_nums = ''.join(random.choices(string.digits, k=3))
        random_suffix = f"{random_chars}{random_nums}"
        course_id = f"COURSE_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random_suffix}"

        # 转换tags为JSON字符串
        tags_json = json.dumps(tags) if tags else None

        # 转换keywordslist为JSON字符串
        keywordslist_json = json.dumps(keywordslist, ensure_ascii=False) if keywordslist else None

        # 验证视频数据
        if videos:
            for video in videos:
                if not video.get('title'):
                    return {
                        "code": 400,
                        "message": "视频标题不能为空",
                        "data": {}
                    }
                if not video.get('video_url'):
                    return {
                        "code": 400,
                        "message": "视频URL不能为空",
                        "data": {}
                    }

        # 验证岗位是否存在
        if position_id:
            position_info = db_client.query_position_by_id(position_id, lang=lang)
            tenant_id = position_info.get("tenant_id")

        result = db_client.insert_course_with_videos(
            course_id=course_id,
            title=title,
            code=code,
            category=category,
            cover_url=cover_url,
            description=description,
            tags=tags_json,
            status=status,
            videos=videos,
            keywordslist=keywordslist_json,
            position_id=position_id,
            tenant_id=tenant_id,  # 从JWT中获取的tenant_id（如果传 position_id 则取岗位所属租户）
            lang=lang
        )

        return {
            "code": 0,
            "message": "success",
            "data": {
                "course_id": result.get("course_id"),
                "version_code": result.get("version_code", "v1"),
                "tenant_id": tenant_id,
                "created_by": current_user.get('id')
            }
        }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"新增失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"新增课程失败: {str(e)}",
            "data": {}
        }


async def update_course_with_videos(
        course_id: str,
        title: str = None,
        category: str = None,
        description: str = None,
        status: str = None,
        videos: List[Dict] = None,
        keywordslist: List[Dict] = None,
        position_id: int = None,
        current_user: Dict = None
):
    """更新课程（从JWT Token获取租户ID和业务语种）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, lang, _effective_tenant_id, err = _resolve_user_context(current_user)
        if err:
            return err

        # 首先根据ID获取course_id（包含租户验证）
        # course = db_client.query_course_info(course_id, tenant_id)
        # if not course:
        #     return {
        #         "code": 404,
        #         "message": "课程不存在或无权访问",
        #         "data": {}
        #     }

        # 验证视频数据
        if videos is not None:
            for video in videos:
                if not video.get('title'):
                    return {
                        "code": 400,
                        "message": "视频标题不能为空",
                        "data": {}
                    }
                if not video.get('video_url'):
                    return {
                        "code": 400,
                        "message": "视频URL不能为空",
                        "data": {}
                    }

        # 转换keywordslist为JSON字符串
        keywordslist_json = json.dumps(keywordslist, ensure_ascii=False) if keywordslist is not None else None

        # 验证岗位是否存在
        # if position_id is not None:
        #     position = db_client.query_position_by_id(position_id, tenant_id, lang=lang)  # 更新查询方法
        #     if not position:
        #         return {
        #             "code": 404,
        #             "message": f"岗位ID【{position_id}】不存在",
        #             "data": {}
        #         }

        result = db_client.update_course_with_videos(
            course_id=course_id,
            title=title,
            category=category,
            description=description,
            status=status,
            videos=videos,
            keywordslist=keywordslist_json,
            position_id=position_id,
            tenant_id=tenant_id,  # 从JWT中获取的tenant_id
            lang=lang
        )

        if result.get("success"):
            return {
                "code": 0,
                "message": "success",
                "data": {
                    "old_version": result.get("old_version"),
                    "new_version": result.get("new_version"),
                    "tenant_id": result.get("tenant_id"),
                    "updated_by": current_user.get('id')
                }
            }
        else:
            return {
                "code": 500,
                "message": "更新课程失败",
                "data": {}
            }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"更新失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"更新课程失败: {str(e)}",
            "data": {}
        }


async def delete_course(course_id: str, current_user: Dict = None):
    """删除课程（从JWT Token获取租户ID和业务语种）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, lang, _effective_tenant_id, err = _resolve_user_context(current_user)
        if err:
            return err

        success = db_client.delete_course_logic(course_id=course_id, tenant_id=tenant_id, lang=lang)

        if success:
            return {
                "code": 0,
                "message": "success",
                "data": {
                    "deleted_by": current_user.get('id')
                }
            }
        else:
            return {
                "code": 500,
                "message": "删除课程失败",
                "data": {}
            }
    except ValueError as ve:
        return {
            "code": 400,
            "message": f"删除失败: {str(ve)}",
            "data": {}
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"删除课程失败: {str(e)}",
            "data": {}
        }


async def get_course_list(
        keyword: str = None,
        category: str = None,
        status: str = None,
        position_id: int = None,
        department_id: int = None,
        company_id: int = None,
        position_name: str = None,
        department_name: str = None,
        company_name: str = None,
        current_user: Dict = None,
        page: int = 1,
        page_size: int = 20
):
    """课程列表查询（从JWT Token获取租户ID和业务语种；OWNER 跨租户全量）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, lang, effective_tenant_id, err = _resolve_user_context(current_user)
        if err:
            return err

        offset = (page - 1) * page_size
        result = db_client.query_course_list(
            keyword=keyword,
            category=category,
            status=status,
            position_id=position_id,
            department_id=department_id,
            company_id=company_id,
            position_name=position_name,
            department_name=department_name,
            company_name=company_name,
            tenant_id=effective_tenant_id,  # OWNER 传 None 跨租户全量，其他角色按自身 tenant_id 隔离
            offset=offset,
            limit=page_size,
            lang=lang
        )

        # items = result.get("items", [])

        # for item in items:
        #     if "cover_url" in item and item["cover_url"]:
        #         try:
        #             if FILES_STORED_TYPE == "oss":
        #                 oss_url = oss_manager.get_presigned_url(item["cover_url"])
        #             else:
        #                 oss_url = await get_share_url_by_file_uri(item["cover_url"],expires_days=1)
        #             item["cover_url"] = oss_url
        #         except Exception as e:
        #             logger.error(f"获取签名失败，文件路径: {item['cover_url']}, 错误: {e}")
        #             continue

        items = apply_proxy_urls_to_course_list(result.get("items", []))

        return {
            "code": 0,
            "message": "success",
            "data": {
                "total": result.get("total", 0),
                "page": page,
                "page_size": page_size,
                "tenant_id": tenant_id,
                "items": items
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"查询课程列表失败: {str(e)}",
            "data": {}
        }


async def get_course_info(course_id: str, current_user: Dict = None):
    """课程详情（从JWT Token获取租户ID和业务语种；OWNER 跨租户）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        tenant_id, lang, effective_tenant_id, err = _resolve_user_context(current_user)
        if err:
            return err

        course_info = db_client.query_course_info(course_id, effective_tenant_id, lang=lang)

        if course_info:
            apply_proxy_urls_to_course(course_info)
            # 解析JSON字段
            if course_info.get('keywordslist') and isinstance(course_info['keywordslist'], str):
                try:
                    course_info['keywordslist'] = json.loads(course_info['keywordslist'])
                except:
                    course_info['keywordslist'] = []

            if course_info.get('tags') and isinstance(course_info['tags'], str):
                try:
                    course_info['tags'] = json.loads(course_info['tags'])
                except:
                    course_info['tags'] = []

            return {
                "code": 0,
                "message": "success",
                "data": course_info
            }
        else:
            return {
                "code": 404,
                "message": "课程不存在或无权访问",
                "data": {}
            }
    except Exception as e:
        return {
            "code": 500,
            "message": f"查询课程详情失败: {str(e)}",
            "data": {}
        }

async def sign_oss_response(uri_or_key: str, expires: int = 3600) -> dict:
    try:
        if FILES_STORED_TYPE == "oss":
            url = oss_manager.get_presigned_url(uri_or_key, expiration=expires)
        else:
            url = await get_share_url_by_file_uri(uri_or_key,expires_days=1)

        return {
            "code": 0,
            "message": "success",
            "data": url
        }

    except Exception as e:
        logger.error(f"链接获取失败, 错误: {e}")
        return {
            "code": 500,
            "message": f"链接获取失败: {str(e)}",
            "data": {}
        }

async def upload_oss_response(file:UploadFile) -> Optional[dict]:
    try:
        file = await add_timestamp_to_file(file)
        if FILES_STORED_TYPE == "oss":
            _, uri, _ = await oss_manager.upload_large_file(file_obj=file,position_id="-1")
        else:
            _, _, uri = await save_upload_file_minio(file=file,post_id="-1")
        return {
            "code": 0,
            "message": "success",
            "data": uri
        }

    except Exception as e:
        logger.error(f"链接获取失败, 错误: {e}")
        return {
            "code": 500,
            "message": f"链接获取失败: {str(e)}",
            "data": {}
        }


async def add_timestamp_to_file(file: UploadFile) -> UploadFile:
    """
    给 UploadFile 的文件名加上时间戳，返回同一个 file 对象，filename 已更新
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    original_filename = file.filename
    file.filename = f"{timestamp}_{original_filename}"
    return file


def _validate_position_tenant(db_client: MySQLClient, position_id: int, tenant_id: int, lang: str = "zh") -> Dict:
    position = db_client.query_position_by_id(position_id, tenant_id=tenant_id, lang=lang)
    if not position:
        raise HTTPException(status_code=403, detail=f"岗位ID【{position_id}】不存在或无权访问")
    return position
