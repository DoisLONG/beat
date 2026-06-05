# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import pymysql
from threading import Lock

from pymysql.cursors import DictCursor

from comps import CustomLogger
import os
from typing import Optional, Dict, List

logger = CustomLogger("practice-db_client", os.getenv("LOG_LEVEL", "INFO"))


# ==============================
# 多语种白名单路由
# ==============================
SUPPORTED_LANGS = {"zh", "en", "th"}
DEFAULT_LANG = "zh"


def _resolve_lang(lang):
    """校验并归一化 data_lang，非法值统一降级为 zh。"""
    if not lang:
        return DEFAULT_LANG
    lang = str(lang).lower()
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def _table_name(base: str, lang) -> str:
    lang = _resolve_lang(lang)
    return base if lang == DEFAULT_LANG else f"{base}_{lang}"


def _get_sop_info_table(lang) -> str:
    return _table_name("sp_sop_info", lang)


def _get_exam_record_table(lang) -> str:
    return _table_name("sp_exam_record", lang)


class MySQLClient:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(MySQLClient, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config):
        if not self._initialized:
            self.config = config
            self.connection = None
            self._initialized = True

    def _connect(self):
        """
        确保连接存在且可用，如果连接断开则自动重连
        """
        try:
            if self.connection is None:
                self.connection = pymysql.connect(**self.config, autocommit=True)
            else:
                self.connection.ping(reconnect=True)
        except Exception as e:
            logger.warning(f"MySQL 连接失效，正在重连: {e}")
            self.connection = pymysql.connect(**self.config, autocommit=True)

    def close_connection(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            finally:
                self.connection = None

    def query_sop_info_by_id(self, sop_info_id: int, lang: str = DEFAULT_LANG) -> Optional[Dict]:
        """按ID查询SOP信息详情

        Args:
            sop_info_id: SOP信息ID
            lang: 业务数据语种（data_lang），用于路由 sp_sop_info* 表

        Returns:
            SOP信息记录字典，或None
        """
        self._connect()
        table = _get_sop_info_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT
                    *
                    FROM {table}
                    WHERE id = %s
                    LIMIT 1
                """
                cursor.execute(query, (sop_info_id,))
                result = cursor.fetchone()

                if result:
                    logger.info(f"查询到SOP信息ID【{sop_info_id}】的记录, table={table}")
                else:
                    logger.warning(f"未找到SOP信息ID【{sop_info_id}】的记录, table={table}")

                return result
            except Exception as e:
                logger.error(f"MySQL 按ID查询SOP信息失败: {e}")
                raise

    def query_sop_infos_by_position_id(self, position_id: str, lang: str = DEFAULT_LANG):
        """
        按岗位ID查询SOP信息列表

        Args:
            position_id: 岗位ID
            lang: 业务数据语种（data_lang）
        """
        self._connect()
        table = _get_sop_info_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT
                    *
                    FROM {table}
                    WHERE position_id = %s
                """
                cursor.execute(query, (position_id,))
                results = cursor.fetchall()

                if results:
                    logger.info(f"查询到岗位ID【{position_id}】的SOP信息记录，共{len(results)}条, table={table}")
                else:
                    logger.warning(f"未找到岗位ID【{position_id}】的SOP信息记录, table={table}")

                return results
            except Exception as e:
                logger.error(f"MySQL 按岗位ID查询SOP信息失败: {e}")
                raise

    async def insert_exam_record(self, record: Dict, lang: str = DEFAULT_LANG) -> bool:
        self._connect()
        table = _get_exam_record_table(lang)
        sql = (
            f"INSERT INTO {table} "
            "(id, user_id, position_id, start_time, end_time, exam_category, filename, "
            "conversation_id, summary, total_score, accumulated_score, total_questions, answered_questions, "
            "sop_id, tenant_id) "
            "VALUES (%(id)s, %(user_id)s, %(position_id)s, %(start_time)s, %(end_time)s, %(exam_category)s, "
            "%(filename)s, %(conversation_id)s, %(summary)s, %(total_score)s, %(accumulated_score)s, "
            "%(total_questions)s, %(answered_questions)s, "
            "%(sop_id)s, %(tenant_id)s)"
        )
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, record)
            # 必须显式提交，否则数据不会持久化
            self.connection.commit()
            logger.info(f"考试记录插入成功 | table={table} | exam_id={record.get('id')}")
            return True
        except pymysql.IntegrityError:
            # 重点：这是处理重复触发（交卷）的核心防线
            logger.warning(f"考试记录已存在，跳过重复插入 | table={table} | exam_id={record.get('id')}")
            return False
        except Exception as e:
            # 发生错误时回滚
            self.connection.rollback()
            logger.error(f"插入考试记录失败 table={table}: {e}")
            return False