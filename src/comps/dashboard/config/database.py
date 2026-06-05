# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from urllib.parse import quote_plus
import os

from comps.dashboard.config.base_config import MYSQL_PASSWORD, MYSQL_USER,MYSQL_HOST,MYSQL_PORT,MYSQL_DB
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use SQLAlchemy engine
password = quote_plus(MYSQL_PASSWORD)
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{password}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
Base = declarative_base()

# 通过环境变量控制是否打印 SQL 日志（生产环境建议关闭）
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in ("true", "1", "yes")

engine = create_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    future=True,
    pool_pre_ping=True,  # 关键：使用前先 ping，一旦断开自动重连
    pool_recycle=1800,  # 连接超过 30 分钟自动回收，避免用到过期连接
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
