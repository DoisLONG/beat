# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import logging

# Database configuration
MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "13306"))
MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "Eap@dfxw2025")
MYSQL_DB: str = os.getenv("MYSQL_DB", "ekba_kb")

# Security settings
SECRET_KEY: str = os.getenv("SECRET_KEY", "your_secret_key")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_DELTA: int = int(os.getenv("JWT_EXPIRATION_DELTA", "86400"))  # in seconds

# 及格分数线
PASSING_SCORE: int = int(os.getenv("PASSING_SCORE", "60"))

# 警告：弱默认密钥
if SECRET_KEY == "your_secret_key":
    logging.warning(
        "警告: SECRET_KEY 使用默认值，生产环境请务必设置安全的随机密钥！"
    )

# Alias for session timeout logic
SESSION_TIMEOUT = JWT_EXPIRATION_DELTA
