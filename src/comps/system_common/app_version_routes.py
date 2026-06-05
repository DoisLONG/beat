# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import time
import mimetypes
import os
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse

from config import MYSQL_CONFIG
from mysql_client import MySQLClient
from comps.oss_manager import oss_manager
from comps.oss_manager.config import FILES_STORED_TYPE
from comps.oss_manager.minio_utils import (
    save_upload_file_minio,
    get_object_metadata_by_uri,
    iter_object_by_uri,
)


MIN_VERSION_CODE = 2
MAX_VERSION_CODE = 2147483647


def _build_empty_data() -> dict:
    return {
        "describe_zh": "",
        "describe_en": "",
        "describe_th": "",
        "edition_url": "",
        "edition_force": 0,
        "package_type": 1,
        "edition_issue": 0,
        "edition_version_code": 0,
        "edition_name": "",
        "edition_silence": 0,
    }


def _validate_binary_flag(name: str, value: int) -> Optional[dict]:
    if value not in (0, 1):
        return {
            "status": 400,
            "message": f"{name} 仅支持 0 或 1",
            "results": None,
        }
    return None


def _validate_version_code(version_code: int) -> Optional[dict]:
    if version_code < MIN_VERSION_CODE or version_code > MAX_VERSION_CODE:
        return {
            "status": 400,
            "message": f"edition_version_code 超出范围，必须在 {MIN_VERSION_CODE}-{MAX_VERSION_CODE} 之间",
            "results": None,
        }
    return None


def _validate_package_url(package_type: int, edition_url: str) -> Optional[dict]:
    url = (edition_url or "").strip().lower()
    if not url:
        return {"status": 400, "message": "edition_url 不能为空", "results": None}

    if package_type == 1 and not url.endswith(".wgt"):
        return {
            "status": 400,
            "message": "package_type=1 时，edition_url 必须指向 .wgt 文件",
            "results": None,
        }

    if package_type == 0 and not url.endswith(".apk"):
        return {
            "status": 400,
            "message": "package_type=0 时，edition_url 必须指向 .apk 文件",
            "results": None,
        }
    return None


async def _build_client_download_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return ""
    if url.startswith(("minio://", "oss://")):
        return ""
    return url


def _build_app_version_download_url(version_id: int) -> str:
    if int(version_id or 0) <= 0:
        return ""
    return f"/v1/app_version/download?id={version_id}"


def _parse_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    if not range_header.startswith("bytes="):
        raise ValueError("仅支持 bytes Range")

    range_value = range_header[6:].strip()
    if "," in range_value:
        raise ValueError("暂不支持多段 Range")

    start_text, sep, end_text = range_value.partition("-")
    if not sep or (start_text == "" and end_text == ""):
        raise ValueError("非法 Range 格式")

    if start_text == "":
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("非法 Range 长度")
        if suffix_length >= file_size:
            return 0, file_size - 1
        return file_size - suffix_length, file_size - 1

    start = int(start_text)
    if start < 0 or start >= file_size:
        raise ValueError("Range 起始位置越界")

    if end_text == "":
        return start, file_size - 1

    end = int(end_text)
    if end < start:
        raise ValueError("Range 结束位置非法")
    return start, min(end, file_size - 1)


def _guess_filename(file_uri: str, fallback: str = "app_version") -> str:
    cleaned = (file_uri or "").split("?", 1)[0].rstrip("/")
    tail = cleaned.rsplit("/", 1)[-1] if cleaned else ""
    return os.path.basename(tail) or fallback


def _build_content_disposition(filename: str) -> str:
    ascii_filename = "".join(
        ch if ord(ch) < 128 and ch not in {'"', "\\"} else "_"
        for ch in filename
    ) or "download"
    return f'attachment; filename="{ascii_filename}"'


def _build_streaming_response(
    decoded_uri: str,
    content_type: str,
    filename: str,
    size: int | None,
    range_header: str | None,
):
    response_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": _build_content_disposition(filename),
        "Cache-Control": "private, max-age=300",
    }

    if size is None or range_header is None:
        if size is not None:
            response_headers["Content-Length"] = str(size)
        if decoded_uri.startswith("minio://"):
            return StreamingResponse(
                iter_object_by_uri(decoded_uri),
                media_type=content_type,
                headers=response_headers,
            )
        return StreamingResponse(
            oss_manager.iter_object(decoded_uri),
            media_type=content_type,
            headers=response_headers,
        )

    try:
        start, end = _parse_range_header(range_header, size)
    except ValueError as exc:
        raise HTTPException(
            status_code=416,
            detail=str(exc),
            headers={"Content-Range": f"bytes */{size}"},
        ) from exc

    content_length = end - start + 1
    response_headers["Content-Length"] = str(content_length)
    response_headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    if decoded_uri.startswith("minio://"):
        iterator = iter_object_by_uri(decoded_uri, offset=start, length=content_length)
    else:
        iterator = oss_manager.iter_object(decoded_uri, offset=start, length=content_length)

    return StreamingResponse(
        iterator,
        media_type=content_type,
        headers=response_headers,
        status_code=206,
    )


async def get_app_version_current(current_version_code: Optional[int] = None):
    db_client = MySQLClient(MYSQL_CONFIG)
    try:
        latest = db_client.query_latest_active_app_version()
        if not latest:
            return {
                "status": 200,
                "message": "当前无可用发布版本",
                "need_update": 0,
                "data": _build_empty_data(),
            }

        latest_code = int(latest.get("edition_version_code") or 0)
        need_update = 0
        if current_version_code is not None:
            need_update = 1 if latest_code > int(current_version_code) else 0

        latest_id = int(latest.get("id") or 0)
        client_download_url = _build_app_version_download_url(latest_id)
        if not client_download_url:
            client_download_url = await _build_client_download_url(latest.get("edition_url") or "")

        return {
            "status": 200,
            "message": "查询成功",
            "need_update": need_update,
            "data": {
                "describe_zh": latest.get("describe_zh") or "",
                "describe_en": latest.get("describe_en") or "",
                "describe_th": latest.get("describe_th") or "",
                "edition_url": client_download_url,
                "edition_force": int(latest.get("edition_force") or 0),
                "package_type": int(latest.get("package_type") or 1),
                "edition_issue": int(latest.get("edition_issue") or 0),
                "edition_version_code": latest_code,
                "edition_name": latest.get("edition_name") or "",
                "edition_silence": int(latest.get("edition_silence") or 0),
                "id": latest_id,
            },
        }
    except Exception as e:
        return {
            "status": 500,
            "message": f"查询客户端版本失败: {str(e)}",
            "data": _build_empty_data(),
            "need_update": 0,
        }


async def publish_app_version(
        edition_name: str,
        edition_version_code: int,
        describe_zh: str,
        describe_en: str,
        describe_th: str,
        edition_url: str,
        edition_force: int = 0,
        package_type: int = 1,
        edition_issue: int = 1,
        edition_silence: int = 0,
        published_by: Optional[str] = None,
):
    db_client = MySQLClient(MYSQL_CONFIG)

    validation = _validate_version_code(edition_version_code)
    if validation:
        return validation

    for flag_name, flag_value in (
        ("edition_force", edition_force),
        ("edition_issue", edition_issue),
        ("edition_silence", edition_silence),
    ):
        validation = _validate_binary_flag(flag_name, flag_value)
        if validation:
            return validation

    if package_type not in (0, 1):
        return {"status": 400, "message": "package_type 仅支持 0 或 1", "results": None}

    validation = _validate_package_url(package_type, edition_url)
    if validation:
        return validation

    if not (edition_name or "").strip():
        return {"status": 400, "message": "edition_name 不能为空", "results": None}

    try:
        existing = db_client.query_app_version_by_version_code(edition_version_code)
        if existing:
            return {
                "status": 400,
                "message": f"edition_version_code={edition_version_code} 已存在",
                "results": None,
            }

        latest = db_client.query_latest_published_app_version()
        if latest and int(latest.get("edition_version_code") or 0) >= int(edition_version_code):
            return {
                "status": 400,
                "message": f"edition_version_code 必须大于当前已发布版本 {latest.get('edition_version_code')}",
                "results": None,
            }

        version_id = db_client.insert_app_version(
            edition_name=edition_name.strip(),
            edition_version_code=edition_version_code,
            describe_zh=(describe_zh or "").strip(),
            describe_en=(describe_en or "").strip(),
            describe_th=(describe_th or "").strip(),
            edition_url=edition_url.strip(),
            edition_force=edition_force,
            package_type=package_type,
            edition_issue=edition_issue,
            edition_silence=edition_silence,
            published_by=published_by,
        )

        return {
            "status": 200,
            "message": "版本发布成功",
            "results": {
                "id": version_id,
                "edition_version_code": edition_version_code,
                "edition_name": edition_name.strip(),
                "describe_zh": (describe_zh or "").strip(),
                "describe_en": (describe_en or "").strip(),
                "describe_th": (describe_th or "").strip(),
                "edition_url": edition_url.strip(),
                "package_type": package_type,
                "status": 1,
            },
        }
    except Exception as e:
        return {"status": 500, "message": f"版本发布失败: {str(e)}", "results": None}


async def revoke_app_version(
        version_id: int,
        revoke_reason: Optional[str] = None,
        revoked_by: Optional[str] = None,
):
    db_client = MySQLClient(MYSQL_CONFIG)
    try:
        version = db_client.query_app_version_by_id(version_id)
        if not version:
            return {"status": 404, "message": f"版本ID【{version_id}】不存在", "results": None}

        if int(version.get("status") or 0) != 1:
            return {"status": 400, "message": f"版本ID【{version_id}】当前状态不可撤销", "results": None}

        db_client.revoke_app_version(
            version_id=version_id,
            revoked_by=revoked_by,
            revoke_reason=(revoke_reason or "").strip() or None,
        )

        return {
            "status": 200,
            "message": "版本撤销成功",
            "results": {"id": version_id, "status": 2},
        }
    except Exception as e:
        return {"status": 500, "message": f"版本撤销失败: {str(e)}", "results": None}


async def list_app_versions(
        page: int = 1,
        page_size: int = 10,
        status: Optional[int] = None,
        edition_name: Optional[str] = None,
        edition_version_code: Optional[int] = None,
):
    db_client = MySQLClient(MYSQL_CONFIG)
    try:
        page = max(1, int(page or 1))
        page_size = max(1, min(100, int(page_size or 10)))

        if status is not None and status not in (1, 2):
            return {"status": 400, "message": "status 仅支持 1 或 2", "results": None}

        result = db_client.query_app_versions_paginated(
            page=page,
            page_size=page_size,
            status=status,
            edition_name=(edition_name or "").strip() or None,
            edition_version_code=edition_version_code,
        )

        return {
            "status": 200,
            "message": "查询成功",
            "results": {
                "data": result.get("data", []),
                "total": result.get("total", 0),
                "page": page,
                "page_size": page_size,
            },
        }
    except Exception as e:
        return {"status": 500, "message": f"版本列表查询失败: {str(e)}", "results": None}


async def upload_app_version_package(file, uploader: Optional[str] = None):
    filename = getattr(file, "filename", "") or ""
    filename_lower = filename.lower()
    if not filename:
        return {"status": 400, "message": "上传文件不能为空", "results": None}
    if not (filename_lower.endswith(".wgt") or filename_lower.endswith(".apk")):
        return {"status": 400, "message": "仅支持上传 .wgt 或 .apk 文件", "results": None}

    try:
        position_id = "0"
        # 不修改 oss_manager，仅在外层给上传文件名增加时间戳前缀，避免同名覆盖
        timestamp_prefix = str(int(time.time() * 1000))
        file.filename = f"{timestamp_prefix}_{filename}"
        if FILES_STORED_TYPE == "oss":
            object_name, file_uri, share_url = await oss_manager.oss_upload(file, position_id)
            edition_url = share_url
        elif FILES_STORED_TYPE == "minio":
            object_name, share_url, file_uri = await save_upload_file_minio(file, position_id)
            edition_url = share_url
        else:
            return {
                "status": 400,
                "message": f"当前 FILES_STORED_TYPE={FILES_STORED_TYPE} 不支持版本包上传",
                "results": None,
            }

        return {
            "status": 200,
            "message": "上传成功",
            "results": {
                "file_name": filename,
                "file_url": file_uri,
            },
        }
    except Exception as e:
        return {"status": 500, "message": f"上传版本包失败: {str(e)}", "results": None}


async def download_app_version_package(version_id: int, range_header: Optional[str] = None):
    db_client = MySQLClient(MYSQL_CONFIG)

    try:
        version = db_client.query_app_version_by_id(version_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询版本失败: {exc}") from exc

    if not version:
        raise HTTPException(status_code=404, detail=f"版本ID【{version_id}】不存在")

    if int(version.get("status") or 0) != 1:
        raise HTTPException(status_code=404, detail=f"版本ID【{version_id}】不可下载")

    file_uri = (version.get("edition_url") or "").strip()
    if not file_uri:
        raise HTTPException(status_code=404, detail="该版本缺少下载地址")

    if file_uri.startswith(("http://", "https://")):
        return RedirectResponse(url=file_uri, status_code=307)

    if not file_uri.startswith(("minio://", "oss://")):
        raise HTTPException(status_code=400, detail="仅支持 minio:// 或 oss:// 存储地址")

    filename = _guess_filename(file_uri)
    guessed_content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    if file_uri.startswith("minio://"):
        metadata = get_object_metadata_by_uri(file_uri)
        content_type = str(metadata.get("content_type") or guessed_content_type)
        size = metadata.get("size")
    else:
        metadata = oss_manager.get_object_metadata(file_uri)
        content_type = str(metadata.get("content_type") or guessed_content_type)
        size = metadata.get("size")

    return _build_streaming_response(
        decoded_uri=file_uri,
        content_type=content_type,
        filename=filename,
        size=size,
        range_header=range_header,
    )
