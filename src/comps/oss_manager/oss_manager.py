# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import asyncio
import tempfile
from typing import Iterator, Optional, Any, Coroutine
from urllib.parse import urlparse, unquote

import oss2
from fastapi import HTTPException

from comps import CustomLogger

from comps.oss_manager import config
from comps.oss_manager.config import FILES_STORED_TYPE

logger = CustomLogger("oss_manager", os.getenv("LOG_LEVEL", "INFO"))

class OSSManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OSSManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        # 只有在使用 OSS 存储时才初始化
        if FILES_STORED_TYPE != "oss":
            logger.info("FILES_STORED_TYPE 不是 'oss'，跳过 OSS Manager 初始化")
            self._initialized = True
            return

        # 加载配置
        self.access_key_id = config.ACCESS_KEY_ID
        self.access_key_secret = config.ACCESS_KEY_SECRET
        self.endpoint = config.OSS_ENDPOINT
        self.bucket_name = config.OSS_BUCKET_NAME
        self.dest_prefix = config.OSS_DEST_PREFIX

        # 校验凭证
        if not (self.access_key_id and self.access_key_secret):
            raise RuntimeError("OSS配置缺失: 请在环境变量设置 ALIYUN_ACCESS_KEY_ID 和 SECRET")

        try:
            self._auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self._bucket = oss2.Bucket(self._auth, self.endpoint, self.bucket_name)
            logger.info(f"OSS Manager 初始化成功. Bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"OSS 连接初始化失败: {e}")
            raise HTTPException(status_code=500, detail="OSS 连接初始化失败")

        self._initialized = True

    def _safe_name(self, name: str) -> str:
        if not name:
            return "unnamed_file"
        safe = name.replace("/", "_").replace(" ", "_")
        return safe

    def _build_object_name(self, post_id: str, filename: str) -> str:
        """
        构建object_name:
        {dest_prefix}/{safe_post_id}_{safe_filename}
        """
        safe_post_id = str(post_id).replace("/", "_").replace(" ", "_")
        safe_filename = self._safe_name(filename)
        if self.dest_prefix:
            return f"{self.dest_prefix}/{safe_post_id}_{safe_filename}"
        return f"{safe_post_id}_{safe_filename}"

    def parse_key(self, uri_or_key: str) -> Optional[str]:
        return self._parse_key(uri_or_key)

    def _parse_key(self, uri_or_key: str) -> Optional[str]:
        # 1. oss://bucket/key
        if uri_or_key.startswith("oss://"):
            u = urlparse(uri_or_key)
            # u.netloc = bucket
            # u.path = /ai-doc/xxx.xls
            if not u.path:
                return None
            return unquote(u.path.lstrip("/"))

        # 2. https://bucket.endpoint/key?sign=xxx
        if uri_or_key.startswith("http"):
            u = urlparse(uri_or_key)
            if not u.path:
                return None
            return unquote(u.path.lstrip("/"))

        # 3. 纯 object key
        return uri_or_key.lstrip("/")

    def _get_full_key(self, filename: str) -> str:
        """自动添加配置的前缀"""
        clean_name = filename.lstrip("/")
        if self.dest_prefix:
            return f"{self.dest_prefix}/{clean_name}"
        return clean_name

    # =========================
    # 公共元数据能力
    # =========================
    async def get_object_size(self, uri_or_key: str) -> Optional[int]:
        """获取 OSS 对象大小（字节）"""
        object_key = self._parse_key(uri_or_key)
        if not object_key:
            return None

        def _sync_head():
            meta = self._bucket.head_object(object_key)

            if hasattr(meta, "content_length"):
                return int(meta.content_length)

            if hasattr(meta, "headers"):
                return int(meta.headers.get("Content-Length"))

            raise RuntimeError(f"Unknown meta format: {meta}")

        try:
            return await asyncio.to_thread(_sync_head)
        except Exception as e:
            logger.error(f"获取对象大小失败 [{object_key}]: {e}")
            return None


    async def oss_upload(self, file, position_id: str) -> tuple[str, str, str]:
        """
        普通文件上传（PDF、图片等小文件 < 50MB）。
        直接读取内存上传。
        """
        filename = getattr(file, "filename", "unnamed_file")
        object_key = self._build_object_name(position_id, filename)

        try:
            contents = await file.read()
            if not contents:
                logger.warning(f"上传文件内容为空: {filename}")

            def _sync_put():
                return self._bucket.put_object(object_key, contents)

            await asyncio.to_thread(_sync_put)

            file_uri = f"oss://{self.bucket_name}/{object_key}"
            share_url = self.get_presigned_url(file_uri)

            logger.info(f"OSS 上传成功: {file_uri}")
            return object_key, file_uri, share_url
        finally:
            if hasattr(file, "close"):
                if asyncio.iscoroutinefunction(file.close):
                    await file.close()
                else:
                    file.close()

    async def upload_large_file(self, file_obj, position_id) -> tuple[str, str, str]:
        filename = getattr(file_obj, "filename", "unnamed_file")
        object_key = self._build_object_name(position_id, filename)

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            CHUNK = 10 * 1024 * 1024
            await file_obj.seek(0)
            while True:
                data = await file_obj.read(CHUNK)
                if not data:
                    break
                await asyncio.to_thread(self._write_chunk, tmp_path, data)

            def _sync_upload():
                return oss2.resumable_upload(
                    self._bucket,
                    object_key,
                    tmp_path,
                    multipart_threshold=100 * 1024 * 1024,
                    num_threads=4,
                )

            await asyncio.to_thread(_sync_upload)

            file_uri = f"oss://{self.bucket_name}/{object_key}"
            share_url = self.get_presigned_url(file_uri)

            logger.info(f"OSS 大文件上传成功: {file_uri}")
            return object_key, file_uri, share_url

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _write_chunk(self, path, content):
        with open(path, "ab") as f:
            f.write(content)

    # ---------------------------
    # 组合功能：上传视频并返回链接
    # ---------------------------
    async def upload_video_and_sign(self, file_obj, position_id, expires: int = 3600) -> Optional[str]:
        """
        上传视频，并直接返回【OSS URI】和【签名播放地址】。

        :param file_obj: 上传的文件对象
        :param position_id: 岗位 ID，用于构建存储路径
        :param expires: 签名链接有效期（秒），默认 1 小时
        :return: "url": "https://..."
        """
        _, file_uri, _ = await self.upload_large_file(file_obj, position_id)
        return self.get_presigned_url(file_uri, expiration=expires)

    # =========================
    # 下载（小文件）
    # =========================
    async def get_bytes(self, file_uri: str, max_size: int = 10 * 1024 * 1024) -> Optional[bytes]:
        key = self._parse_key(file_uri)
        if not key:
            return None

        def _sync_get():
            meta = self._bucket.head_object(key)
            size = int(meta.content_length)
            if size > max_size:
                raise ValueError("文件过大")
            return self._bucket.get_object(key).read()

        try:
            return await asyncio.to_thread(_sync_get)
        except Exception as e:
            logger.error(f"下载 bytes 失败: {e}")
            return None

    # =========================
    # 下载（大文件，落盘）
    # =========================
    async def download_large_file(
            self,
            file_uri: str,
            local_path: str,
    ) -> bool:
        key = self._parse_key(file_uri)
        if not key:
            return False

        def _sync_download():
            self._bucket.get_object_to_file(key, local_path)

        try:
            await asyncio.to_thread(_sync_download)
            return True
        except Exception as e:
            logger.error(f"下载失败: {file_uri}, 错误: {e}")
            return False

    # =========================
    # 预览 / 语种判断
    # =========================
    async def get_head_text(
            self,
            uri_or_key: str,
            max_chars: int = 1000,
            byte_limit: int = 8192,
    ) -> Optional[str]:
        object_key = self._parse_key(uri_or_key)
        if not object_key:
            return None

        def _sync_range():
            obj = self._bucket.get_object(
                object_key,
                byte_range=(0, byte_limit - 1),
            )
            return obj.read()

        try:
            raw = await asyncio.to_thread(_sync_range)
            text = raw.decode("utf-8", errors="ignore")
            return text[:max_chars]
        except Exception as e:
            logger.error(f"Range 读取失败 [{object_key}]: {e}")
            return None


    async def download_to_temp_by_file_uri(self, file_uri: str, local_path: str) -> bool:
        """
        下载文件保存到本地路径
        :param file_uri: OSS URI
        :param local_path: 本地保存路径
        """
        key = self._parse_key(file_uri)
        if not key:
            return False

        def _sync_download():
            self._bucket.get_object_to_file(key, local_path)

        try:
            await asyncio.to_thread(_sync_download)
            return True
        except Exception as e:
            logger.error(f"下载失败: {file_uri}, 错误: {e}")
            return False

    async def check_exists(self, filename: str, post_id: str) -> Optional[str]:
        object_key = self._build_object_name(post_id, filename)
        try:
            exists = await asyncio.to_thread(self._bucket.object_exists, object_key)
            if exists:
                return f"oss://{self.bucket_name}/{object_key}"
            return None
        except Exception:
            return None

    async def get_uri_by_filename(self, filename: str, post_id: str) -> Optional[str]:
        return await self.check_exists(filename, post_id)

    # ---------------------------
    # URL 生成功能 (同步)
    # ---------------------------
    def get_presigned_url(self, uri_or_key: str, expiration: int = 3600) -> str:
        key = self._parse_key(uri_or_key)
        if not key:
            return ""
        try:
            return self._bucket.sign_url('GET', key, expiration)
        except Exception as e:
            logger.error(f"签名 URL 生成失败: {e}")
            return ""

    def get_public_url(self, uri_or_key: str) -> str:
        key = self._parse_key(uri_or_key)
        if not key:
            return ""
        domain = self.endpoint.replace("http://", "").replace("https://", "")
        return f"https://{self.bucket_name}.{domain}/{key}"

    def get_video_url(self, uri_or_key: str, expires: int = 3600) -> str:
        """
        专门用于获取视频播放地址的语义化方法。
        默认使用签名 URL，最安全。
        """
        return self.get_presigned_url(uri_or_key, expiration=expires)

    def get_object_metadata(self, uri_or_key: str) -> dict[str, str | int | None]:
        key = self._parse_key(uri_or_key)
        if not key:
            raise HTTPException(status_code=400, detail="非法 OSS URI")

        try:
            meta = self._bucket.head_object(key)
        except oss2.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail=f"文件不存在: {uri_or_key}") from None
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取文件元数据失败: {exc}") from exc

        headers = getattr(meta, "headers", {}) or {}
        content_length = getattr(meta, "content_length", None) or headers.get("Content-Length")
        content_type = headers.get("Content-Type")
        etag = headers.get("ETag")
        return {
            "object_key": key,
            "size": int(content_length) if content_length is not None else None,
            "content_type": content_type,
            "etag": etag,
        }

    def iter_object(
        self,
        uri_or_key: str,
        chunk_size: int = 1024 * 1024,
        offset: int | None = None,
        length: int | None = None,
    ) -> Iterator[bytes]:
        key = self._parse_key(uri_or_key)
        if not key:
            raise HTTPException(status_code=400, detail="非法 OSS URI")

        obj = None
        try:
            range_kwargs = {}
            if offset is not None and length is not None and length > 0:
                range_kwargs["byte_range"] = (offset, offset + length - 1)
            elif offset is not None:
                range_kwargs["byte_range"] = (offset, None)
            obj = self._bucket.get_object(key, **range_kwargs)
            while True:
                chunk = obj.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        except oss2.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail=f"文件不存在: {uri_or_key}") from None
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取文件失败: {exc}") from exc
        finally:
            if obj is not None:
                obj.close()


# 内部实例化
_manager_instance = OSSManager()

def get_oss_manager() -> OSSManager:
    return _manager_instance
