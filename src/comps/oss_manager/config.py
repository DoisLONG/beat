# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

# -------------------------------------------------------------
# OSS 凭证配置
# -------------------------------------------------------------
ACCESS_KEY_ID = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")

# -------------------------------------------------------------
# OSS 实例配置
# -------------------------------------------------------------
# 默认使用上海节点，可环境变量覆盖
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "https://oss-cn-shanghai.aliyuncs.com")

# Bucket 名称
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "eh-shanghai-ai")

# -------------------------------------------------------------
# 文件路径配置
# -------------------------------------------------------------
# 存储目录前缀，自动去除首尾斜杠，防止拼接出现 "//"
OSS_DEST_PREFIX = os.getenv("OSS_DEST_PREFIX", "ai-doc").strip("/")
# oss or minio
FILES_STORED_TYPE = os.getenv("FILES_STORED_TYPE", "minio")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower()
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "eap")
MINIO_PREFIX = os.getenv("MINIO_PREFIX", "ai-doc").strip("/")
