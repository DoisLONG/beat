# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

# 服务配置
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "6020"))
SERVICE_NAME = "opea_service@dashboard"

# 活跃用户定义
ACTIVE_USER_DAYS = int(os.getenv("ACTIVE_USER_DAYS", "7"))  # 近N天
ACTIVE_USER_MIN_SECONDS = int(os.getenv("ACTIVE_USER_MIN_SECONDS", "1800"))  # 最少在线时长（秒）

# 考试达标分数线
EXAM_PASS_SCORE = float(os.getenv("EXAM_PASS_SCORE", "60.0"))

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 会话超时时间（秒）
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1小时无活动则超时

# 缓存配置
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "false").lower() == "true"
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 缓存5分钟

# 数据库配置
MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "13306"))
MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "Eap@dfxw2025")
MYSQL_DB: str = os.getenv("MYSQL_DB", "ekba_kb")
MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))

# --------------------
# 统计快照定时任务配置
# 配置格式参考 CronTrigger 参数
# --------------------

# 每日任务执行时间 (默认 每日 00:05)
CRON_DAILY_HOUR = os.getenv("CRON_DAILY_HOUR", "0")
CRON_DAILY_MINUTE = os.getenv("CRON_DAILY_MINUTE", "5")

# 每周任务执行时间 (默认 周一 00:10)
CRON_WEEKLY_DAY_OF_WEEK = os.getenv("CRON_WEEKLY_DAY_OF_WEEK", "mon")
CRON_WEEKLY_HOUR = os.getenv("CRON_WEEKLY_HOUR", "0")
CRON_WEEKLY_MINUTE = os.getenv("CRON_WEEKLY_MINUTE", "10")
