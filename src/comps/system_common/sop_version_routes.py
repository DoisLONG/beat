# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from mysql_client import MySQLClient
from config import MYSQL_CONFIG
import json


async def create_sop_version(
        sop_info_id: int,
        content: List[dict],
        version_name: str = None,
        lang: str = "zh",
):
    """创建SOP版本（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    # 参数验证

    try:

        # 获取 sop_info 记录信息，验证租户权限
        sop_info_record = db_client.query_sop_info_by_id_and_tenant(sop_info_id, lang=lang)
        if not sop_info_record:
            return {
                "status": 404,
                "message": f"SOP信息ID【{sop_info_id}】不存在",
                "results": None
            }

        # 使用 sop_info 中的 filename
        file_name = sop_info_record['filename']
        current_version = sop_info_record['sop_version']

        # 生成新版本号：基于当前 sop_version 累加
        if current_version and current_version.startswith('v'):
            try:
                # 提取 v 后面的数字并累加
                current_version_num = int(current_version[1:])
                new_version_number = f"v{current_version_num + 1}"
            except ValueError:
                # 如果解析失败，从 v1 开始
                new_version_number = "v1"
        else:
            # 如果没有当前版本或格式不对，从 v1 开始
            new_version_number = "v1"

        content_json = json.dumps(content, ensure_ascii=False)

        # 使用自动生成的版本号插入新记录
        version_id = db_client.insert_sop_version(
            file_name=file_name,
            version_number=new_version_number,
            content=content_json,
            version_name=version_name,
            sop_info_id=sop_info_id,
            lang=lang,
        )

        # 更新 sop_info 表中的版本号
        db_client.update_sop_info_version_by_id(
            sop_info_id=sop_info_id,
            sop_version=new_version_number,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"文件【{file_name}】新增版本【{new_version_number}】成功",
            "results": {
                "file_name": file_name,
                "version_number": new_version_number,
                "version_name": version_name,
                "version_id": version_id,
                "sop_info_id": sop_info_id
            }
        }
    except ValueError as ve:
        error_msg = str(ve)
        if "Duplicate entry" in error_msg and "uk_tenant_file_version" in error_msg:
            return {
                "status": 400,
                "message": f"文件【{file_name}】版本号【{new_version_number}】已存在",
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
            "message": f"新增SOP版本失败: {str(e)}",
            "results": None
        }


async def delete_sop_version(
        version_id: int,
        lang: str = "zh",
):
    """删除SOP版本（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 先验证版本是否存在且属于该租户
        version = db_client.query_sop_version_by_id_and_tenant(version_id, lang=lang)
        if not version:
            return {
                "status": 404,
                "message": f"版本ID【{version_id}】不存在或无权删除",
                "results": None
            }

        # 获取关联的sop_info_id（如果有）
        sop_info_id = version.get('sop_info_id')

        db_client.delete_sop_version(
            version_id=version_id,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"版本ID【{version_id}】删除成功",
            "results": {
                "version_id": version_id,
                "sop_info_id": sop_info_id
            }
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
            "message": f"删除SOP版本失败: {str(e)}",
            "results": None
        }


async def update_sop_version(
        version_id: int,
        file_name: str = None,
        version_number: str = None,
        version_name: str = None,
        content: str = None,
        lang: str = "zh",
):
    """更新SOP版本信息（包含租户验证）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 验证版本是否存在且属于该租户
        version = db_client.query_sop_version_by_id_and_tenant(version_id, lang=lang)
        # if not version:
        #     return {
        #         "status": 404,
        #         "message": f"版本ID【{version_id}】不存在或无权更新",
        #         "results": None
        #     }

        # 如果要更新文件名，检查新文件名在租户内是否已存在其他版本
        if file_name is not None and file_name != version.get('file_name'):
            # 检查同一租户内是否存在其他同名的版本记录（当前版本除外）
            existing = db_client.query_sop_versions_by_file_and_tenant(
                file_name=file_name,
                exclude_version_id=version_id,
                lang=lang,
            )
            if existing:
                return {
                    "status": 400,
                    "message": f"已存在文件名【{file_name}】的版本记录",
                    "results": None
                }

        db_client.update_sop_version(
            version_id=version_id,
            file_name=file_name,
            version_number=version_number,
            version_name=version_name,
            content=content,
            lang=lang,
        )

        updated_fields = [k for k, v in {
            "file_name": file_name,
            "version_number": version_number,
            "version_name": version_name,
            "content": content
        }.items() if v is not None]

        return {
            "status": 200,
            "message": f"版本ID【{version_id}】更新成功",
            "results": {
                "version_id": version_id,
                "updated_fields": updated_fields
            }
        }
    except ValueError as ve:
        error_msg = str(ve)
        if "Duplicate entry" in error_msg and "uk_tenant_file_version" in error_msg:
            return {
                "status": 400,
                "message": f"文件【{file_name}】版本号【{version_number}】已存在",
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
            "message": f"更新SOP版本失败: {str(e)}",
            "results": None
        }


async def get_sop_version(
        version_id: int = None,
        file_name: str = None,
        version_number: str = None,
        sop_info_id: int = None,  # 新增：支持按sop_info_id查询
        lang: str = "zh",
):
    """查询SOP版本（包含租户筛选）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 构建查询条件
        conditions = {}  # 必须包含租户ID

        if version_id is not None:
            conditions['version_id'] = version_id
        if file_name is not None:
            conditions['file_name'] = file_name
        if version_number is not None:
            conditions['version_number'] = version_number
        if sop_info_id is not None:
            conditions['sop_info_id'] = sop_info_id

        # 执行查询
        results = db_client.query_sop_versions_by_multiple_conditions(lang=lang, **conditions)

        # 解析JSON内容（如果需要）
        for item in results:
            if 'content' in item and isinstance(item['content'], str):
                try:
                    item['content'] = json.loads(item['content'])
                except:
                    pass  # 保持原样

        return {
            "status": 200,
            "message": f"查询成功，共找到{len(results)}条版本记录",
            "results": results
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询SOP版本失败: {str(e)}",
            "results": None
        }


# 新增：SOP版本分页查询
async def get_sop_versions_paginated(
        tenant_id: int,
        file_name: str = None,
        version_number: str = None,
        sop_info_id: int = None,
        page: int = 1,
        page_size: int = 10,
        lang: str = "zh",
):
    """SOP版本分页查询（包含租户筛选）"""
    db_client = MySQLClient(MYSQL_CONFIG)

    if not tenant_id:
        return {
            "status": 400,
            "message": "租户ID不能为空",
            "results": None
        }

    try:
        # 构建查询条件
        conditions = {'tenant_id': tenant_id}

        if file_name is not None:
            conditions['file_name__like'] = f'%{file_name}%'  # 模糊查询
        if version_number is not None:
            conditions['version_number'] = version_number
        if sop_info_id is not None:
            conditions['sop_info_id'] = sop_info_id

        # 计算分页偏移
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        # 执行分页查询
        results = db_client.query_sop_versions_paginated(
            conditions=conditions,
            offset=offset,
            limit=page_size,
            lang=lang,
        )

        # 查询总记录数
        total = db_client.count_sop_versions(lang=lang, **conditions)

        # 解析JSON内容
        for item in results:
            if 'content' in item and isinstance(item['content'], str):
                try:
                    item['content'] = json.loads(item['content'])
                except:
                    pass  # 保持原样

        return {
            "status": 200,
            "message": "查询成功",
            "results": {
                "tenant_id": tenant_id,
                "records": results,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询SOP版本失败: {str(e)}",
            "results": None
        }
