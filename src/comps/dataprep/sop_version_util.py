# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from typing import List

from mysql_client import MySQLClient
from config import MYSQL_CONFIG
from comps import CustomLogger
import json
logger = CustomLogger("dataprep-sop-version-util", os.getenv("LOG_LEVEL", "INFO"))

def create_sop_version_filename(
        content: List[dict],
        file_name:str = None,
        version_name: str = None,
        sop_id: int = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)
    try:
        # 获取 sop_info 记录信息（按语种路由到正确的 sop_info 表）
        # # 如果提供了 file_name，优先按 file_name 查询
        # sop_info_record = db_client.query_sop_info_by_filename(file_name)
        sop_info_record = db_client.query_sop_info_by_id(sop_id, lang=lang)
        # if sop_info_record:
        #     sop_info_id = sop_info_record['id']  # 获取对应的 sop_info_id

        # # 使用 sop_info 中的 filename
        # file_name = sop_info_record['filename']
        current_version = sop_info_record['sop_version']
        logger.info(f"开始创建SOP版本: file_name={file_name}, sop_info_id={sop_id}, lang={lang}")
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

        # 使用自动生成的版本号插入新记录（路由到对应语种版本表）
        version_id = db_client.insert_sop_version(
            file_name=file_name,
            version_number=new_version_number,
            content=content_json,
            sop_info_id=sop_id,
            version_name=version_name,
            lang=lang,
        )

        # 更新 sop_info 语种表中的版本号
        db_client.update_sop_info_version_by_id(
            sop_info_id=sop_id,
            sop_version=new_version_number,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"文件【{file_name}】新增版本【{new_version_number}】成功，并更新了SOP信息版本号",
            "results": {
                "file_name": file_name,
                "version_number": new_version_number,
                "version_name": version_name,
                "version_id": version_id,
                "sop_info_id": sop_id
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
            "message": f"新增SOP版本失败: {str(e)}",
            "results": None
        }

async def create_sop_version(
        sop_info_id: int,
        content: List[dict],
        version_name: str = None,
        lang: str = "zh",
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 获取 sop_info 记录信息（按语种路由到正确的 sop_info 表）
        sop_info_record = db_client.query_sop_info_by_id(sop_info_id, lang=lang)
        if not sop_info_record:
            raise ValueError(f"SOP信息ID不存在: {sop_info_id}（lang={lang}）")

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

        # 使用自动生成的版本号插入新记录（路由到对应语种版本表）
        version_id = db_client.insert_sop_version(
            file_name=file_name,
            version_number=new_version_number,
            content=content_json,
            sop_info_id=sop_info_id,
            version_name=version_name,
            lang=lang,
        )

        # 更新 sop_info 语种表中的版本号
        db_client.update_sop_info_version_by_id(
            sop_info_id=sop_info_id,
            sop_version=new_version_number,
            lang=lang,
        )

        return {
            "status": 200,
            "message": f"文件【{file_name}】新增版本【{new_version_number}】成功，并更新了SOP信息版本号",
            "results": {
                "file_name": file_name,
                "version_number": new_version_number,
                "version_name": version_name,
                "version_id": version_id,
                "sop_info_id": sop_info_id
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
            "message": f"新增SOP版本失败: {str(e)}",
            "results": None
        }


async def delete_sop_version(version_id: int):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        db_client.delete_sop_version(version_id=version_id)

        return {
            "status": 200,
            "message": f"版本ID【{version_id}】删除成功",
            "results": {"version_id": version_id}
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
        content: str = None
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        db_client.update_sop_version(
            version_id=version_id,
            file_name=file_name,
            version_number=version_number,
            version_name=version_name,
            content=content
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
            "results": {"version_id": version_id, "updated_fields": updated_fields}
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
            "message": f"更新SOP版本失败: {str(e)}",
            "results": None
        }


async def get_sop_version(
        version_id: int = None,
        file_name: str = None,
        version_number: str = None
):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        # 构建查询条件
        conditions = {}
        if version_id is not None:
            conditions['version_id'] = version_id
        if file_name is not None:
            conditions['file_name'] = file_name
        if version_number is not None:
            conditions['version_number'] = version_number

        # 根据条件数量执行不同的查询
        results = db_client.query_sop_versions_by_multiple_conditions(**conditions)

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
