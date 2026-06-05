# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import tempfile
from datetime import timedelta
from typing import Iterator, Optional, Tuple

from minio import Minio, S3Error
from fastapi import UploadFile, HTTPException
from starlette.concurrency import run_in_threadpool

from comps import CustomLogger
from comps.oss_manager.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECURE,
    MINIO_SECRET_KEY,
    MINIO_BUCKET_NAME,
    MINIO_PREFIX
)

logger = CustomLogger("dataprep-minio-utils", os.getenv("LOG_LEVEL", "INFO"))

# ===========================
# MinIO Client
# ===========================
MINIO_CONF = {
    "endpoint": MINIO_ENDPOINT,
    "access_key": MINIO_ACCESS_KEY,
    "secret_key": MINIO_SECRET_KEY,
    "secure": MINIO_SECURE == "true",
}
minio_client = Minio(**MINIO_CONF)


# ===========================
# 工具函数
# ===========================
def _safe_name(name: str) -> str:
    """防路径注入 + 简单清洗"""
    return os.path.basename(name).replace("\\", "_").replace("/", "_")


def _build_object_name(post_id: str, filename: str) -> str:
    safe_post_id = str(post_id).replace("/", "_").replace(" ", "_")
    safe_filename = _safe_name(filename)
    return f"{MINIO_PREFIX}/{safe_post_id}_{safe_filename}"


# ===========================
# 上传文件（覆盖模式）
# ===========================
async def save_upload_file_minio(file, post_id: str) -> Tuple[str, str, str]:
    """
    保存 UploadFile 到 MinIO
    规则: prefix/{post_id}_{filename}
    同岗位同文件名允许覆盖
    返回: (object_name, share_url, file_uri)
    """

    def upload_logic():
        # 1. 确保 bucket 存在
        if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
            minio_client.make_bucket(MINIO_BUCKET_NAME)

        # 2. 原始文件名
        original_name = file.filename
        if not original_name:
            raise ValueError("UploadFile.filename 为空")

        # 3. 构建 object_name
        object_name = _build_object_name(post_id, original_name)

        logger.info(f"[MinIO Upload] bucket={MINIO_BUCKET_NAME}, object={object_name}")

        # 4. 直接上传（存在则覆盖）
        minio_client.put_object(
            bucket_name=MINIO_BUCKET_NAME,
            object_name=object_name,
            data=file.file,
            length=-1,  # 流式上传
            part_size=10 * 1024 * 1024,
            content_type=file.content_type,
        )

        # 5. 生成签名 URL（7天）
        share_url = minio_client.presigned_get_object(
            MINIO_BUCKET_NAME,
            object_name,
            expires=timedelta(days=7)
        )

        return object_name, share_url

    object_name, url = await run_in_threadpool(upload_logic)
    file_uri = f"minio://{MINIO_BUCKET_NAME}/{object_name}"
    return object_name, url, file_uri


async def download_minio_by_uri(file_uri: str) -> tuple[str, str]:
    """
    下载 MinIO 文件到临时文件
    file_uri 格式: minio://bucket/object_name
    返回: (tmp_dir, temp_file_path)
    """

    if not file_uri.startswith("minio://"):
        raise HTTPException(status_code=400, detail=f"非法 file_uri: {file_uri}")

    # 解析 URI
    uri_body = file_uri.replace("minio://", "", 1)
    try:
        bucket, object_name = uri_body.split("/", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"非法 file_uri 结构: {file_uri}")

    temp_filename = _safe_name(os.path.basename(object_name).split('_', 1)[-1] if '_' in os.path.basename(object_name) else os.path.basename(object_name))

    tmp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(tmp_dir, temp_filename)

    try:
        minio_client.fget_object(bucket, object_name, temp_path)
        return tmp_dir, temp_path

    except (S3Error, Exception) as e:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        error_type = "S3" if isinstance(e, S3Error) else "未知"
        raise HTTPException(
            status_code=500,
            detail=f"通过 file_uri 下载失败 ({error_type}): {file_uri}, 错误: {e}"
        )

# ===========================
# 下载文件到临时目录
# ===========================
async def download_minio_to_temp(filename: str, post_id: str) -> Tuple[str, str]:
    """
    下载 MinIO 文件到临时目录
    定位规则: prefix/{post_id}_{filename}
    返回: (tmp_dir, temp_file_path)
    """

    if not filename or not post_id:
        raise HTTPException(status_code=400, detail="filename 和 post_id 必须提供")

    object_name = _build_object_name(post_id, filename)
    temp_filename = _safe_name(filename)

    tmp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(tmp_dir, temp_filename)

    try:
        minio_client.fget_object(MINIO_BUCKET_NAME, object_name, temp_path)
        return tmp_dir, temp_path

    except (S3Error, Exception) as e:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        error_type = "S3" if isinstance(e, S3Error) else "未知"
        raise HTTPException(
            status_code=500,
            detail=f"MinIO 文件下载失败 ({error_type}): {MINIO_BUCKET_NAME}/{object_name}, 错误: {e}"
        )


# ===========================
# 获取 MinIO URI
# ===========================
async def get_uri_by_filename(filename: str, post_id: str) -> Optional[str]:
    """
    根据 filename + post_id 获取 MinIO URI
    """
    if not filename or not post_id:
        return None

    object_name = _build_object_name(post_id, filename)

    def check():
        try:
            minio_client.stat_object(MINIO_BUCKET_NAME, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise

    try:
        exists = await run_in_threadpool(check)
        if exists:
            return f"minio://{MINIO_BUCKET_NAME}/{object_name}"
        return None
    except Exception as e:
        logger.error(f"[get_uri_by_filename] 获取 MinIO URI 失败: {e}")
        return None


# ===========================
# 获取分享 URL
# ===========================
async def get_share_url_by_filename(
    filename: str,
    post_id: str,
    expires_days: int = 30
) -> Optional[str]:
    """
    根据 filename + post_id 获取签名 URL
    """
    if not filename or not post_id:
        return None

    object_name = _build_object_name(post_id, filename)

    def get_url():
        return minio_client.presigned_get_object(
            MINIO_BUCKET_NAME,
            object_name,
            expires=timedelta(days=expires_days)
        )

    try:
        url = await run_in_threadpool(get_url)
        return url
    except Exception as e:
        logger.error(f"[get_share_url_by_filename] 生成 MinIO 签名 URL 失败: {e}")
        return None

async def get_share_url_by_filename_and_post(
    filename: str,
    post_id: str,
    expires_days: int = 30
) -> Optional[str]:
    """
    通过 filename + post_id 获取 share_url
    """
    object_name = f"{MINIO_PREFIX}/{post_id}/{filename.lstrip('/')}"

    def gen():
        return minio_client.presigned_get_object(
            MINIO_BUCKET_NAME,
            object_name,
            expires=timedelta(days=expires_days)
        )

    try:
        url = await run_in_threadpool(gen)
        return url
    except Exception as e:
        logger.error(
            f"[get_share_url_by_filename_and_post] 生成 share_url 失败: "
            f"{MINIO_BUCKET_NAME}/{object_name}, err={e}"
        )
        return None

async def get_share_url_by_file_uri(file_uri: str, expires_days: int = 30) -> Optional[str]:
    """
    通过 file_uri 生成 share_url
    file_uri 格式: minio://bucket/object_name
    """
    if not file_uri.startswith("minio://"):
        raise ValueError("非法 file_uri 格式")

    # 解析 bucket 和 object_name
    uri = file_uri.replace("minio://", "")
    parts = uri.split("/", 1)
    if len(parts) != 2:
        raise ValueError("非法 file_uri 结构")

    bucket_name, object_name = parts

    def gen():
        return minio_client.presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(days=expires_days)
        )

    try:
        url = await run_in_threadpool(gen)
        return url
    except Exception as e:
        logger.error(f"[get_share_url_by_file_uri] 生成 share_url 失败: {e}")
        return None


def parse_minio_uri(file_uri: str) -> tuple[str, str]:
    """解析 minio://bucket/object_name URI。"""
    if not file_uri.startswith("minio://"):
        raise ValueError("非法 file_uri 格式")

    uri = file_uri.replace("minio://", "", 1)
    parts = uri.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("非法 file_uri 结构")
    return parts[0], parts[1]


def get_object_metadata_by_uri(file_uri: str) -> dict[str, str | int | None]:
    """读取 MinIO 对象元数据，供代理下载接口复用。"""
    bucket_name, object_name = parse_minio_uri(file_uri)

    try:
        metadata = minio_client.stat_object(bucket_name, object_name)
    except S3Error as exc:
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_uri}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取文件元数据失败: {exc}") from exc

    return {
        "bucket_name": bucket_name,
        "object_name": object_name,
        "size": getattr(metadata, "size", None),
        "content_type": getattr(metadata, "content_type", None),
        "etag": getattr(metadata, "etag", None),
    }


def iter_object_by_uri(
    file_uri: str,
    chunk_size: int = 1024 * 1024,
    offset: int | None = None,
    length: int | None = None,
) -> Iterator[bytes]:
    """按块读取 MinIO 对象，避免先生成预签名地址。"""
    bucket_name, object_name = parse_minio_uri(file_uri)
    response = None

    try:
        get_object_kwargs = {}
        if offset is not None:
            get_object_kwargs["offset"] = offset
        if length is not None:
            get_object_kwargs["length"] = length
        response = minio_client.get_object(bucket_name, object_name, **get_object_kwargs)
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            yield chunk
    except S3Error as exc:
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_uri}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {exc}") from exc
    finally:
        if response is not None:
            response.close()
            response.release_conn()
