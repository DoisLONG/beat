# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from comps.oss_manager.oss_manager import get_oss_manager, OSSManager
from comps.oss_manager.config import OSS_BUCKET_NAME, OSS_ENDPOINT

# 创建一个默认的全局实例供直接使用
oss_manager = get_oss_manager()

__all__ = ["oss_manager", "OSSManager", "OSS_BUCKET_NAME", "OSS_ENDPOINT"]