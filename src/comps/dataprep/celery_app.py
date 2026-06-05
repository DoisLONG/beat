# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from datetime import timedelta
from celery import Celery
from comps.dataprep.config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB
)

celery_app = Celery(
    "dataprep",
    broker=f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    backend=f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
)

celery_app.conf.update(
    result_expires=timedelta(days=1),  # 任务结果保留 1 天
    timezone='Asia/Shanghai',  # 添加时区配置
    enable_utc=True,  # 启用UTC
    task_track_started=True,
    # # debug
    # worker_send_task_events=True,
    # task_send_sent_event=True,
)
