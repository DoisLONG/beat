# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
SYSTEM_COMMON_PORT = int(os.getenv("SYSTEM_COMMON_PORT", 8010))
# MYSQL配置
MYSQL_HOST = os.getenv("MYSQL_HOST", "10.3.70.118")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 13306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Eap@dfxw2025")
MYSQL_DB = os.getenv("MYSQL_DB", "ekba_kb")

MYSQL_CONFIG = {
    "host": MYSQL_HOST,
    "port": MYSQL_PORT,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "db": MYSQL_DB
}
# 支持多个密钥，用逗号分隔，必须是 Base64 编码的 32 字节密钥，加密时使用第一个密钥，解密时尝试所有密钥
MODEL_CONFIG_ENCRYPTION_KEYS = os.getenv("MODEL_CONFIG_ENCRYPTION_KEYS", "fd90Zn9EmvWbHtAyjP9bApzes-DtPcvHOXyAs-_QPjU=")
MODEL_CONFIG_ASR_PROBE_AUDIO_PATH = os.getenv("MODEL_CONFIG_ASR_PROBE_AUDIO_PATH", "")
