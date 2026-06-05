# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import pymysql
from threading import Lock

from pymysql.constants import CLIENT
from pymysql.cursors import DictCursor

from comps import CustomLogger
import os
from typing import Optional, Dict, List, Any

logger = CustomLogger("dataprep-mysql", os.getenv("LOG_LEVEL", "INFO"))

# ——— 多语种路由辅助（表名白名单，防止 SQL 注入）———
# zh 直接复用原有旧表，无需迁移历史数据；en/th 为新建语种表
_LANG_SOP_TABLE_MAP: Dict[str, str] = {
    "zh": "sp_sop_info",
    "en": "sp_sop_info_en",
    "th": "sp_sop_info_th",
}
_FALLBACK_SOP_TABLE = "sp_sop_info"

# ——— sp_sop_version 多语种路由（与 sop_info 保持相同语种边界）———
# zh 复用原有旧表 sp_sop_version；en/th 为新建语种版本表
_LANG_VERSION_TABLE_MAP: Dict[str, str] = {
    "zh": "sp_sop_version",
    "en": "sp_sop_version_en",
    "th": "sp_sop_version_th",
}
_FALLBACK_VERSION_TABLE = "sp_sop_version"

_LANG_TENANT_TABLE_MAP: Dict[str, str] = {
    "zh": "sp_tenant",
    "en": "sp_tenant_en",
    "th": "sp_tenant_th",
}
_FALLBACK_TENANT_TABLE = "sp_tenant"

_LANG_COMPANY_TABLE_MAP: Dict[str, str] = {
    "zh": "sp_company",
    "en": "sp_company_en",
    "th": "sp_company_th",
}
_FALLBACK_COMPANY_TABLE = "sp_company"

_LANG_DEPARTMENT_TABLE_MAP: Dict[str, str] = {
    "zh": "sp_department",
    "en": "sp_department_en",
    "th": "sp_department_th",
}
_FALLBACK_DEPARTMENT_TABLE = "sp_department"

_LANG_POSITION_TABLE_MAP: Dict[str, str] = {
    "zh": "sp_position",
    "en": "sp_position_en",
    "th": "sp_position_th",
}
_FALLBACK_POSITION_TABLE = "sp_position"

_LANG_GENERAL_POSITION_NAME_MAP: Dict[str, str] = {
    "zh": "通用岗位",
    "en": "General Position",
    "th": "ตำแหน่งทั่วไป",
}


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
                self.connection = pymysql.connect(**self.config, autocommit=True, client_flag=CLIENT.FOUND_ROWS)
            else:
                self.connection.ping(reconnect=True)
        except Exception as e:
            logger.warning(f"MySQL 连接失效，正在重连: {e}")
            self.connection = pymysql.connect(**self.config, autocommit=True, client_flag=CLIENT.FOUND_ROWS)

    def close_connection(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            finally:
                self.connection = None

    @staticmethod
    def _get_sop_table(lang: str) -> str:
        """根据语种返回对应的 SOP 表名（白名单保护，防止 SQL 注入）。

        Args:
            lang: 业务语种，如 "zh" / "en" / "th"

        Returns:
            对应表名，如 "sp_sop_info" / "sp_sop_info_en" / "sp_sop_info_th"；
            未知语种降级为 "sp_sop_info"
        """
        return _LANG_SOP_TABLE_MAP.get(lang, _FALLBACK_SOP_TABLE)

    @staticmethod
    def _get_version_table(lang: str) -> str:
        """根据语种返回对应的 SOP 版本表名（白名单保护，防止 SQL 注入）。

        Args:
            lang: 业务语种，如 "zh" / "en" / "th"

        Returns:
            对应表名，如 "sp_sop_version" / "sp_sop_version_en" / "sp_sop_version_th"；
            未知语种降级为 "sp_sop_version"
        """
        return _LANG_VERSION_TABLE_MAP.get(lang, _FALLBACK_VERSION_TABLE)

    @staticmethod
    def _get_tenant_table(lang: str) -> str:
        return _LANG_TENANT_TABLE_MAP.get(lang, _FALLBACK_TENANT_TABLE)

    @staticmethod
    def _get_company_table(lang: str) -> str:
        return _LANG_COMPANY_TABLE_MAP.get(lang, _FALLBACK_COMPANY_TABLE)

    @staticmethod
    def _get_department_table(lang: str) -> str:
        return _LANG_DEPARTMENT_TABLE_MAP.get(lang, _FALLBACK_DEPARTMENT_TABLE)

    @staticmethod
    def _get_position_table(lang: str) -> str:
        return _LANG_POSITION_TABLE_MAP.get(lang, _FALLBACK_POSITION_TABLE)

    @staticmethod
    def _get_general_position_name(lang: str) -> str:
        return _LANG_GENERAL_POSITION_NAME_MAP.get(lang, _LANG_GENERAL_POSITION_NAME_MAP["zh"])

    def insert_sops(self, title, filename, position_id, file_type, tenant_id, file_uri, start_time, end_time,
                    lang: str = "zh"):
        """插入SOP信息到对应语种表（包含租户ID）。

        Args:
            lang: 业务语种，决定写入哪张语种表（sp_sop_info / sp_sop_info_en / sp_sop_info_th）
        """
        table = self._get_sop_table(lang)
        tenant_table = self._get_tenant_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 验证租户是否存在
                cursor.execute(
                    f"SELECT tenant_id FROM {tenant_table} WHERE tenant_id = %s AND status = 1",
                    (tenant_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"租户ID不存在或已停用: {tenant_id}")

                query = f"""
                    INSERT INTO {table} (title, filename, file_uri, position_id, file_type, tenant_id, start_time, end_time, lang) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (title, filename, file_uri, position_id, file_type, tenant_id, start_time, end_time, lang))
                self.connection.commit()
                inserted_id = cursor.lastrowid
                logger.info(f"租户【{tenant_id}】新增SOP【{title}】到【{table}】成功，SOP ID: {inserted_id}")
                return inserted_id
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 插入SOP失败: {e}")
                raise

    def update_taskid_and_status(self, sop_id: int, task_id: str, task_status: str = "PENDING",
                                  lang: str = "zh") -> bool:
        """根据 sop_id 更新 task_id 与 task_status。

        Args:
            lang: 业务语种，决定操作哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                sql = f"""
                    UPDATE {table}
                    SET task_id = %s, task_status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """
                cursor.execute(sql, (task_id, task_status, sop_id))
                if cursor.rowcount == 0:
                    logger.warning(f"sop_id={sop_id} 在 {table} 未找到, 更新未生效")
                    return False
                return True
            except Exception as e:
                logger.error(f"更新 task_id/status 失败: {e}")
                return False

    def query_sop_existing(self, sop_type_name):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 校验类型名称是否已存在
                check_sql = "SELECT position_id FROM sop_type WHERE sop_type_name = %s"
                cursor.execute(check_sql, (sop_type_name))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")

    def query_sop_existing_id(self, sop_type_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 校验类型名称是否已存在
                check_sql = "SELECT position_id FROM sop_type WHERE position_id = %s"
                cursor.execute(check_sql, (sop_type_id))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")

    def check_duplicate_sop_type(self, new_sop_type_name, sop_type_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                check_duplicate_sql = """
                    SELECT position_id FROM sop_type 
                    WHERE sop_type_name = %s AND position_id != %s
                """
                cursor.execute(check_duplicate_sql, (new_sop_type_name, sop_type_id))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")

    def update_sop_type(self, new_sop_type_name, sop_type_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                update_sql = "UPDATE sop_type SET sop_type_name = %s WHERE position_id = %s"
                cursor.execute(update_sql, (new_sop_type_name, sop_type_id))
            except Exception as e:
                logger.error(f"MySQL 修改失败: {e}")

    def delete_sop_type(self, sop_type_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 执行删除操作
                delete_sql = "DELETE FROM sop_type WHERE position_id = %s"
                cursor.execute(delete_sql, (sop_type_id))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 删除失败: {e}")

    def insert_sop_type(self, sop_type_name):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 插入新类型
                insert_sql = "INSERT INTO sop_type (sop_type_name) VALUES (%s)"
                cursor.execute(insert_sql, (sop_type_name))
            except Exception as e:
                logger.error(f"MySQL 插入失败: {e}")

    def query_all_sop_type(self):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 查询所有SOP类型（无分页，返回全部数据）
                query_sql = "SELECT position_id, sop_type_name FROM sop_type ORDER BY position_id ASC"
                cursor.execute(query_sql)
                result = cursor.fetchall()
                return result
            except Exception as e:
                logger.error(f"MySQL 插入失败: {e}")

    def query_sops_by_task_id(self, task_id, lang: str = "zh"):
        """按 task_id 查询 SOP 记录。

        Args:
            lang: 业务语种，决定查哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"SELECT * FROM {table} WHERE task_id = %s"
                cursor.execute(query, (task_id,))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")
                return None

    def query_sops_by_filename(self, file_name, position_id, lang: str = "zh"):
        """按文件名和岗位 ID 查询 SOP 记录。

        Args:
            lang: 业务语种，决定查哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"SELECT * FROM {table} WHERE filename = %s and position_id = %s"
                cursor.execute(query, (file_name, position_id))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")
                return None

    def update_sops(self, sop_id: int, task_status, remark="无", lang: str = "zh"):
        """更新 SOP 的 task_status 和 remark。

        Args:
            lang: 业务语种，决定操作哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = f"UPDATE {table} SET task_status = %s, remark = %s WHERE id = %s"
                cursor.execute(query, (task_status, remark, sop_id))
            except Exception as e:
                logger.error(f"MySQL 更新失败: {e}")

    def query_sops_list(self, lang: str = "zh"):
        """查询全部 SOP 记录。

        Args:
            lang: 业务语种，决定查哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"SELECT * FROM {table}"
                cursor.execute(query)
                result = cursor.fetchall()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询列表失败: {e}")
                return []

    def delete_sops(self, sop_id: int, lang: str = "zh"):
        """删除指定语种表中的 SOP 记录。

        Args:
            lang: 业务语种，决定操作哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = f"DELETE FROM {table} WHERE id = %s"
                cursor.execute(query, (sop_id,))
            except Exception as e:
                logger.error(f"MySQL 删除失败: {e}")

    def insert_company(
            self,
            company_name: str,
            establish_time: Optional[str] = None,
            address: Optional[str] = None,
            contact_phone: Optional[str] = None,
            remark: Optional[str] = None
    ) -> None:
        """新增公司记录（返回None，插入失败会抛出异常）

        Args:
            company_name: 公司名称（必填，不可重复）
            establish_time: 成立时间（可选，格式YYYY-MM-DD）
            address: 公司地址（可选）
            contact_phone: 联系电话（可选）
            remark: 备注信息（可选）
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = """
                    INSERT INTO sp_company (
                        company_name, establish_time, address, contact_phone, remark
                    ) VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    company_name,
                    establish_time,
                    address,
                    contact_phone,
                    remark
                ))
                self.connection.commit()  # 提交事务
            except Exception as e:
                self.connection.rollback()  # 出错回滚
                logger.error(f"MySQL 新增公司失败: {e}")
                raise

    def delete_company(self, company_id: int) -> None:
        """删除指定ID的公司记录（返回None，删除失败会抛出异常）

        Args:
            company_id: 公司ID（主键，精确匹配）
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = "DELETE FROM sp_company WHERE company_id = %s"
                cursor.execute(query, (company_id,))
                self.connection.commit()  # 提交事务
            except Exception as e:
                self.connection.rollback()  # 出错回滚
                logger.error(f"MySQL 删除公司失败: {e}")
                raise

    def update_company(
            self,
            company_id: int,
            company_name: Optional[str] = None,
            establish_time: Optional[str] = None,
            address: Optional[str] = None,
            contact_phone: Optional[str] = None,
            remark: Optional[str] = None
    ) -> None:
        """更新公司记录（仅更新非空字段，返回None，更新失败会抛出异常）

        Args:
            company_id: 公司ID（主键，定位要更新的记录）
            company_name: 新公司名称（可选，不可与其他公司重复）
            establish_time: 新成立时间（可选，格式YYYY-MM-DD）
            address: 新地址（可选）
            contact_phone: 新联系电话（可选）
            remark: 新备注信息（可选）
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 动态构建更新字段（仅处理非空参数）
                update_fields = []
                params = []
                if company_name is not None:
                    update_fields.append("company_name = %s")
                    params.append(company_name)
                if establish_time is not None:
                    update_fields.append("establish_time = %s")
                    params.append(establish_time)
                if address is not None:
                    update_fields.append("address = %s")
                    params.append(address)
                if contact_phone is not None:
                    update_fields.append("contact_phone = %s")
                    params.append(contact_phone)
                if remark is not None:
                    update_fields.append("remark = %s")
                    params.append(remark)

                if not update_fields:
                    # 无更新字段时直接返回（不执行SQL）
                    return

                # 拼接更新SQL（包含自动更新时间）
                query = f"""
                    UPDATE sp_company 
                    SET {', '.join(update_fields)}, update_time = CURRENT_TIMESTAMP 
                    WHERE company_id = %s
                """
                params.append(company_id)  # 补充WHERE条件的参数

                cursor.execute(query, tuple(params))
                self.connection.commit()  # 提交事务
            except Exception as e:
                self.connection.rollback()  # 出错回滚
                logger.error(f"MySQL 更新公司失败: {e}")
                raise

    def query_company_by_id(self, company_id: int) :
        """按ID查询公司（返回单条记录字典，不存在则返回None）"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT company_id, company_name FROM sp_company 
                    WHERE company_id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (company_id,))
                return cursor.fetchone()  # 返回单条记录（字典）
            except Exception as e:
                logger.error(f"MySQL 按ID查询公司失败: {e}")
                raise

    def query_company_by_name(self, company_name: str) :
        """按ID查询公司（返回单条记录字典，不存在则返回None）"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT company_id, company_name FROM sp_company 
                    WHERE company_name = %s 
                    LIMIT 1
                """
                cursor.execute(query, (company_name,))
                return cursor.fetchone()  # 返回单条记录（字典）
            except Exception as e:
                logger.error(f"MySQL 按ID查询公司失败: {e}")
                raise

    def query_company_by_name_like(self, company_name: str) :
        """按名称模糊查询公司（返回多条记录列表）"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT company_id, company_name FROM sp_company 
                    WHERE company_name LIKE %s 
                    ORDER BY company_id ASC
                """
                # 在参数中直接构造模糊匹配模式
                search_pattern = f"%{company_name}%"
                cursor.execute(query, (search_pattern,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 模糊查询公司失败: {e}")
                raise

    def query_all_companies(self) :
        """查询所有公司记录"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT company_id, company_name FROM sp_company 
                    ORDER BY company_id ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询所有公司失败: {e}")
                raise

    def insert_department(
            self,
            company_id: int,  # 所属公司ID（外键，必填）
            department_name: str,  # 部门名称（必填）
            manager: Optional[str] = None,  # 部门负责人（可选）
            manager_phone: Optional[str] = None,  # 负责人电话（可选）
            remark: Optional[str] = None  # 备注（可选）
    ) -> None:
        """新增部门记录（需先确认所属公司存在）

        Args:
            company_id: 所属公司ID（外键，必须存在对应的公司）
            department_name: 部门名称（同一公司内不可重复）
            manager: 部门负责人姓名（可选）
            manager_phone: 负责人联系电话（可选）
            remark: 部门备注信息（可选）
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 先检查所属公司是否存在（避免外键约束错误）
                cursor.execute("SELECT company_id FROM sp_company WHERE company_id = %s LIMIT 1", (company_id,))
                if not cursor.fetchone():
                    raise ValueError(f"所属公司ID不存在: {company_id}（外键约束失败）")

                # 插入部门记录
                query = """
                       INSERT INTO sp_department (
                           company_id, department_name, manager, manager_phone, remark
                       ) VALUES (%s, %s, %s, %s, %s)
                   """
                cursor.execute(query, (
                    company_id,
                    department_name,
                    manager,
                    manager_phone,
                    remark
                ))
                self.connection.commit()
                logger.info(f"公司ID【{company_id}】新增部门【{department_name}】成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增部门失败: {e}")
                raise

        # ------------------------------
        # 部门表 - 删除
        # ------------------------------

    def delete_department(self, department_id: int) -> None:
        """删除指定ID的部门记录（若存在下属岗位会因外键约束失败）

        Args:
            department_id: 部门ID（主键）
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 先检查部门是否存在
                cursor.execute("SELECT department_id FROM sp_department WHERE department_id = %s LIMIT 1",
                               (department_id,))
                if not cursor.fetchone():
                    raise ValueError(f"部门ID不存在: {department_id}")

                # 执行删除（受外键约束：若有岗位关联会失败）
                query = "DELETE FROM sp_department WHERE department_id = %s"
                cursor.execute(query, (department_id,))
                self.connection.commit()
                logger.info(f"部门ID【{department_id}】删除成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除部门失败: {e}")
                raise

        # ------------------------------
        # 部门表 - 更新
        # ------------------------------

    def update_department(
            self,
            department_id: int,  # 部门ID（主键，必填）
            company_id: Optional[int] = None,  # 所属公司ID（可选，不建议频繁修改）
            department_name: Optional[str] = None,  # 部门名称（可选）
            manager: Optional[str] = None,  # 负责人（可选）
            manager_phone: Optional[str] = None,  # 负责人电话（可选）
            remark: Optional[str] = None  # 备注（可选）
    ) -> None:
        """更新部门记录（仅更新非空字段，需注意公司内部门名称唯一性）

        Args:
            department_id: 部门ID（定位记录）
            company_id: 新所属公司ID（若修改，需确保公司存在）
            department_name: 新部门名称（若修改，同一公司内不可重复）
            manager: 新负责人（可选）
            manager_phone: 新负责人电话（可选）
            remark: 新备注（可选）
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 先检查部门是否存在
                cursor.execute("SELECT company_id, department_name FROM sp_department WHERE department_id = %s LIMIT 1",
                               (department_id,))
                department = cursor.fetchone()
                if not department:
                    raise ValueError(f"部门ID不存在: {department_id}")
                current_company_id = department[0]  # 当前所属公司ID

                # 动态构建更新字段
                update_fields = []
                params = []

                # 处理公司ID（若修改，需校验新公司存在）
                if company_id is not None and company_id != current_company_id:
                    cursor.execute("SELECT company_id FROM sp_company WHERE company_id = %s LIMIT 1", (company_id,))
                    if not cursor.fetchone():
                        raise ValueError(f"新所属公司ID不存在: {company_id}")
                    update_fields.append("company_id = %s")
                    params.append(company_id)
                    target_company_id = company_id  # 后续校验名称用新公司ID
                else:
                    target_company_id = current_company_id  # 用原公司ID

                # 处理部门名称（若修改，需校验同一公司内不重复）
                if department_name is not None and department_name != department[1]:
                    cursor.execute(
                        "SELECT department_id FROM sp_department WHERE company_id = %s AND department_name = %s LIMIT 1",
                        (target_company_id, department_name)
                    )
                    if cursor.fetchone():
                        raise ValueError(f"公司ID【{target_company_id}】已存在部门【{department_name}】（名称重复）")
                    update_fields.append("department_name = %s")
                    params.append(department_name)

                # 处理其他字段（负责人、电话、备注）
                if manager is not None:
                    update_fields.append("manager = %s")
                    params.append(manager)
                if manager_phone is not None:
                    update_fields.append("manager_phone = %s")
                    params.append(manager_phone)
                if remark is not None:
                    update_fields.append("remark = %s")
                    params.append(remark)

                # 无更新字段则直接返回
                if not update_fields:
                    logger.warning(f"部门ID【{department_id}】无更新字段，跳过更新")
                    return

                # 拼接SQL并执行
                query = f"""
                       UPDATE sp_department 
                       SET {', '.join(update_fields)}, update_time = CURRENT_TIMESTAMP 
                       WHERE department_id = %s
                   """
                params.append(department_id)  # 补充WHERE条件参数

                cursor.execute(query, tuple(params))
                self.connection.commit()
                logger.info(f"部门ID【{department_id}】更新成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新部门失败: {e}")
                raise

        # ------------------------------
        # 部门表 - 查询（按ID）
        # ------------------------------

    def query_department_by_id(self, department_id: int) -> Optional[Dict]:
        """按ID查询部门详情（返回单条记录字典，不存在则返回None）"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                       SELECT department_id, department_name FROM sp_department 
                       WHERE department_id = %s 
                       LIMIT 1
                   """
                cursor.execute(query, (department_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按ID查询部门失败: {e}")
                raise

        # ------------------------------
        # 部门表 - 查询（按公司ID）
        # ------------------------------

    def query_departments_by_company_id(self, company_id: int) -> List[Dict]:
        """查询指定公司下的所有部门（返回列表，无结果则为空列表）"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                       SELECT department_id, department_name FROM sp_department 
                       WHERE company_id = %s 
                       ORDER BY department_id ASC
                   """
                cursor.execute(query, (company_id,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 按公司ID查询部门失败: {e}")
                raise

        # ------------------------------
        # 部门表 - 查询（按名称模糊）
        # ------------------------------

    def query_department_by_name_like(self, department_name: str) -> List[Dict]:
        """按名称模糊查询部门（返回所有匹配记录，跨公司）"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT department_id, department_name FROM sp_department 
                    WHERE department_name LIKE %s 
                    ORDER BY department_id ASC
                """
                search_pattern = f"%{department_name}%"
                cursor.execute(query, (search_pattern,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 模糊查询部门失败: {e}")
                raise

        # ------------------------------
        # 部门表 - 查询（所有）
        # ------------------------------

    def query_all_departments(self) -> List[Dict]:
        """查询所有部门记录（按公司ID和部门ID排序）"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                       SELECT department_id, department_name FROM sp_department 
                       ORDER BY company_id ASC, department_id ASC
                   """
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询所有部门失败: {e}")
                raise

    def insert_post(
            self,
            department_id: int,
            post_name: str,
            duty: Optional[str] = None,
            requirement: Optional[str] = None,
            remark: Optional[str] = None
    ) -> None:
        """新增岗位记录（需先确认所属部门存在，且同一部门内岗位名称不重复）

        Args:
            department_id: 所属部门ID（外键，必须存在对应的部门）
            post_name: 岗位名称（同一部门内不可重复）
            duty: 岗位职责（可选）
            requirement: 任职要求（可选）
            salary_range: 薪资范围（可选，如"5k-10k"）
            remark: 备注信息（可选）

        Raises:
            ValueError: 若部门不存在或岗位名称重复
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 1. 检查所属部门是否存在（外键约束前置校验）
                cursor.execute(
                    "SELECT department_id FROM sp_department WHERE department_id = %s LIMIT 1",
                    (department_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"所属部门ID不存在: {department_id}（外键约束失败）")

                # 2. 检查同一部门内岗位名称是否重复（唯一索引前置校验）
                cursor.execute(
                    "SELECT post_id FROM sp_position WHERE department_id = %s AND post_name = %s LIMIT 1",
                    (department_id, post_name)
                )
                if cursor.fetchone():
                    raise ValueError(f"部门ID【{department_id}】已存在岗位【{post_name}】（名称重复）")

                # 3. 执行插入
                query = """
                    INSERT INTO sp_position (
                        department_id, post_name, duty, requirement, remark
                    ) VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    department_id,
                    post_name,
                    duty,
                    requirement,
                    remark
                ))
                self.connection.commit()
                logger.info(f"部门ID【{department_id}】新增岗位【{post_name}】成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 删除
    # ------------------------------
    def delete_post(self, post_id: int) -> None:
        """删除指定ID的岗位记录（无下游外键约束，直接删除）

        Args:
            post_id: 岗位ID（主键）

        Raises:
            ValueError: 若岗位ID不存在
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 检查岗位是否存在
                cursor.execute(
                    "SELECT post_id FROM sp_position WHERE post_id = %s LIMIT 1",
                    (post_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"岗位ID不存在: {post_id}")

                # 执行删除
                query = "DELETE FROM sp_position WHERE post_id = %s"
                cursor.execute(query, (post_id,))
                self.connection.commit()
                logger.info(f"岗位ID【{post_id}】删除成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 更新
    # ------------------------------
    def update_post(
            self,
            post_id: int,
            department_id: Optional[int] = None,
            post_name: Optional[str] = None,
            duty: Optional[str] = None,
            requirement: Optional[str] = None,
            salary_range: Optional[str] = None,
            remark: Optional[str] = None
    ) -> None:
        """更新岗位记录（仅更新非空字段，需校验部门存在性和名称唯一性）

        Args:
            post_id: 岗位ID（主键，定位记录）
            department_id: 新所属部门ID（可选，需存在）
            post_name: 新岗位名称（可选，同一部门内不可重复）
            duty: 新岗位职责（可选）
            requirement: 新任职要求（可选）
            salary_range: 新薪资范围（可选）
            remark: 新备注（可选）

        Raises:
            ValueError: 若岗位不存在、部门不存在或名称重复
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 1. 检查岗位是否存在
                cursor.execute(
                    "SELECT department_id, post_name FROM sp_position WHERE post_id = %s LIMIT 1",
                    (post_id,)
                )
                post = cursor.fetchone()
                if not post:
                    raise ValueError(f"岗位ID不存在: {post_id}")
                current_department_id = post[0]  # 当前所属部门ID

                # 2. 动态构建更新字段和参数
                update_fields = []
                params = []

                # 处理所属部门ID（若修改，需校验新部门存在）
                if department_id is not None and department_id != current_department_id:
                    cursor.execute(
                        "SELECT department_id FROM sp_department WHERE department_id = %s LIMIT 1",
                        (department_id,)
                    )
                    if not cursor.fetchone():
                        raise ValueError(f"新所属部门ID不存在: {department_id}")
                    update_fields.append("department_id = %s")
                    params.append(department_id)
                    target_department_id = department_id  # 后续校验名称用新部门ID
                else:
                    target_department_id = current_department_id  # 用原部门ID

                # 处理岗位名称（若修改，需校验同一部门内不重复）
                if post_name is not None and post_name != post[1]:
                    cursor.execute(
                        "SELECT post_id FROM sp_position WHERE department_id = %s AND post_name = %s LIMIT 1",
                        (target_department_id, post_name)
                    )
                    if cursor.fetchone():
                        raise ValueError(f"部门ID【{target_department_id}】已存在岗位【{post_name}】（名称重复）")
                    update_fields.append("post_name = %s")
                    params.append(post_name)

                # 处理其他字段（岗位职责、要求等）
                if duty is not None:
                    update_fields.append("duty = %s")
                    params.append(duty)
                if requirement is not None:
                    update_fields.append("requirement = %s")
                    params.append(requirement)
                if salary_range is not None:
                    update_fields.append("salary_range = %s")
                    params.append(salary_range)
                if remark is not None:
                    update_fields.append("remark = %s")
                    params.append(remark)

                # 无更新字段则直接返回
                if not update_fields:
                    logger.warning(f"岗位ID【{post_id}】无更新字段，跳过更新")
                    return

                # 3. 执行更新
                query = f"""
                    UPDATE sp_position 
                    SET {', '.join(update_fields)}, update_time = CURRENT_TIMESTAMP 
                    WHERE post_id = %s
                """
                params.append(post_id)  # 补充WHERE条件参数

                cursor.execute(query, tuple(params))
                self.connection.commit()
                logger.info(f"岗位ID【{post_id}】更新成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（按ID）
    # ------------------------------
    def query_post_by_id(self, post_id: int) -> Optional[Dict]:
        """按ID查询岗位详情（返回单条记录字典，不存在则返回None）

        Args:
            post_id: 岗位ID（主键）

        Returns:
            岗位记录字典（含所有字段），或None
        """
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT post_id, post_name FROM sp_position 
                    WHERE post_id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (post_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按ID查询岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（按部门ID）
    # ------------------------------
    def query_posts_by_department_id(self, department_id: int) -> List[Dict]:
        """查询指定部门下的所有岗位（返回列表，无结果则为空列表）

        Args:
            department_id: 所属部门ID

        Returns:
            岗位记录列表（每个元素为岗位字典）
        """
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT post_id, post_name FROM sp_position 
                    WHERE department_id = %s 
                    ORDER BY post_id ASC
                """
                cursor.execute(query, (department_id,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 按部门ID查询岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（按名称模糊）
    # ------------------------------
    def query_post_by_name_like(self, post_name: str) -> List[Dict]:
        """按名称模糊查询岗位（返回所有匹配记录，跨部门）

        Args:
            post_name: 岗位名称关键词（模糊匹配）

        Returns:
            岗位记录列表（每个元素为岗位字典）
        """
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT post_id, post_name FROM sp_position 
                    WHERE post_name LIKE %s
                    ORDER BY department_id ASC, post_id ASC
                """
                search_pattern = f"%{post_name}%"
                cursor.execute(query, (search_pattern,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 模糊查询岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（所有）
    # ------------------------------
    def query_all_posts(self) -> List[Dict]:
        """查询所有岗位记录（按部门ID和岗位ID排序）

        Returns:
            所有岗位记录列表（每个元素为岗位字典）
        """
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = """
                    SELECT post_id, post_name FROM sp_position 
                    ORDER BY department_id ASC, post_id ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询所有岗位失败: {e}")
                raise

    def query_sops_list_paginated(self, tenant_id: int, keyword: str = "", page: int = 1, page_size: int = 10,
                                   company_id: int = None, department_id: int = None, position_id: str = None,
                                   lang: str = "zh"):
        """分页查询 SOP 列表（包含租户筛选）。

        Args:
            lang: 业务语种，决定查哪张语种表（sp_sop_info_zh/en/th）
        """
        table = self._get_sop_table(lang)
        company_table = self._get_company_table(lang)
        department_table = self._get_department_table(lang)
        position_table = self._get_position_table(lang)
        general_position_name = self._get_general_position_name(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                # 构建查询条件（必须包含租户ID）
                where_conditions = []
                params = []

                # 关键词搜索（假设搜索title字段）
                if keyword:
                    where_conditions.append("s.title LIKE %s")
                    params.append(f"%{keyword}%")

                # 删除公司ID筛选条件 ✅
                # 删除部门ID筛选条件 ✅

                # 岗位ID筛选（验证岗位是否属于该租户，并查询对应的通用岗位）
                # if position_id is not None:
                #     # 验证岗位是否属于该租户
                #     cursor.execute(
                #         "SELECT position_id FROM sp_position WHERE position_id = %s AND tenant_id = %s",
                #         (position_id, tenant_id)
                #     )
                #     if not cursor.fetchone():
                #         # 如果岗位不属于该租户，直接返回空结果
                #         return {
                #             "records": [],
                #             "total": 0,
                #             "page": page,
                #             "page_size": page_size,
                #             "total_pages": 0,
                #             "tenant_id": tenant_id
                #         }

                # 查找该租户下的所有通用岗位ID
                cursor.execute(
                    f"""SELECT position_id FROM {position_table}
                           WHERE tenant_id = %s AND position_name = %s""",
                    (tenant_id, general_position_name)
                )
                general_positions = cursor.fetchall()

                if position_id:
                    where_conditions.append("s.tenant_id = %s")
                    params.append(tenant_id)

                    if general_positions:
                        # 构建IN条件
                        general_position_ids = [str(p['position_id']) for p in general_positions]
                        placeholders = ', '.join(['%s'] * len(general_position_ids))

                        # 条件：指定的个人岗位 OR 通用岗位
                        where_conditions.append(f"(s.position_id = %s OR s.position_id IN ({placeholders}))")
                        params.append(position_id)
                        params.extend(general_position_ids)
                    else:
                        # 如果没有通用岗位，只查询指定岗位
                        where_conditions.append("s.position_id = %s")
                        params.append(position_id)


                # 构建WHERE子句
                where_sql = " AND ".join(where_conditions)

                # 计算偏移量
                offset = (page - 1) * page_size

                # 查询数据
                where_clause = ""
                if where_sql:
                    where_clause = f"WHERE {where_sql}"

                query = f"""
                    SELECT 
                        s.*,
                        p.position_name,
                        d.department_id,
                        d.department_name,
                        c.company_id,
                        c.company_name,
                        s.tenant_id
                    FROM {table} s
                    LEFT JOIN {position_table} p ON s.position_id = p.position_id AND p.tenant_id = s.tenant_id
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id AND d.tenant_id = s.tenant_id
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id AND c.tenant_id = s.tenant_id
                    {where_clause}
                    ORDER BY s.created_at DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([page_size, offset])

                cursor.execute(query, params)
                records = cursor.fetchall()

                # 查询总数
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM {table} s
                    LEFT JOIN {position_table} p ON s.position_id = p.position_id AND p.tenant_id = s.tenant_id
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id AND d.tenant_id = s.tenant_id
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id AND c.tenant_id = s.tenant_id
                    {where_clause}
                """
                cursor.execute(count_query, params[:-2])  # 去掉LIMIT和OFFSET参数
                total_count = cursor.fetchone()['total']

                # 处理percent字段
                for record in records:
                    val = record.get('percent')
                    if val is not None:
                        val_str = str(val).strip()
                        if val_str.endswith('%'):
                            val_str = val_str[:-1]
                        try:
                            record['percent'] = int(float(val_str))
                        except ValueError:
                            record['percent'] = None

                return {
                    "tenant_id": tenant_id,
                    "records": records,
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size
                }

            except Exception as e:
                logger.error(f"MySQL 分页查询SOP列表失败: {e}")
                raise

    def query_sop_info_by_filename(self, file_name: str, lang: str = "zh") -> Optional[Dict]:
        """按文件名查询SOP信息详情。

        Args:
            lang: 业务语种，决定查哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT *
                    FROM {table}
                    WHERE filename = %s 
                    LIMIT 1
                """
                cursor.execute(query, (file_name,))
                result = cursor.fetchone()

                if result:
                    logger.info(f"查询到文件名【{file_name}】的SOP信息记录（{table}）")
                else:
                    logger.warning(f"未找到文件名【{file_name}】的SOP信息记录（{table}）")

                return result
            except Exception as e:
                logger.error(f"MySQL 按文件名查询SOP信息失败: {e}")
                raise

    def query_sop_info_by_id(self, sop_info_id: int, lang: str = "zh") -> Optional[Dict]:
        """按ID查询SOP信息详情。

        Args:
            lang: 业务语种，决定查哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT *
                    FROM {table}
                    WHERE id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (sop_info_id,))
                result = cursor.fetchone()

                if result:
                    logger.info(f"查询到SOP信息ID【{sop_info_id}】的记录（{table}）")
                else:
                    logger.warning(f"未找到SOP信息ID【{sop_info_id}】的记录（{table}）")

                return result
            except Exception as e:
                logger.error(f"MySQL 按ID查询SOP信息失败: {e}")
                raise

    def insert_sop_version(
            self,
            file_name: str,
            version_number: str,
            content: str,
            sop_info_id: int,
            version_name: Optional[str] = None,
            lang: str = "zh",
    ) -> int:
        """插入 SOP 版本记录到对应语种版本表（需校验 sop_info_id + 版本号唯一性）。

        Args:
            file_name: 文件名
            version_number: 版本号
            content: 版本内容（JSON 字符串）
            sop_info_id: 所属 SOP 的 ID（在对应语种表中唯一）
            version_name: 版本名称（可选）
            lang: 业务语种，决定写入哪张语种版本表
                  （sp_sop_version / sp_sop_version_en / sp_sop_version_th）

        Returns:
            新插入记录的版本 ID

        Raises:
            ValueError: 若 sop_info_id + 版本号组合在该语种版本表中已存在
        """
        version_table = self._get_version_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 检查 sop_info_id + 版本号在本语种版本表中是否唯一
                cursor.execute(
                    f"SELECT id FROM {version_table} WHERE sop_info_id = %s AND version_number = %s LIMIT 1",
                    (sop_info_id, version_number)
                )
                if cursor.fetchone():
                    raise ValueError(
                        f"sop_info_id={sop_info_id} 与版本号【{version_number}】的组合在 {version_table} 中已存在"
                    )

                # 执行插入
                query = f"""
                    INSERT INTO {version_table} (file_name, version_number, version_name, content, sop_info_id)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (file_name, version_number, version_name, content, sop_info_id))
                self.connection.commit()

                version_id = cursor.lastrowid
                logger.info(f"SOP版本插入成功，ID: {version_id}，表: {version_table}")
                return version_id
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 插入SOP版本失败（{version_table}）: {e}")
                raise

    def update_sop_info_version_by_id(self, sop_info_id: int, sop_version: str, lang: str = "zh") -> None:
        """根据ID更新语种表中的 sop_version 字段。

        Args:
            sop_info_id: SOP信息ID
            sop_version: 新的SOP版本号
            lang: 业务语种，决定操作哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 先检查记录是否存在
                cursor.execute(
                    f"SELECT id FROM {table} WHERE id = %s LIMIT 1",
                    (sop_info_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"SOP信息ID不存在: {sop_info_id}（{table}）")

                # 执行更新
                query = f"""
                    UPDATE {table} 
                    SET sop_version = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """
                cursor.execute(query, (sop_version, sop_info_id))

                affected_rows = cursor.rowcount
                self.connection.commit()

                if affected_rows > 0:
                    logger.info(f"成功更新SOP信息ID【{sop_info_id}】的版本号为【{sop_version}】（{table}）")
                else:
                    logger.warning(f"更新SOP信息ID【{sop_info_id}】版本号未影响任何记录（{table}）")

            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 按ID更新sop_info版本号失败: {e}")
                raise

    def update_title_by_id(self, record_id: int, title: str, position_id: str = None, lang: str = "zh"):
        """根据记录 ID 更新 title 字段，可选择同时更新 position_id。

        Args:
            lang: 业务语种，决定操作哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                if position_id is not None:
                    query = f"UPDATE {table} SET title = %s, position_id = %s WHERE id = %s"
                    affected_rows = cursor.execute(query, (title, position_id, record_id))
                else:
                    query = f"UPDATE {table} SET title = %s WHERE id = %s"
                    affected_rows = cursor.execute(query, (title, record_id))

                if affected_rows == 0:
                    logger.warning(f"未找到 ID 为 {record_id} 的记录")
                    return False
                logger.info(f"成功更新 ID 为 {record_id} 的记录")
                return True
            except Exception as e:
                logger.error(f"MySQL 更新失败: {e}")
                return False

    def update_sop_info_num_flag(self, sop_id, num_flag, lang: str = "zh"):
        """更新 SOP 信息的 num_flag 字段。

        Args:
            lang: 业务语种，决定操作哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = f"UPDATE {table} SET num_flag = %s WHERE id = %s"
                affected_rows = cursor.execute(query, (num_flag, sop_id))

                if affected_rows == 0:
                    # 可能是值未变化或记录不存在，进行二次检查
                    cursor.execute(f"SELECT num_flag FROM {table} WHERE id = %s LIMIT 1", (sop_id,))
                    row = cursor.fetchone()
                    if not row:
                        logger.warning(f"未找到{table}中id为{sop_id}记录")
                        return False
                    # row 可能是 tuple 或 dict，根据类型取值
                    current_val = row[0] if isinstance(row, tuple) else row.get("num_flag")
                    if str(current_val) == str(num_flag):
                        logger.info(f"记录 id={sop_id} num_flag 已是目标值 {num_flag}，无需更新，视为成功")
                        return True
                    logger.warning(f"记录 id={sop_id} 存在但更新未生效（当前值:{current_val}, 目标值:{num_flag}）")
                    return False

                logger.info(f"成功更新 sop_info 中 id={sop_id} 的 num_flag 为 {num_flag}")
                return True
            except Exception as e:
                logger.error(f"MySQL 更新失败: {e}")
                return False

    def query_sop_id_by_filename_and_position_id(self, filename, position_id, tenant_id, lang: str = "zh"):
        """根据文件名、岗位ID和租户ID查询SOP信息ID。

        Args:
            lang: 业务语种，决定查哪张语种表
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = f"""
                    SELECT id FROM {table}
                    WHERE filename = %s AND position_id = %s AND tenant_id = %s
                """
                cursor.execute(query, (filename, position_id, tenant_id))
                result = cursor.fetchone()
                return result[0] if result else None
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")
                return None

    def query_organization_tree(self, user_id: int, lang: str = "zh") -> List[Dict]:
        """查询当前用户的组织架构树，仅包含对应语种表中有 SOP 的岗位。

        Args:
            user_id: 当前用户ID
            lang: 业务语种，决定从哪张语种表中筛选岗位

        Returns:
            组织架构树形结构列表
            [
                {
                    "id": 1,
                    "name": "公司1",
                    "type": "company",
                    "children": [
                        {
                            "id": 1,
                            "name": "部门1",
                            "type": "department",
                            "children": [
                                {
                                    "id": 1,
                                    "name": "岗位1",
                                    "type": "position",
                                    "is_current": True
                                }
                            ]
                        }
                    ]
                }
            ]
        """
        company_table = self._get_company_table(lang)
        department_table = self._get_department_table(lang)
        position_table = self._get_position_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                # 首先查询当前用户所属的公司、部门、岗位信息和角色
                get_user_info_query = """
                    SELECT 
                        company_id,
                        department_id,
                        position_id,
                        role_id
                    FROM sp_user
                    WHERE id = %s AND is_active = 1
                    LIMIT 1
                """
                cursor.execute(get_user_info_query, (user_id,))
                user_info = cursor.fetchone()

                if not user_info:
                    logger.warning(f"用户 {user_id} 未找到或未激活")
                    return []

                user_company_id = user_info['company_id']
                user_department_id = user_info['department_id']
                user_position_id = user_info['position_id']
                user_role_id = user_info['role_id']

                if not user_company_id or not user_position_id:
                    logger.warning(f"用户 {user_id} 未关联公司或岗位")
                    return []

                # 判断用户是否为管理员（假设role_id=1为管理员，role_id=2为部门管理员等）
                is_admin = user_role_id == 1  # 只有系统管理员可以看到更多

                # 查询对应语种表中存在的岗位及其所属部门和公司信息
                sop_table = self._get_sop_table(lang)
                query = f"""
                    SELECT DISTINCT
                        c.company_id,
                        c.company_name,
                        d.department_id,
                        d.department_name,
                        p.position_id,
                        p.position_name
                    FROM {sop_table} si
                    INNER JOIN {position_table} p ON si.position_id = p.position_id AND p.tenant_id = si.tenant_id
                    INNER JOIN {department_table} d ON p.department_id = d.department_id AND d.tenant_id = si.tenant_id
                    INNER JOIN {company_table} c ON d.company_id = c.company_id AND c.tenant_id = si.tenant_id
                    WHERE c.company_id = %s
                """
                params = [user_company_id]

                if is_admin:
                    # 管理员可以看到整个公司的所有岗位
                    pass
                else:
                    # 非管理员只能看到自己的岗位
                    if user_department_id:
                        # 如果有关联部门，只显示该部门中自己的岗位
                        query += " AND d.department_id = %s AND p.position_id = %s"
                        params.append(user_department_id)
                        params.append(user_position_id)
                    else:
                        # 如果没有关联部门，只显示自己的岗位（通过公司定位）
                        query += " AND p.position_id = %s"
                        params.append(user_position_id)

                query += " ORDER BY c.company_id, d.department_id, p.position_id"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                # 如果没有查询到数据
                if not rows:
                    logger.warning(f"用户 {user_id} 的岗位未在sop_info中找到")
                    return []

                # 构建树形结构
                company_map = {}

                for row in rows:
                    company_id = row['company_id']
                    department_id = row['department_id']
                    position_id = row['position_id']

                    # 构建/获取公司节点
                    if company_id not in company_map:
                        company_map[company_id] = {
                            "id": company_id,
                            "name": row['company_name'],
                            "type": "company",
                            "children": {}
                        }

                    company_node = company_map[company_id]

                    # 构建/获取部门节点
                    if department_id not in company_node['children']:
                        company_node['children'][department_id] = {
                            "id": department_id,
                            "name": row['department_name'],
                            "type": "department",
                            "children": []
                        }

                    department_node = company_node['children'][department_id]

                    # 添加岗位节点，标记当前用户的岗位
                    is_current_position = (position_id == user_position_id)
                    position_node = {
                        "id": position_id,
                        "name": row['position_name'],
                        "type": "position",
                        "is_current": is_current_position
                    }
                    department_node['children'].append(position_node)

                # 转换为列表格式
                result = []
                for company in company_map.values():
                    # 标记当前用户的部门
                    for dept_id, dept in company['children'].items():
                        dept['is_current'] = (dept_id == user_department_id)
                    company['children'] = list(company['children'].values())
                    result.append(company)

                return result

            except Exception as e:
                logger.error(f"查询组织架构树失败: {e}")
                return []

    def query_tenant_by_id(self, tenant_id: int, lang: str = "zh") -> Optional[Dict]:
        """查询租户信息"""
        tenant_table = self._get_tenant_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = """
                    SELECT 
                        tenant_id,
                        tenant_name,
                        status
                    FROM {tenant_table}
                    WHERE tenant_id = %s
                    LIMIT 1
                """
                cursor.execute(query.format(tenant_table=tenant_table), (tenant_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询租户信息失败: {e}")
                raise

    def query_position_by_id(
            self,
            position_id: int,
            lang: str = "zh"
    ) -> Optional[Dict]:
        """根据岗位ID和租户ID查询岗位信息"""
        position_table = self._get_position_table(lang)
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = """
                    SELECT p.*
                    FROM {position_table} p
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id AND d.tenant_id = p.tenant_id
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id AND c.tenant_id = p.tenant_id
                    WHERE p.position_id = %s 
                """
                cursor.execute(
                    query.format(
                        position_table=position_table,
                        department_table=department_table,
                        company_table=company_table,
                    ),
                    (position_id,),
                )
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询岗位失败: {e}")
                raise

    def delete_sop_version(self, sop_id: int, lang: str = "zh"):
        """删除对应语种版本表中、与指定 sop_id 关联的全部 SOP 版本记录。

        Args:
            sop_id: 关联的 SOP ID（对应语种版本表中的 sop_info_id）
            lang: 业务语种，决定操作哪张语种版本表
                  （sp_sop_version / sp_sop_version_en / sp_sop_version_th）
        """
        version_table = self._get_version_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 先检查该语种版本表中是否存在关联记录
                cursor.execute(
                    f"SELECT id FROM {version_table} WHERE sop_info_id = %s LIMIT 1",
                    (sop_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"SOP版本不存在: sop_id={sop_id}，表={version_table}")

                # 执行删除
                query = f"DELETE FROM {version_table} WHERE sop_info_id = %s"
                cursor.execute(query, (sop_id,))
                logger.info(f"SOP版本（sop_id={sop_id}）从 {version_table} 删除成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除SOP版本失败（{version_table}）: {e}")

    def update_percent_by_id(self, sop_info_id: int, percent: str, lang: str = "zh") -> bool:
        """根据 ID 更新语种表中的 percent 字段。

        Args:
            sop_info_id: 记录 ID
            percent: 新的百分比字符串
            lang: 业务语种，决定操作哪张语种表
        Returns:
            True: 更新成功或原值已是目标值；False: 记录不存在或更新失败
        """
        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                sql = f"UPDATE {table} SET percent = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                affected = cursor.execute(sql, (percent, sop_info_id))
                if affected == 0:
                    # 检查是否存在以及是否本来就是该值
                    cursor.execute(f"SELECT percent FROM {table} WHERE id = %s LIMIT 1", (sop_info_id,))
                    row = cursor.fetchone()
                    if not row:
                        logger.warning(f"未找到 sop_info 中 id={sop_info_id} 记录")
                        return False
                    current_val = row[0] if isinstance(row, tuple) else row.get("percent")
                    if str(current_val) == str(percent):
                        logger.info(f"id={sop_info_id} 的 percent 已为目标值 {percent}，视为成功")
                        return True
                    logger.warning(f"id={sop_info_id} 更新未生效，当前值:{current_val} 目标值:{percent}")
                    return False
                logger.info(f"成功更新 sop_info 中 id={sop_info_id} 的 percent 为 {percent}")
                return True
            except Exception as e:
                logger.error(f"MySQL 更新 percent 失败: {e}")
                return False

    def update_sop_info(self, sop_id: int, data: Dict[str, Any], lang: str = "zh") -> bool:
        """通用更新语种表的方法。

        Args:
            sop_id: 要更新的记录ID
            data: 一个字典，键为列名，值为要更新的数据
            lang: 业务语种，决定操作哪张语种表

        Returns:
            如果更新成功或无需更新，返回 True；否则返回 False
        """
        if not data:
            logger.warning("更新数据不能为空")
            return False

        table = self._get_sop_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 动态构建 SET 子句
                set_clauses = [f"`{key}` = %s" for key in data.keys()]
                # 自动更新 updated_at 字段
                set_clauses.append("`updated_at` = CURRENT_TIMESTAMP")

                query = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = %s"

                params = list(data.values())
                params.append(sop_id)

                affected_rows = cursor.execute(query, tuple(params))

                if affected_rows == 0:
                    # 检查记录是否存在，以区分"未找到"和"值未变"
                    cursor.execute(f"SELECT id FROM {table} WHERE id = %s", (sop_id,))
                    if cursor.fetchone():
                        logger.info(f"记录 id={sop_id} 的值未发生变化，无需更新。")
                        return True
                    else:
                        logger.warning(f"未找到 id={sop_id} 的记录，更新失败。")
                        return False

                logger.info(f"成功更新 {table} 中 id={sop_id} 的记录。")
                return True
            except Exception as e:
                logger.error(f"MySQL 更新 {table} 失败: {e}")
                return False

        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 动态构建 SET 子句
                set_clauses = [f"`{key}` = %s" for key in data.keys()]
                # 自动更新 updated_at 字段
                set_clauses.append("`updated_at` = CURRENT_TIMESTAMP")

                query = f"UPDATE sp_sop_info SET {', '.join(set_clauses)} WHERE id = %s"

                params = list(data.values())
                params.append(sop_id)

                affected_rows = cursor.execute(query, tuple(params))

                if affected_rows == 0:
                    # 检查记录是否存在，以区分“未找到”和“值未变”
                    cursor.execute("SELECT id FROM sp_sop_info WHERE id = %s", (sop_id,))
                    if cursor.fetchone():
                        logger.info(f"记录 id={sop_id} 的值未发生变化，无需更新。")
                        return True
                    else:
                        logger.warning(f"未找到 id={sop_id} 的记录，更新失败。")
                        return False

                logger.info(f"成功更新 sp_sop_info 表中 id={sop_id} 的记录。")
                return True
            except Exception as e:
                logger.error(f"MySQL 更新 sp_sop_info 失败: {e}")
                return False
