# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from comps.account.config import MYSQL_HOST, MYSQL_PORT, MYSQL_DB, MYSQL_USER, MYSQL_PASSWORD

# Use SQLAlchemy engine
password = quote_plus(MYSQL_PASSWORD)
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{password}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,  # 关键：使用前先 ping，一旦断开自动重连
    pool_recycle=1800,  # 连接超过 30 分钟自动回收，避免用到过期连接
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
