# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from modelscope import snapshot_download

# 统一模型根目录
BASE_DIR = "/opt/models"

# 创建目录（避免不存在时报错）
os.makedirs(BASE_DIR, exist_ok=True)

print("开始下载 PDF-Extract-Kit 模型...")
pdf_model_dir = snapshot_download(
    'OpenDataLab/PDF-Extract-Kit-1.0',
    local_dir=os.path.join(BASE_DIR, 'OpenDataLab/PDF-Extract-Kit-1.0'),
)
print(f"PDF-Extract-Kit 下载完成: {pdf_model_dir}")

print("开始下载 LayoutReader 模型...")
layout_model_dir = snapshot_download(
    'ppaanngggg/layoutreader',
    local_dir=os.path.join(BASE_DIR, 'ppaanngggg/layoutreader'),
)
print(f"LayoutReader 下载完成: {layout_model_dir}")
