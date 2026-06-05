# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import pymysql
from threading import Lock

from pymysql.cursors import DictCursor

from comps import CustomLogger
import os
from typing import Optional, Dict, List

logger = CustomLogger("prepare_execl_milvus", os.getenv("LOG_LEVEL", "INFO"))


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

    @staticmethod
    def _resolve_lang(lang: Optional[str]) -> str:
        if lang in ("zh", "en", "th"):
            return lang
        return "zh"

    def _table_name(self, base_table: str, lang: Optional[str] = "zh") -> str:
        resolved = self._resolve_lang(lang)
        if resolved == "zh":
            return base_table
        return f"{base_table}_{resolved}"

    def _get_tenant_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_tenant", lang)

    def _get_company_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_company", lang)

    def _get_department_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_department", lang)

    def _get_position_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_position", lang)

    def _get_sop_info_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_sop_info", lang)

    def _get_sop_version_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_sop_version", lang)

    def _get_course_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_course", lang)

    def _get_material_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_material", lang)

    def _get_default_company_entities_text(self, lang: Optional[str] = "zh") -> Dict[str, str]:
        resolved = self._resolve_lang(lang)
        if resolved == "en":
            return {
                "department_name": "General Department",
                "department_remark": "System auto-created default company department",
                "position_name": "General Position",
                "position_duty": "General position responsibilities, can be adjusted as needed",
                "position_requirement": "General position requirements",
                "position_remark": "System auto-created general position",
            }
        if resolved == "th":
            return {
                "department_name": "แผนกทั่วไป",
                "department_remark": "แผนกเริ่มต้นของบริษัทที่ระบบสร้างอัตโนมัติ",
                "position_name": "ตำแหน่งทั่วไป",
                "position_duty": "หน้าที่ของตำแหน่งทั่วไป สามารถปรับได้ตามต้องการ",
                "position_requirement": "คุณสมบัติของตำแหน่งทั่วไป",
                "position_remark": "ตำแหน่งทั่วไปที่ระบบสร้างอัตโนมัติ",
            }
        return {
            "department_name": "通用部门",
            "department_remark": "系统自动创建的公司默认部门",
            "position_name": "通用岗位",
            "position_duty": "通用岗位职责，可根据需要调整",
            "position_requirement": "通用任职要求",
            "position_remark": "系统自动创建的通用岗位",
        }

    def insert_sops(self, task_id, title, filename, task_status,position_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = "INSERT INTO sop_info (task_id, title, filename, task_status, position_id) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (task_id, title, filename, task_status,position_id))
            except Exception as e:
                logger.error(f"MySQL 插入失败: {e}")

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

    def query_sop_existing_id(self, position_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 校验类型名称是否已存在
                check_sql = "SELECT position_id FROM sop_type WHERE position_id = %s"
                cursor.execute(check_sql, (position_id))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")

    def check_duplicate_sop_type(self, new_sop_type_name, position_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                check_duplicate_sql = """
                    SELECT position_id FROM sop_type 
                    WHERE sop_type_name = %s AND position_id != %s
                """
                cursor.execute(check_duplicate_sql, (new_sop_type_name,position_id))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")

    def update_sop_type(self, new_sop_type_name, position_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                update_sql = "UPDATE sop_type SET sop_type_name = %s WHERE position_id = %s"
                cursor.execute(update_sql, (new_sop_type_name, position_id))
            except Exception as e:
                logger.error(f"MySQL 修改失败: {e}")

    def delete_sop_type(self, position_id):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 执行删除操作
                delete_sql = "DELETE FROM sop_type WHERE position_id = %s"
                cursor.execute(delete_sql, (position_id))
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

    def query_sops_by_task_id(self, task_id):
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = "SELECT * FROM sop_info WHERE task_id = %s"
                cursor.execute(query, (task_id,))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")
                return None

    def query_sops_by_filename(self, file_name):
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = "SELECT * FROM sop_info WHERE filename = %s"
                cursor.execute(query, (file_name,))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询失败: {e}")
                return None

    def update_sops(self, filename, task_status, remark="无"):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = "UPDATE sop_info SET task_status = %s, remark = %s WHERE filename = %s"
                cursor.execute(query, (task_status, remark, filename))
            except Exception as e:
                logger.error(f"MySQL 更新失败: {e}")

    def query_sops_list(self):
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = "SELECT * FROM sop_info"
                cursor.execute(query)
                result = cursor.fetchall()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询列表失败: {e}")
                return []

    def delete_sops(self, filename: str):
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = "DELETE FROM sop_info WHERE filename = %s"
                cursor.execute(query, (filename,))
            except Exception as e:
                logger.error(f"MySQL 删除失败: {e}")

    def insert_company(
            self,
            company_name: str,
            tenant_id: int,
            establish_time: Optional[str] = None,
            address: Optional[str] = None,
            contact_phone: Optional[str] = None,
            remark: Optional[str] = None,
            create_default_entities: bool = True,  # 新增参数：是否创建默认部门和岗位
            lang: str = "zh",
    ) -> dict:
        """新增公司记录（包含租户信息）并可选创建默认部门、岗位

        Returns:
            dict: 包含公司ID、部门ID、岗位ID的字典
        """
        self._connect()
        company_table = self._get_company_table(lang)
        department_table = self._get_department_table(lang)
        position_table = self._get_position_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 1. 创建公司
                query = f"""
                    INSERT INTO {company_table} (
                        company_name, tenant_id, establish_time, address, contact_phone, remark
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    company_name,
                    tenant_id,
                    establish_time,
                    address,
                    contact_phone,
                    remark
                ))
                company_id = cursor.lastrowid

                department_id = None
                position_id = None

                # 2. 如果要求，创建默认部门和岗位
                if create_default_entities:
                    default_text = self._get_default_company_entities_text(lang)
                    # 2.1 创建默认部门
                    default_dept_name = default_text["department_name"]
                    dept_query = f"""
                        INSERT INTO {department_table} (
                            tenant_id, department_name, company_id, remark
                        ) VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(dept_query, (
                        tenant_id,
                        default_dept_name,
                        company_id,
                        default_text["department_remark"],
                    ))
                    department_id = cursor.lastrowid

                    # 2.2 创建通用岗位
                    general_position_name = default_text["position_name"]
                    position_query = f"""
                        INSERT INTO {position_table} (
                            tenant_id, department_id, position_name, duty, requirement, remark
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(position_query, (
                        tenant_id,
                        department_id,
                        general_position_name,
                        default_text["position_duty"],
                        default_text["position_requirement"],
                        default_text["position_remark"],
                    ))
                    position_id = cursor.lastrowid

                # 提交事务
                self.connection.commit()

                logger.info(f"租户【{tenant_id}】新增公司【{company_name}】成功，公司ID: {company_id}")

                # 返回包含所有ID的字典
                return {
                    "company_id": company_id,
                    "department_id": department_id,
                    "position_id": position_id,
                    "default_department_name": "通用部门" if department_id else None,
                    "default_position_name": "通用岗位" if position_id else None
                }

            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增公司及默认实体失败: {e}")
                raise

    def query_company_by_name_and_tenant(self, company_name: str, tenant_id: int, lang: str = "zh") -> Optional[Dict]:
        """按公司名称和租户ID查询公司"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT company_id, company_name, tenant_id 
                    FROM {company_table}
                    WHERE company_name = %s AND tenant_id = %s
                    LIMIT 1
                """
                cursor.execute(query, (company_name, tenant_id))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按名称和租户查询公司失败: {e}")
                raise

    def delete_company(self, company_id: int, lang: str = "zh") -> None:
        """删除指定ID的公司记录（手动检查下属部门，替代外键约束）

        Args:
            company_id: 公司ID（主键，精确匹配）

        Raises:
            ValueError: 公司不存在或存在下属部门时抛出
            Exception: 数据库操作异常时抛出
        """
        self._connect()
        company_table = self._get_company_table(lang)
        department_table = self._get_department_table(lang)
        with self.connection.cursor() as cursor:
            try:

                # 1. 手动查询关联的部门（替代外键约束校验）
                cursor.execute(
                    f"SELECT department_id FROM {department_table} WHERE company_id = %s LIMIT 1",
                    (company_id,)
                )
                if cursor.fetchone():
                    raise ValueError(
                        f"公司ID【{company_id}】存在下属部门，无法删除（请先删除关联部门）"
                    )

                # 2. 执行公司删除操作
                delete_query = f"DELETE FROM {company_table} WHERE company_id = %s"
                cursor.execute(delete_query, (company_id,))
                self.connection.commit()
                logger.info(f"公司ID【{company_id}】删除成功")

            except ValueError as ve:
                # 业务逻辑异常（公司不存在/有下属部门）
                self.connection.rollback()
                logger.error(f"删除公司失败: {ve}")
                raise  # 向上抛出业务异常，便于上层处理
            except Exception as e:
                # 数据库系统异常（如连接错误、SQL语法错误等）
                self.connection.rollback()
                logger.error(f"MySQL 删除公司失败: {str(e)}", exc_info=True)
                raise  # 向上抛出系统异常

    def update_company(
            self,
            company_id: int,
            tenant_id: int,  # 新增：用于验证
            company_name: Optional[str] = None,
            establish_time: Optional[str] = None,
            address: Optional[str] = None,
            contact_phone: Optional[str] = None,
            remark: Optional[str] = None,
            lang: str = "zh",
    ) -> None:
        """更新公司记录（包含租户验证）"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 验证公司是否属于指定租户
                cursor.execute(
                    f"SELECT company_id FROM {company_table} WHERE company_id = %s AND tenant_id = %s LIMIT 1",
                    (company_id, tenant_id)
                )
                if not cursor.fetchone():
                    raise ValueError(f"公司ID【{company_id}】不属于租户【{tenant_id}】")

                # 动态构建更新字段
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
                    return

                # 拼接更新SQL
                query = f"""
                    UPDATE {company_table}
                    SET {', '.join(update_fields)}, update_time = CURRENT_TIMESTAMP 
                    WHERE company_id = %s AND tenant_id = %s
                """
                params.extend([company_id, tenant_id])

                cursor.execute(query, tuple(params))
                self.connection.commit()
                logger.info(f"租户【{tenant_id}】公司ID【{company_id}】更新成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新公司失败: {e}")
                raise

    def query_company_by_id(self, company_id: int, lang: str = "zh") :
        """按ID查询公司（返回单条记录字典，不存在则返回None）"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT * FROM {company_table}
                    WHERE company_id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (company_id,))
                return cursor.fetchone()  # 返回单条记录（字典）
            except Exception as e:
                logger.error(f"MySQL 按ID查询公司失败: {e}")
                raise

    def query_company_by_name(self, company_name: str, lang: str = "zh") :
        """按ID查询公司（返回单条记录字典，不存在则返回None）"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT company_id, company_name FROM {company_table}
                    WHERE company_name = %s 
                    LIMIT 1
                """
                cursor.execute(query, (company_name,))
                return cursor.fetchone()  # 返回单条记录（字典）
            except Exception as e:
                logger.error(f"MySQL 按ID查询公司失败: {e}")
                raise

    def query_company_by_name_like(self, company_name: str, lang: str = "zh") :
        """按名称模糊查询公司（返回多条记录列表）"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT company_id, company_name FROM {company_table}
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

    def query_all_companies(self, lang: str = "zh") :
        """查询所有公司记录"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT company_id, company_name FROM {company_table}
                    ORDER BY company_id ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询所有公司失败: {e}")
                raise

    def insert_department(
            self,
            company_id: int,
            department_name: str,
            tenant_id: int,  # 新增：租户ID
            manager: Optional[str] = None,
            manager_phone: Optional[str] = None,
            remark: Optional[str] = None,
            lang: str = "zh",
    ) -> int:
        """新增部门记录（包含租户信息）"""
        self._connect()
        company_table = self._get_company_table(lang)
        department_table = self._get_department_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 验证公司是否属于指定租户
                cursor.execute(
                    f"SELECT tenant_id FROM {company_table} WHERE company_id = %s",
                    (company_id,)
                )
                company = cursor.fetchone()
                if not company:
                    raise ValueError(f"所属公司ID不存在: {company_id}")

                # if company[0] != tenant_id:
                #     raise ValueError(f"公司ID【{company_id}】不属于租户【{tenant_id}】")

                # 检查同一公司内部门名称是否重复
                cursor.execute(
                    f"SELECT department_id FROM {department_table} WHERE company_id = %s AND department_name = %s LIMIT 1",
                    (company_id, department_name)
                )
                if cursor.fetchone():
                    raise ValueError(f"公司ID【{company_id}】已存在部门【{department_name}】（名称重复）")

                # 插入部门记录
                query = f"""
                    INSERT INTO {department_table} (
                        company_id, tenant_id, department_name, manager, manager_phone, remark
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    company_id,
                    tenant_id,  # 新增
                    department_name,
                    manager,
                    manager_phone,
                    remark
                ))

                department_id = cursor.lastrowid
                self.connection.commit()
                logger.info(
                    f"租户【{tenant_id}】公司ID【{company_id}】新增部门【{department_name}】成功，部门ID: {department_id}")
                return department_id
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增部门失败: {e}")
                raise

    def delete_department(self, department_id: int, tenant_id: int = None, lang: str = "zh") -> None:
        """删除部门记录（可选租户验证）"""
        self._connect()
        department_table = self._get_department_table(lang)
        position_table = self._get_position_table(lang)
        with self.connection.cursor() as cursor:
            try:
                where_clauses = ["department_id = %s"]
                params = [department_id]

                # 如果提供了租户ID，加入租户验证
                if tenant_id and tenant_id != 1:
                    where_clauses.append("tenant_id = %s")
                    params.append(tenant_id)

                # 检查部门是否存在
                check_query = f"""
                    SELECT department_id FROM {department_table}
                    WHERE {' AND '.join(where_clauses)} 
                    LIMIT 1
                """
                cursor.execute(check_query, tuple(params))
                if not cursor.fetchone():
                    if tenant_id:
                        raise ValueError(f"部门ID【{department_id}】不存在或不属于租户【{tenant_id}】")
                    else:
                        raise ValueError(f"部门ID不存在: {department_id}")

                # 手动查询关联的岗位（替代外键约束校验）
                cursor.execute(
                    f"SELECT position_id FROM {position_table} WHERE department_id = %s LIMIT 1",
                    (department_id,)
                )
                if cursor.fetchone():
                    raise ValueError(
                        f"部门ID【{department_id}】存在下属岗位，无法删除（请先删除关联岗位）"
                    )

                # 执行删除
                delete_query = f"""
                    DELETE FROM {department_table}
                    WHERE {' AND '.join(where_clauses)}
                """
                cursor.execute(delete_query, tuple(params))
                self.connection.commit()
                logger.info(f"部门ID【{department_id}】删除成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除部门失败: {e}")
                raise

    def update_department(
            self,
            department_id: int,
            tenant_id: int,  # 新增：租户ID（用于验证）
            company_id: Optional[int] = None,
            department_name: Optional[str] = None,
            manager: Optional[str] = None,
            manager_phone: Optional[str] = None,
            remark: Optional[str] = None,
            lang: str = "zh",
    ) -> None:
        """更新部门记录（包含租户验证）"""
        self._connect()
        company_table = self._get_company_table(lang)
        department_table = self._get_department_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 查询当前部门信息并验证租户
                cursor.execute(
                    f"SELECT company_id, department_name, tenant_id FROM {department_table} WHERE department_id = %s LIMIT 1",
                    (department_id,)
                )
                department = cursor.fetchone()
                if not department:
                    raise ValueError(f"部门ID不存在: {department_id}")

                current_company_id = department[0]
                current_department_name = department[1]
                current_tenant_id = department[2]

                # 验证部门是否属于指定租户
                if current_tenant_id != tenant_id:
                    raise ValueError(f"部门ID【{department_id}】不属于租户【{tenant_id}】")

                # 动态构建更新字段
                update_fields = []
                params = []

                # 处理公司ID（若修改，需校验新公司存在且属于同一租户）
                if company_id is not None and company_id != current_company_id:
                    cursor.execute(
                        f"SELECT tenant_id FROM {company_table} WHERE company_id = %s LIMIT 1",
                        (company_id,)
                    )
                    company = cursor.fetchone()
                    if not company:
                        raise ValueError(f"新所属公司ID不存在: {company_id}")

                    if company[0] != tenant_id:
                        raise ValueError(f"新公司ID【{company_id}】不属于租户【{tenant_id}】")

                    update_fields.append("company_id = %s")
                    params.append(company_id)
                    target_company_id = company_id
                else:
                    target_company_id = current_company_id

                # 处理部门名称（若修改，需校验同一公司内不重复）
                if department_name is not None and department_name != current_department_name:
                    cursor.execute(
                        f"SELECT department_id FROM {department_table} WHERE company_id = %s AND department_name = %s LIMIT 1",
                        (target_company_id, department_name)
                    )
                    if cursor.fetchone():
                        raise ValueError(f"公司ID【{target_company_id}】已存在部门【{department_name}】（名称重复）")
                    update_fields.append("department_name = %s")
                    params.append(department_name)

                # 处理其他字段
                if manager is not None:
                    update_fields.append("manager = %s")
                    params.append(manager)
                if manager_phone is not None:
                    update_fields.append("manager_phone = %s")
                    params.append(manager_phone)
                if remark is not None:
                    update_fields.append("remark = %s")
                    params.append(remark)

                if not update_fields:
                    logger.warning(f"部门ID【{department_id}】无更新字段，跳过更新")
                    return

                # 执行更新
                query = f"""
                    UPDATE {department_table}
                    SET {', '.join(update_fields)}, update_time = CURRENT_TIMESTAMP 
                    WHERE department_id = %s AND tenant_id = %s
                """
                params.extend([department_id, tenant_id])

                cursor.execute(query, tuple(params))
                self.connection.commit()
                logger.info(f"租户【{tenant_id}】部门ID【{department_id}】更新成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新部门失败: {e}")
                raise

    def query_department_by_id_tenant_id(
            self,
            department_id: int,
            tenant_id: int,
            lang: str = "zh",
    ) -> Optional[Dict]:
        """根据部门ID和租户ID查询部门信息"""
        self._connect()
        department_table = self._get_department_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"""
                    SELECT * FROM {department_table}
                    WHERE department_id = %s AND tenant_id = %s
                """
                cursor.execute(query, (department_id, tenant_id))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询部门失败: {e}")
                return None

    def query_department_by_id(self, department_id: int, lang: str = "zh") -> Optional[Dict]:
        """按ID查询部门详情（包含租户信息）"""
        self._connect()
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT 
                        d.*,
                        c.company_name,
                        c.tenant_id as company_tenant_id
                    FROM {department_table} d
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE d.department_id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (department_id,))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 按ID查询部门失败: {e}")
                raise

        # ------------------------------
        # 部门表 - 查询（按公司ID）
        # ------------------------------

    def query_departments_by_company_id(self, company_id: int, lang: str = "zh") -> List[Dict]:
        """查询指定公司下的所有部门（返回列表，无结果则为空列表）"""
        self._connect()
        department_table = self._get_department_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                       SELECT department_id, department_name FROM {department_table}
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

    def query_department_by_name_like(self, department_name: str, lang: str = "zh") -> List[Dict]:
        """按名称模糊查询部门（返回所有匹配记录，跨公司）"""
        self._connect()
        department_table = self._get_department_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT department_id, department_name FROM {department_table}
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

    def query_all_departments(self, lang: str = "zh") -> List[Dict]:
        """查询所有部门记录（按公司ID和部门ID排序）"""
        self._connect()
        department_table = self._get_department_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                       SELECT department_id, department_name FROM {department_table}
                       ORDER BY company_id ASC, department_id ASC
                   """
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询所有部门失败: {e}")
                raise

    def insert_post(
            self,
            tenant_id: int,
            department_id: int,
            position_name: str,
            duty: str = None,
            requirement: str = None,
            remark: str = None,
            lang: str = "zh",
    ) -> int:
        """新增岗位记录（包含租户信息）"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        position_table = self._get_position_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 验证租户是否存在
                cursor.execute(
                    f"SELECT tenant_id FROM {tenant_table} WHERE tenant_id = %s AND status = 1",
                    (tenant_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"租户ID不存在或已停用: {tenant_id}")

                # 验证部门是否存在且属于该租户
                # cursor.execute(
                #     "SELECT department_id FROM sp_department WHERE department_id = %s AND tenant_id = %s",
                #     (department_id, tenant_id)
                # )
                # if not cursor.fetchone():
                #     raise ValueError(f"部门ID不存在或不属于该租户: {department_id}")

                # 插入岗位记录
                query = f"""
                    INSERT INTO {position_table} (
                        tenant_id, department_id, position_name, 
                        duty, requirement, remark
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """

                cursor.execute(query, (
                    tenant_id, department_id, position_name,
                    duty, requirement, remark
                ))

                position_id = cursor.lastrowid
                self.connection.commit()
                logger.info(f"租户【{tenant_id}】新增岗位【{position_name}】成功，岗位ID: {position_id}")

                return position_id
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 删除
    # ------------------------------
    def delete_post(
            self,
            position_id: int,
            tenant_id: int,  # 新增参数
            lang: str = "zh",
    ) -> None:
        """删除岗位（包含租户验证）"""
        self._connect()
        position_table = self._get_position_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 物理删除或逻辑删除（根据业务需求选择）
                # 物理删除：
                if tenant_id == 1:
                    # 超级管理员不进行租户验证
                    query = f"DELETE FROM {position_table} WHERE position_id = %s"
                    cursor.execute(query, (position_id))
                else:
                    query = f"DELETE FROM {position_table} WHERE position_id = %s AND tenant_id = %s"
                    cursor.execute(query, (position_id, tenant_id))

                # 或者逻辑删除（推荐）：
                # query = """
                #     UPDATE sp_position
                #     SET is_deleted = 1, update_time = CURRENT_TIMESTAMP
                #     WHERE position_id = %s AND tenant_id = %s
                # """
                # cursor.execute(query, (position_id, tenant_id))

                self.connection.commit()

                if cursor.rowcount == 0:
                    raise ValueError(f"岗位ID【{position_id}】不存在或不属于租户【{tenant_id}】")

                logger.info(f"租户【{tenant_id}】删除岗位ID【{position_id}】成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 更新
    # ------------------------------
    def update_post(
            self,
            position_id: int,
            tenant_id: int,  # 新增参数
            department_id: int = None,
            position_name: str = None,
            duty: str = None,
            requirement: str = None,
            remark: str = None,
            lang: str = "zh",
    ) -> None:
        """更新岗位信息（包含租户验证）"""
        self._connect()
        position_table = self._get_position_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 构建更新字段
                update_fields = []
                params = []

                if department_id is not None:
                    update_fields.append("department_id = %s")
                    params.append(department_id)
                if position_name is not None:
                    update_fields.append("position_name = %s")
                    params.append(position_name)
                if duty is not None:
                    update_fields.append("duty = %s")
                    params.append(duty)
                if requirement is not None:
                    update_fields.append("requirement = %s")
                    params.append(requirement)
                if remark is not None:
                    update_fields.append("remark = %s")
                    params.append(remark)

                if not update_fields:
                    return  # 没有要更新的字段

                update_fields.append("update_time = CURRENT_TIMESTAMP")


                if tenant_id == 1:
                    # 超级管理员不进行租户验证
                    query = f"""
                        UPDATE {position_table}
                        SET {', '.join(update_fields)} 
                        WHERE position_id = %s
                    """
                    params.append(position_id)
                else:
                    # 添加WHERE条件（包含租户验证）
                    query = f"""
                        UPDATE {position_table}
                        SET {', '.join(update_fields)} 
                        WHERE position_id = %s AND tenant_id = %s
                    """
                    params.extend([position_id, tenant_id])

                cursor.execute(query, tuple(params))
                self.connection.commit()

                if cursor.rowcount == 0:
                    raise ValueError(f"岗位ID【{position_id}】不存在或不属于租户【{tenant_id}】")

                logger.info(f"租户【{tenant_id}】更新岗位ID【{position_id}】成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新岗位失败: {e}")
                raise

    def query_position_by_id_and_tenant(
            self,
            position_id: int,
            tenant_id: int,
            lang: str = "zh",
    ) -> Optional[Dict]:
        """根据岗位ID和租户ID查询岗位信息"""
        self._connect()
        position_table = self._get_position_table(lang)
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"""
                    SELECT p.*, d.department_name, c.company_name
                    FROM {position_table} p
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE p.position_id = %s AND p.tenant_id = %s
                """
                cursor.execute(query, (position_id, tenant_id))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询岗位失败: {e}")
                raise
    # ------------------------------
    # 岗位表 - 查询（按ID）
    # ------------------------------
    def query_position_by_id(self, position_id: int, lang: str = "zh") -> Optional[Dict]:
        """按ID查询岗位详情（返回单条记录字典，不存在则返回None）

        Args:
            position_id: 岗位ID（主键）

        Returns:
            岗位记录字典（含所有字段），或None
        """
        self._connect()
        position_table = self._get_position_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT * FROM {position_table}
                    WHERE position_id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (position_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按ID查询岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（按部门ID）
    # ------------------------------
    def query_posts_by_department_id(self, department_id: int, lang: str = "zh") -> List[Dict]:
        """查询指定部门下的所有岗位（返回列表，无结果则为空列表）

        Args:
            department_id: 所属部门ID

        Returns:
            岗位记录列表（每个元素为岗位字典）
        """
        self._connect()
        position_table = self._get_position_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT position_id, position_name FROM {position_table}
                    WHERE department_id = %s and position_name != '通用岗位'
                    ORDER BY position_id ASC
                """
                cursor.execute(query, (department_id,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 按部门ID查询岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（按名称模糊）
    # ------------------------------
    def query_position_by_name_like(self, position_name: str, lang: str = "zh") -> List[Dict]:
        """按名称模糊查询岗位（返回所有匹配记录，跨部门）

        Args:
            position_name: 岗位名称关键词（模糊匹配）

        Returns:
            岗位记录列表（每个元素为岗位字典）
        """
        self._connect()
        position_table = self._get_position_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT position_id, position_name FROM {position_table}
                    WHERE position_name LIKE %s
                    ORDER BY department_id ASC, position_id ASC
                """
                search_pattern = f"%{position_name}%"
                cursor.execute(query, (search_pattern,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 模糊查询岗位失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（所有）
    # ------------------------------
    def query_all_posts(self, lang: str = "zh") -> List[Dict]:
        """查询所有岗位记录（按部门ID和岗位ID排序）

        Returns:
            所有岗位记录列表（每个元素为岗位字典）
        """
        self._connect()
        position_table = self._get_position_table(lang)
        with self.connection.cursor(DictCursor) as cursor:  # 指定使用字典游标
            try:
                query = f"""
                    SELECT position_id, position_name FROM {position_table}
                    ORDER BY department_id ASC, position_id ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询所有岗位失败: {e}")
                raise

    def query_posts_by_multiple_conditions(
            self,
            tenant_id: int = None,  # None 表示 OWNER 查全局，否则过滤指定租户
            position_id: int = None,
            department_id: int = None,
            position_name: str = None,
            lang: str = "zh",
    ) -> List[Dict]:
        """根据多个条件查询岗位列表（tenant_id=None 时查全局，否则过滤指定租户）"""
        self._connect()
        position_table = self._get_position_table(lang)
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                where_clauses = ["1=1"]
                params = []

                if tenant_id is not None:
                    where_clauses.append("p.tenant_id = %s")
                    params.append(tenant_id)
                # tenant_id is None（OWNER）→ 不加租户过滤，查全局

                if position_id is not None:
                    where_clauses.append("p.position_id = %s")
                    params.append(position_id)
                if department_id is not None:
                    where_clauses.append("p.department_id = %s")
                    params.append(department_id)
                if position_name is not None:
                    where_clauses.append("p.position_name = %s")
                    params.append(position_name)

                query = f"""
                    SELECT p.*, d.department_name, c.company_name
                    FROM {position_table} p
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY p.create_time DESC
                """

                cursor.execute(query, tuple(params))
                results = cursor.fetchall()

                for item in results:
                    item['position_id'] = str(item['position_id'])
                    if 'company_id' in item:
                        item['company_id'] = str(item['company_id'])
                    if 'department_id' in item:
                        item['department_id'] = str(item['department_id'])

                return results
            except Exception as e:
                logger.error(f"MySQL 查询岗位列表失败: {e}")
                raise

    def query_posts_with_company_department(
            self,
            conditions: Dict,
            offset: int = 0,
            limit: int = 10,
            lang: str = "zh",
    ) -> List[Dict]:
        """多表关联查询岗位（包含公司、部门信息，支持租户筛选）"""
        self._connect()
        position_table = self._get_position_table(lang)
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                # 基础查询
                query = f"""
                    SELECT 
                        p.position_id, p.position_name, p.duty, p.requirement, p.remark,
                        p.department_id, d.department_name,
                        d.company_id, c.company_name,
                        p.create_time, p.update_time,
                        p.tenant_id
                    FROM {position_table} p
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE 1=1
                """
                params = []

                # 检查租户ID是否为1
                is_tenant_one = False
                for key in ['tenant_id', 'p.tenant_id']:
                    if key in conditions and str(conditions[key]) == '1':
                        is_tenant_one = True

                        break

                # 处理条件
                for key, value in conditions.items():


                    if 'position_name' in key:
                        # 岗位名称条件总是要处理
                        if key.endswith('__like'):
                            field = key.replace('__like', '')
                            query += f" AND {field} LIKE %s"
                            params.append(value)
                        else:
                            query += f" AND {key} = %s"
                            params.append(value)
                    elif not is_tenant_one:
                        if key in ['tenant_id', 'p.tenant_id']:
                            # 租户ID条件已经在上面处理过了
                            query += " AND p.tenant_id = %s"
                            params.append(conditions.get("p.tenant_id"))
                            continue
                        # 非租户1的情况，处理所有条件
                        if key.endswith('__like'):
                            field = key.replace('__like', '')
                            query += f" AND {field} LIKE %s"
                            params.append(value)
                        else:
                            query += f" AND {key} = %s"
                            params.append(value)
                    # 租户1的情况下，其他条件被忽略

                query += " ORDER BY p.create_time DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cursor.execute(query, tuple(params))
                results = cursor.fetchall()

                # 转换数据类型
                for item in results:
                    item['position_id'] = str(item['position_id'])
                    if 'company_id' in item:
                        item['company_id'] = str(item['company_id'])
                    if 'department_id' in item:
                        item['department_id'] = str(item['department_id'])

                return results
            except Exception as e:
                logger.error(f"MySQL 多表查询岗位失败: {e}")
                raise

    def query_departments_by_multiple_conditions(self, lang: str = "zh", **conditions) -> List[Dict]:
        """多条件并联查询部门记录（tenant_id=None 时查全局，否则过滤指定租户）"""
        self._connect()
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = []
                params = []

                tenant_id = conditions.get('tenant_id')
                if tenant_id is not None:
                    where_clauses.append("d.tenant_id = %s")
                    params.append(tenant_id)
                # tenant_id is None（OWNER）→ 不加租户过滤，查全局

                if 'department_id' in conditions and conditions['department_id'] is not None:
                    where_clauses.append("d.department_id = %s")
                    params.append(conditions['department_id'])

                if 'company_id' in conditions and conditions['company_id'] is not None:
                    where_clauses.append("d.company_id = %s")
                    params.append(conditions['company_id'])

                if 'department_name__like' in conditions and conditions['department_name__like'] is not None:
                    where_clauses.append("d.department_name LIKE %s")
                    params.append(conditions['department_name__like'])
                elif 'department_name' in conditions and conditions['department_name'] is not None:
                    where_clauses.append("d.department_name = %s")
                    params.append(conditions['department_name'])

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                query = f"""
                    SELECT 
                        d.*,
                        c.company_name
                    FROM {department_table} d
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE {where_sql}
                    ORDER BY d.company_id ASC, d.department_id ASC
                """

                cursor.execute(query, params)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 多条件查询部门失败: {e}")
                raise

    # 同时需要修改 count_posts_with_company_department 方法（适配conditions字典入参）
    def count_posts_with_company_department(self, lang: str = "zh", **conditions) -> int:
        """统计多表关联查询的记录数"""
        self._connect()
        position_table = self._get_position_table(lang)
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor() as cursor:
            try:
                query = f"""
                    SELECT COUNT(*) as total
                    FROM {position_table} p
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE 1=1
                """
                params = []

                # 检查租户ID是否为1
                is_tenant_one = False
                tenant_id_keys = ['tenant_id', 'p.tenant_id']
                for key in tenant_id_keys:
                    if key in conditions and str(conditions[key]) == '1':
                        is_tenant_one = True
                        break

                for key, value in conditions.items():


                    if 'position_name' in key:
                        # 岗位名称条件总是要处理
                        if key.endswith('__like'):
                            field = key.replace('__like', '')
                            query += f" AND {field} LIKE %s"
                            params.append(value)
                        else:
                            query += f" AND {key} = %s"
                            params.append(value)
                    elif not is_tenant_one:
                        if key in ['tenant_id', 'p.tenant_id']:
                            # 租户ID条件已经在上面处理过了
                            query += " AND p.tenant_id = %s"
                            params.append(conditions.get("p.tenant_id"))
                            continue
                        # 非租户1的情况，处理所有条件
                        if key.endswith('__like'):
                            field = key.replace('__like', '')
                            query += f" AND {field} LIKE %s"
                            params.append(value)
                        else:
                            query += f" AND {key} = %s"
                            params.append(value)
                    # 租户1的情况下，其他条件被忽略

                cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                logger.error(f"MySQL 统计岗位数量失败: {e}")
                raise

    def query_departments_with_company(
            self,
            conditions: Dict[str, str],  # 接收字典格式查询条件
            offset: int = 0,
            limit: int = 10,
            lang: str = "zh",
    ) -> List[Dict]:
        """
        部门表关联公司表的分页查询（带公司名称）
        适配字典格式条件传入，支持多表字段筛选
        :param conditions: 查询条件字典（key为字段名，含表别名，value为匹配值）
                          示例：{'d.department_id': 1, 'd.department_name__like': '%技术%', 'c.company_name__like': '%科技%'}
        :param offset: 偏移量（分页起始位置）
        :param limit: 每页条数
        :return: 部门列表（含公司名称）
        """
        self._connect()
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                # 获取租户ID（可能以不同形式存在）
                tenant_id = None
                tenant_id_keys = ['tenant_id', 'd.tenant_id', 'c.tenant_id']
                for key in tenant_id_keys:
                    if key in conditions:
                        tenant_id = conditions[key]
                        break

                # 获取部门名称条件
                department_name = None
                department_name_key = None
                for key in conditions.keys():
                    if 'department_name' in key:
                        department_name = conditions[key]
                        department_name_key = key
                        break

                # 构建查询条件
                where_conditions = []
                params = []

                # 基础条件：排除通用部门
                # where_conditions.append("d.department_name != '通用部门'")

                # 如果租户ID为1，只使用租户ID和部门名称条件
                if tenant_id and str(tenant_id) == '1':

                    # 添加部门名称条件（如果存在）
                    if department_name and department_name_key:
                        if department_name_key.endswith('__like'):
                            actual_field = department_name_key.replace('__like', '')
                            where_conditions.append(f"{actual_field} LIKE %s")
                            params.append(department_name)
                        else:
                            where_conditions.append(f"{department_name_key} = %s")
                            params.append(department_name)
                else:
                    # 正常处理所有条件
                    for field, value in conditions.items():
                        # 处理模糊匹配（字段名以__like结尾）
                        if field.endswith('__like'):
                            actual_field = field[:-6]  # 去掉__like后缀
                            where_conditions.append(f"{actual_field} LIKE %s")
                            params.append(value)
                        else:
                            # 精确匹配字段
                            where_conditions.append(f"{field} = %s")
                            params.append(value)

                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

                # 关联查询SQL
                query = f"""
                    SELECT 
                        d.department_id, d.company_id, d.department_name, d.manager,
                        d.manager_phone, d.remark, d.create_time, d.update_time,
                        c.company_name, d.tenant_id
                    FROM {department_table} d
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE {where_clause}
                    LIMIT %s OFFSET %s
                """
                # 补充分页参数（offset和limit）
                params.extend([limit, offset])
                cursor.execute(query, params)
                result = cursor.fetchall()

                return result
            except Exception as e:
                logger.error(f"MySQL 部门关联查询失败: {e}")
                return []

    # ------------------------------
    # 4. 部门表关联计数（count_departments_with_company）
    # ------------------------------
    def count_departments_with_company(self, lang: str = "zh", **conditions) -> int:
        """统计部门数量（与分页查询条件一致）"""
        self._connect()
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 获取租户ID（可能以不同形式存在）
                tenant_id = None
                tenant_id_keys = ['tenant_id', 'd.tenant_id', 'c.tenant_id']
                for key in tenant_id_keys:
                    if key in conditions:
                        tenant_id = conditions[key]
                        break

                # 获取部门名称条件
                department_name = None
                department_name_key = None
                for key in conditions.keys():
                    if 'department_name' in key:
                        department_name = conditions[key]
                        department_name_key = key
                        break

                # 构建查询条件
                where_conditions = []
                params = []

                # 基础条件：排除通用部门
                # where_conditions.append("d.department_name != '通用部门'")

                # 如果租户ID为1，只使用租户ID和部门名称条件
                if tenant_id and str(tenant_id) == '1':

                    # 添加部门名称条件（如果存在）
                    if department_name and department_name_key:
                        if department_name_key.endswith('__like'):
                            actual_field = department_name_key.replace('__like', '')
                            where_conditions.append(f"{actual_field} LIKE %s")
                            params.append(department_name)
                        else:
                            where_conditions.append(f"{department_name_key} = %s")
                            params.append(department_name)
                else:
                    # 正常处理所有条件
                    for field, value in conditions.items():
                        # 处理模糊匹配（字段名以__like结尾）
                        if field.endswith('__like'):
                            actual_field = field[:-6]  # 去掉__like后缀
                            where_conditions.append(f"{actual_field} LIKE %s")
                            params.append(value)
                        else:
                            # 精确匹配字段
                            where_conditions.append(f"{field} = %s")
                            params.append(value)

                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM {department_table} d
                    LEFT JOIN {company_table} c ON d.company_id = c.company_id
                    WHERE {where_clause}
                """
                cursor.execute(count_query, params)
                result = cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                logger.error(f"MySQL 统计部门数量失败: {e}")
                raise

    def query_tenant_by_id(self, tenant_id: int, lang: str = "zh") -> Optional[Dict]:
        """查询租户信息"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT 
                        tenant_id,
                        tenant_name,
                        status
                    FROM {tenant_table}
                    WHERE tenant_id = %s
                    LIMIT 1
                """
                cursor.execute(query, (tenant_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询租户信息失败: {e}")
                raise

    # ------------------------------
    # 公司表分页查询（db_client.query_companies_paginated）
    # ------------------------------
    def query_companies_paginated(
            self,
            conditions: Dict,
            offset: int,
            limit: int,
            lang: str = "zh",
    ) -> List[Dict]:
        """公司表多条件分页查询（tenant_id=None 时查全局，否则过滤指定租户）"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = []
                params = []

                for key, value in conditions.items():
                    if value is None:
                        continue
                    if key == 'tenant_id':
                        where_clauses.append("tenant_id = %s")
                        params.append(value)
                    elif key.endswith('__like'):
                        field = key.replace('__like', '')
                        if field in ['company_name', 'address', 'contact_phone']:
                            where_clauses.append(f"{field} LIKE %s")
                            params.append(value)
                    elif key == 'company_id':
                        where_clauses.append("company_id = %s")
                        params.append(value)

                # tenant_id 不在 conditions 中（OWNER）→ 不加租户过滤，查全局
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                query = f"""
                    SELECT * FROM {company_table}
                    WHERE {where_sql}
                    ORDER BY company_id ASC
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])

                cursor.execute(query, params)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 公司分页查询失败: {e}")
                raise

    def count_companies_by_conditions(self, lang: str = "zh", **conditions) -> int:
        """公司表多条件计数（tenant_id=None 时统计全局，否则过滤指定租户）"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = []
                params = []

                for key, value in conditions.items():
                    if value is None:
                        continue
                    if key == 'tenant_id':
                        where_clauses.append("tenant_id = %s")
                        params.append(value)
                    elif key.endswith('__like'):
                        field = key.replace('__like', '')
                        if field in ['company_name', 'address', 'contact_phone']:
                            where_clauses.append(f"{field} LIKE %s")
                            params.append(value)
                    elif key == 'company_id':
                        where_clauses.append("company_id = %s")
                        params.append(value)

                # tenant_id 不在 conditions 中（OWNER）→ 不加租户过滤，统计全局
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                count_query = f"""
                    SELECT COUNT(*) AS total FROM {company_table}
                    WHERE {where_sql}
                """
                cursor.execute(count_query, params)
                result = cursor.fetchone()
                return result['total'] if result and result['total'] else 0
            except Exception as e:
                logger.error(f"MySQL 公司条件计数失败: {e}")
                raise

    def query_companies_by_multiple_conditions(self, lang: str = "zh", **conditions) -> List[Dict]:
        """多条件并联查询公司记录（tenant_id=None 时查全局，否则过滤指定租户）"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = []
                params = []

                tenant_id = conditions.get('tenant_id')
                if tenant_id is not None:
                    where_clauses.append("tenant_id = %s")
                    params.append(tenant_id)
                # tenant_id is None（OWNER）→ 不加租户过滤，查全局

                if 'company_id' in conditions and conditions['company_id'] is not None:
                    where_clauses.append("company_id = %s")
                    params.append(conditions['company_id'])

                if 'company_name__like' in conditions and conditions['company_name__like'] is not None:
                    where_clauses.append("company_name LIKE %s")
                    params.append(conditions['company_name__like'])
                elif 'company_name' in conditions and conditions['company_name'] is not None:
                    where_clauses.append("company_name = %s")
                    params.append(conditions['company_name'])

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                query = f"""
                    SELECT * FROM {company_table}
                    WHERE {where_sql}
                    ORDER BY company_id ASC
                """

                cursor.execute(query, params)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 多条件查询公司失败: {e}")
                raise

    def query_sops_list_paginated(self, keyword: str, page: int = 1, page_size: int = 10):
        """
        分页查询 sops 列表
        :param keyword: 搜索关键词
        :param page: 当前页码，从 1 开始
        :param page_size: 每页记录数
        :return: 查询结果列表和总记录数
        """
        self._connect()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                # 计算偏移量
                offset = (page - 1) * page_size

                # 先查询总记录数
                if keyword and keyword.strip():
                    count_query = "SELECT COUNT(*) as total FROM sop_info WHERE title LIKE %s OR filename LIKE %s"
                    search_pattern = f"%{keyword}%"
                    cursor.execute(count_query, (search_pattern, search_pattern))
                else:
                    count_query = "SELECT COUNT(*) as total FROM sop_info"
                    cursor.execute(count_query)

                total = cursor.fetchone()['total']

                # 查询分页数据
                if keyword and keyword.strip():
                    query = "SELECT * FROM sop_info WHERE title LIKE %s OR filename LIKE %s LIMIT %s OFFSET %s"
                    search_pattern = f"%{keyword}%"
                    cursor.execute(query, (search_pattern, search_pattern, page_size, offset))
                else:
                    query = "SELECT * FROM sop_info LIMIT %s OFFSET %s"
                    cursor.execute(query, (page_size, offset))

                result = cursor.fetchall()
                return {"data": result, "total": total}
            except Exception as e:
                logger.error(f"MySQL 分页查询失败: {e}")
                return {"data": [], "total": 0}

    def query_sop_version_by_id_and_tenant(
            self,
            version_id: int,
            lang: str = "zh",
    ) -> Optional[Dict]:
        """根据版本ID和租户ID查询SOP版本信息"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        sop_info_table = self._get_sop_info_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"""
                    SELECT sv.*, si.title as sop_title, si.position_id
                    FROM {sop_version_table} sv
                    LEFT JOIN {sop_info_table} si ON sv.sop_info_id = si.id
                    WHERE sv.id = %s
                """
                cursor.execute(query, (version_id,))
                result = cursor.fetchone()
                return result
            except Exception as e:
                logger.error(f"MySQL 查询SOP版本失败: {e}")
                raise

    def update_sop_version(
            self,
            version_id: int,
            file_name: str = None,
            version_number: str = None,
            version_name: str = None,
            content: str = None,
            lang: str = "zh",
    ) -> None:
        """更新SOP版本信息（包含租户验证）"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 构建更新字段
                update_fields = []
                params = []

                if file_name is not None:
                    update_fields.append("file_name = %s")
                    params.append(file_name)
                if version_number is not None:
                    update_fields.append("version_number = %s")
                    params.append(version_number)
                if version_name is not None:
                    update_fields.append("version_name = %s")
                    params.append(version_name)
                if content is not None:
                    update_fields.append("content = %s")
                    params.append(content)

                if not update_fields:
                    return  # 没有要更新的字段

                update_fields.append("updated_at = CURRENT_TIMESTAMP")

                # 添加WHERE条件（包含租户验证）
                query = f"""
                    UPDATE {sop_version_table}
                    SET {', '.join(update_fields)} 
                    WHERE id = %s
                """
                params.extend([version_id])

                cursor.execute(query, tuple(params))
                self.connection.commit()

                if cursor.rowcount == 0:
                    raise ValueError(f"版本ID【{version_id}】不存在")

                logger.info(f"更新SOP版本ID【{version_id}】成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新SOP版本失败: {e}")
                raise

    # ------------------------------
    # SOP版本表 - 插入
    # ------------------------------
    def insert_sop_version(
            self,
            file_name: str,
            version_number: str,
            content: str,
            version_name: str = None,
            sop_info_id: int = None,
            lang: str = "zh",
    ) -> int:
        """新增SOP版本记录（包含租户信息）"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        with self.connection.cursor() as cursor:
            try:

                # 插入版本记录
                query = f"""
                    INSERT INTO {sop_version_table} (
                         file_name, version_number, 
                        version_name, content, sop_info_id
                    ) VALUES ( %s, %s, %s, %s, %s)
                """

                cursor.execute(query, (
                     file_name, version_number,
                    version_name, content, sop_info_id
                ))

                version_id = cursor.lastrowid
                self.connection.commit()
                logger.info(f"租户新增SOP版本【{file_name} - {version_number}】成功，版本ID: {version_id}")

                return version_id
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增SOP版本失败: {e}")
                raise

    # ------------------------------
    # SOP版本表 - 删除
    # ------------------------------
    def delete_sop_version(
            self,
            version_id: int,
            lang: str = "zh",
    ) -> None:
        """删除SOP版本（包含租户验证）"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 物理删除
                query = f"DELETE FROM {sop_version_table} WHERE id = %s "
                cursor.execute(query, (version_id,))

                self.connection.commit()

                if cursor.rowcount == 0:
                    raise ValueError(f"版本ID【{version_id}】不存在")

                logger.info(f"删除SOP版本ID【{version_id}】成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除SOP版本失败: {e}")
                raise

    # ------------------------------
    # SOP版本表 - 查询（按ID）
    # ------------------------------
    def query_sop_version_by_id(self, version_id: int, lang: str = "zh") -> Optional[Dict]:
        """按ID查询SOP版本详情

        Args:
            version_id: 版本ID

        Returns:
            版本记录字典，或None
        """
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT * FROM {sop_version_table}
                    WHERE id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (version_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按ID查询SOP版本失败: {e}")
                raise

    # ------------------------------
    # SOP版本表 - 查询（按文件名）
    # ------------------------------
    def query_sop_versions_by_file_name(self, file_name: str, lang: str = "zh") -> List[Dict]:
        """查询指定文件名的所有版本

        Args:
            file_name: 文件名

        Returns:
            版本记录列表
        """
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT * FROM {sop_version_table}
                    WHERE file_name = %s 
                    ORDER BY version_number ASC
                """
                cursor.execute(query, (file_name,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 按文件名查询SOP版本失败: {e}")
                raise

    def query_sop_versions_by_file_and_tenant(
            self,
            file_name: str,
            exclude_version_id: int = None,
            lang: str = "zh",
    ) -> List[Dict]:
        """查询同一租户内指定文件名的所有版本（排除指定版本）"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"SELECT * FROM {sop_version_table} WHERE file_name = %s"
                params = [file_name]

                if exclude_version_id is not None:
                    query += " AND id != %s"
                    params.append(exclude_version_id)

                cursor.execute(query, tuple(params))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询文件版本失败: {e}")
                raise

    # ------------------------------
    # SOP版本表 - 查询（多条件）
    # ------------------------------
    def query_sop_versions_by_multiple_conditions(
            self,
            version_id: int = None,
            file_name: str = None,
            version_number: str = None,
            sop_info_id: int = None,
            lang: str = "zh",
    ) -> List[Dict]:
        """根据多个条件查询SOP版本列表（包含租户筛选）"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        sop_info_table = self._get_sop_info_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                # 基础查询（必须包含租户条件）
                query = f"""
                    SELECT sv.*, si.title as sop_title
                    FROM {sop_version_table} sv
                    LEFT JOIN {sop_info_table} si ON sv.sop_info_id = si.id 
                    WHERE 1=1
                """
                params = []

                # 动态添加条件
                conditions = []
                if version_id is not None:
                    conditions.append("sv.id = %s")
                    params.append(version_id)
                if file_name is not None:
                    conditions.append("sv.file_name = %s")
                    params.append(file_name)
                if version_number is not None:
                    conditions.append("sv.version_number = %s")
                    params.append(version_number)
                if sop_info_id is not None:
                    conditions.append("sv.sop_info_id = %s")
                    params.append(sop_info_id)

                if conditions:
                    query += " AND " + " AND ".join(conditions)

                query += " ORDER BY sv.created_at DESC"

                cursor.execute(query, tuple(params))
                results = cursor.fetchall()
                return results
            except Exception as e:
                logger.error(f"MySQL 查询SOP版本列表失败: {e}")
                raise

    def query_sop_info_by_id(self, sop_info_id: int) -> Optional[Dict]:
        """按ID查询SOP信息详情

        Args:
            sop_info_id: SOP信息ID

        Returns:
            SOP信息记录字典，或None
        """
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = """
                    SELECT 
                    *
                    FROM sop_info 
                    WHERE id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (sop_info_id,))
                result = cursor.fetchone()

                if result:
                    logger.info(f"查询到SOP信息ID【{sop_info_id}】的记录")
                else:
                    logger.warning(f"未找到SOP信息ID【{sop_info_id}】的记录")

                return result
            except Exception as e:
                logger.error(f"MySQL 按ID查询SOP信息失败: {e}")
                raise

    def query_sop_versions_paginated(
            self,
            conditions: Dict,
            offset: int = 0,
            limit: int = 10,
            lang: str = "zh",
    ) -> List[Dict]:
        """SOP版本分页查询（支持多种条件）"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        sop_info_table = self._get_sop_info_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                # 基础查询
                query = f"""
                    SELECT sv.*, si.title as sop_title
                    FROM {sop_version_table} sv
                    LEFT JOIN {sop_info_table} si ON sv.sop_info_id = si.id AND si.tenant_id = sv.tenant_id
                    WHERE 1=1
                """
                params = []

                # 动态添加条件
                for key, value in conditions.items():
                    if key.endswith('__like'):
                        field = key.replace('__like', '')
                        query += f" AND sv.{field} LIKE %s"
                        params.append(value)
                    elif key == 'tenant_id':
                        query += " AND sv.tenant_id = %s"
                        params.append(value)
                    else:
                        query += f" AND sv.{key} = %s"
                        params.append(value)

                query += " ORDER BY sv.created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cursor.execute(query, tuple(params))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 分页查询SOP版本失败: {e}")
                raise

    def count_sop_versions(self, lang: str = "zh", **conditions) -> int:
        """统计SOP版本数量"""
        self._connect()
        sop_version_table = self._get_sop_version_table(lang)
        with self.connection.cursor() as cursor:
            try:
                query = f"SELECT COUNT(*) as total FROM {sop_version_table} WHERE 1=1"
                params = []

                # 动态添加条件
                for key, value in conditions.items():
                    if key.endswith('__like'):
                        field = key.replace('__like', '')
                        query += f" AND {field} LIKE %s"
                        params.append(value)
                    else:
                        query += f" AND {key} = %s"
                        params.append(value)

                cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                logger.error(f"MySQL 统计SOP版本数量失败: {e}")
                raise

    def query_sop_info_by_id_and_tenant(
            self,
            sop_info_id: int,
            lang: str = "zh",
    ) -> Optional[Dict]:
        """根据SOP信息ID和租户ID查询SOP信息"""
        self._connect()
        sop_info_table = self._get_sop_info_table(lang)
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                query = f"""
                    SELECT * FROM {sop_info_table}
                    WHERE id = %s
                """
                cursor.execute(query, (sop_info_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询SOP信息失败: {e}")
                return None

    def update_sop_info_version_by_id(
            self,
            sop_info_id: int,
            sop_version: str,
            lang: str = "zh",
    ) -> None:
        """更新SOP信息表中的版本号（包含租户验证）"""
        self._connect()
        sop_info_table = self._get_sop_info_table(lang)
        with self.connection.cursor() as cursor:
            try:
                query = f"""
                    UPDATE {sop_info_table}
                    SET sop_version = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """
                cursor.execute(query, (sop_version, sop_info_id))
                self.connection.commit()

                if cursor.rowcount == 0:
                    raise ValueError(f"SOP信息ID【{sop_info_id}】不存在")

                logger.info(f"更新SOP信息版本号【{sop_version}】成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新SOP信息版本号失败: {e}")
                raise

    def update_title_by_id(self, record_id: int, title: str):
        """
        根据记录 ID 更新 title 字段
        :param record_id: 记录 ID
        :param title: 新的标题
        """
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = "UPDATE sop_info SET title = %s WHERE id = %s"
                affected_rows = cursor.execute(query, (title, record_id))
                if affected_rows == 0:
                    logger.warning(f"未找到 ID 为 {record_id} 的记录")
                    return False
                logger.info(f"成功更新 ID 为 {record_id} 的记录标题")
                return True
            except Exception as e:
                logger.error(f"MySQL 更新标题失败: {e}")
                return False

    # 在 MySQLClient 类中添加以下方法

    # ------------------------------
    # 租户表 - 插入
    # ------------------------------
    def insert_tenant(
            self,
            tenant_code: str,
            tenant_name: str,
            status: int = 1,
            expire_time: Optional[str] = None,
            max_user_count: Optional[int] = None,
            remark: Optional[str] = None,
            lang: str = "zh",
    ) -> int:
        """新增租户记录"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor() as cursor:
            try:
                query = f"""
                    INSERT INTO {tenant_table} (
                        tenant_code, tenant_name, status, 
                        expire_time, max_user_count, remark
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """

                cursor.execute(query, (
                    tenant_code, tenant_name, status,
                    expire_time, max_user_count, remark
                ))

                tenant_id = cursor.lastrowid
                self.connection.commit()
                logger.info(f"新增租户【{tenant_name}】成功，租户ID: {tenant_id}")

                return tenant_id
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增租户失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 删除
    # ------------------------------
    def delete_tenant(self, tenant_id: int, lang: str = "zh") -> None:
        """删除租户记录"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 先检查租户是否存在
                cursor.execute(
                    f"SELECT tenant_id FROM {tenant_table} WHERE tenant_id = %s LIMIT 1",
                    (tenant_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"租户ID不存在: {tenant_id}")

                # 执行删除
                delete_query = f"DELETE FROM {tenant_table} WHERE tenant_id = %s"
                cursor.execute(delete_query, (tenant_id,))
                self.connection.commit()

                logger.info(f"租户ID【{tenant_id}】删除成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除租户失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 更新
    # ------------------------------
    def update_tenant(
            self,
            tenant_id: int,
            tenant_code: Optional[str] = None,
            tenant_name: Optional[str] = None,
            status: Optional[int] = None,
            expire_time: Optional[str] = None,
            max_user_count: Optional[int] = None,
            remark: Optional[str] = None,
            lang: str = "zh",
    ) -> None:
        """更新租户信息"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor() as cursor:
            try:
                # 检查租户是否存在
                cursor.execute(
                    f"SELECT tenant_id FROM {tenant_table} WHERE tenant_id = %s LIMIT 1",
                    (tenant_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"租户ID不存在: {tenant_id}")

                # 如果要修改租户编码，检查是否重复
                if tenant_code:
                    cursor.execute(
                        f"SELECT tenant_id FROM {tenant_table} WHERE tenant_code = %s AND tenant_id != %s LIMIT 1",
                        (tenant_code, tenant_id)
                    )
                    if cursor.fetchone():
                        raise ValueError(f"租户编码【{tenant_code}】已存在")

                # 动态构建更新字段
                update_fields = []
                params = []

                if tenant_code is not None:
                    update_fields.append("tenant_code = %s")
                    params.append(tenant_code)
                if tenant_name is not None:
                    update_fields.append("tenant_name = %s")
                    params.append(tenant_name)
                if status is not None:
                    update_fields.append("status = %s")
                    params.append(status)
                if expire_time is not None:
                    update_fields.append("expire_time = %s")
                    params.append(expire_time)
                if max_user_count is not None:
                    update_fields.append("max_user_count = %s")
                    params.append(max_user_count)
                if remark is not None:
                    update_fields.append("remark = %s")
                    params.append(remark)

                if not update_fields:
                    return  # 没有要更新的字段

                # 拼接更新SQL
                query = f"""
                    UPDATE {tenant_table}
                    SET {', '.join(update_fields)}, update_time = CURRENT_TIMESTAMP 
                    WHERE tenant_id = %s
                """
                params.append(tenant_id)

                cursor.execute(query, tuple(params))
                self.connection.commit()
                logger.info(f"租户ID【{tenant_id}】更新成功")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新租户失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 查询（按ID）
    # ------------------------------
    def query_tenant_by_id(self, tenant_id: int, lang: str = "zh") -> Optional[Dict]:
        """按ID查询租户信息"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT 
                        tenant_id, tenant_code, tenant_name, 
                        status, expire_time, max_user_count, 
                        remark, create_time, update_time
                    FROM {tenant_table}
                    WHERE tenant_id = %s 
                    LIMIT 1
                """
                cursor.execute(query, (tenant_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按ID查询租户失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 查询（按编码）
    # ------------------------------
    def query_tenant_by_code(self, tenant_code: str, lang: str = "zh") -> Optional[Dict]:
        """按编码查询租户信息"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT 
                        tenant_id, tenant_code, tenant_name, 
                        status, expire_time, max_user_count, 
                        remark, create_time, update_time
                    FROM {tenant_table}
                    WHERE tenant_code = %s 
                    LIMIT 1
                """
                cursor.execute(query, (tenant_code,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按编码查询租户失败: {e}")
                raise

    def count_users_by_position(self, position_id: int, tenant_id: int) -> int:
        """统计指定租户下绑定指定岗位的用户数量"""
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = """
                    SELECT COUNT(*) as user_count
                    FROM sp_user
                    WHERE position_id = %s 
                    AND tenant_id = %s
                    AND is_active = 1
                    AND deleted_at IS NULL
                """
                cursor.execute(query, (position_id, tenant_id))
                result = cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                logger.error(f"MySQL 统计用户数量失败: {e}")
                return 0

    def count_courses_by_position(self, position_id: int, tenant_id: int, lang: str = "zh") -> int:
        """统计指定租户下绑定指定岗位的课程数量"""
        self._connect()
        course_table = self._get_course_table(lang)
        with self.connection.cursor() as cursor:
            try:
                query = f"""
                    SELECT COUNT(*) as course_count
                    FROM {course_table}
                    WHERE position_id = %s 
                    AND tenant_id = %s
                    AND is_deleted = 0
                """
                cursor.execute(query, (position_id, tenant_id))
                result = cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                logger.error(f"MySQL 统计课程数量失败: {e}")
                return 0

    def count_materials_by_position(self, position_id: int, tenant_id: int, lang: str = "zh") -> int:
        """统计指定租户下绑定指定岗位的资料数量"""
        self._connect()
        material_table = self._get_material_table(lang)
        with self.connection.cursor() as cursor:
            try:
                query = f"""
                    SELECT COUNT(*) as material_count
                    FROM {material_table}
                    WHERE position_id = %s 
                    AND tenant_id = %s
                    AND is_deleted = 0
                """
                cursor.execute(query, (position_id, tenant_id))
                result = cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                logger.error(f"MySQL 统计资料数量失败: {e}")
                return 0

    # ------------------------------
    # 租户表 - 查询（按名称模糊）
    # ------------------------------
    def query_tenant_by_name_like(self, tenant_name: str, lang: str = "zh") -> List[Dict]:
        """按名称模糊查询租户"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT 
                        tenant_id, tenant_code, tenant_name, 
                        status, expire_time, max_user_count, 
                        create_time, update_time
                    FROM {tenant_table}
                    WHERE tenant_name LIKE %s 
                    ORDER BY tenant_id ASC
                """
                search_pattern = f"%{tenant_name}%"
                cursor.execute(query, (search_pattern,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 模糊查询租户失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 查询（所有）
    # ------------------------------
    def query_all_tenants(self, lang: str = "zh") -> List[Dict]:
        """查询所有租户"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT 
                        tenant_id, tenant_code, tenant_name, 
                        status, expire_time, max_user_count, 
                        create_time, update_time
                    FROM {tenant_table}
                    ORDER BY tenant_id ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 查询所有租户失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 多条件查询
    # ------------------------------
    def query_tenants_by_multiple_conditions(self, lang: str = "zh", **conditions) -> List[Dict]:
        """多条件查询租户记录"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = []
                params = []

                # 构建查询条件
                if 'tenant_id' in conditions and conditions['tenant_id'] is not None:
                    where_clauses.append("tenant_id = %s")
                    params.append(conditions['tenant_id'])

                if 'tenant_code' in conditions and conditions['tenant_code'] is not None:
                    where_clauses.append("tenant_code = %s")
                    params.append(conditions['tenant_code'])

                if 'tenant_name' in conditions and conditions['tenant_name'] is not None:
                    if 'tenant_name__like' in conditions:
                        # 优先使用模糊匹配
                        where_clauses.append("tenant_name LIKE %s")
                        params.append(conditions['tenant_name__like'])
                    else:
                        where_clauses.append("tenant_name LIKE %s")
                        params.append(f"%{conditions['tenant_name']}%")

                if 'status' in conditions and conditions['status'] is not None:
                    where_clauses.append("status = %s")
                    params.append(conditions['status'])

                # 构建完整的SQL语句
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                query = f"""
                    SELECT 
                        tenant_id, tenant_code, tenant_name, 
                        status, expire_time, max_user_count, 
                        remark, create_time, update_time
                    FROM {tenant_table}
                    WHERE {where_sql}
                    ORDER BY tenant_id ASC
                """

                cursor.execute(query, params)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 多条件查询租户失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 分页查询
    # ------------------------------
    def query_tenants_paginated(
            self,
            conditions: Dict,
            offset: int,
            limit: int,
            lang: str = "zh",
    ) -> List[Dict]:
        """租户分页查询"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = []
                params = []

                # 构建查询条件
                for key, value in conditions.items():
                    if value is None:
                        continue

                    if key == 'tenant_id':
                        where_clauses.append("tenant_id = %s")
                        params.append(value)
                    elif key.endswith('__like'):
                        field = key.replace('__like', '')
                        if field in ['tenant_code', 'tenant_name']:
                            where_clauses.append(f"{field} LIKE %s")
                            params.append(value)
                    elif key == 'tenant_code':
                        where_clauses.append("tenant_code = %s")
                        params.append(value)
                    elif key == 'tenant_name':
                        where_clauses.append("tenant_name LIKE %s")
                        params.append(f"%{value}%")
                    elif key == 'status':
                        where_clauses.append("status = %s")
                        params.append(value)

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                query = f"""
                    SELECT 
                        tenant_id, tenant_code, tenant_name, 
                        status, expire_time, max_user_count, 
                        create_time, update_time
                    FROM {tenant_table}
                    WHERE {where_sql}
                    ORDER BY tenant_id ASC
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])

                cursor.execute(query, params)
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 租户分页查询失败: {e}")
                raise

    # ------------------------------
    # 租户表 - 条件计数
    # ------------------------------
    def count_tenants_by_conditions(self, lang: str = "zh", **conditions) -> int:
        """统计符合条件的租户数量"""
        self._connect()
        tenant_table = self._get_tenant_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = []
                params = []

                # 条件构建逻辑与分页查询一致
                for key, value in conditions.items():
                    if value is None:
                        continue

                    if key == 'tenant_id':
                        where_clauses.append("tenant_id = %s")
                        params.append(value)
                    elif key.endswith('__like'):
                        field = key.replace('__like', '')
                        if field in ['tenant_code', 'tenant_name']:
                            where_clauses.append(f"{field} LIKE %s")
                            params.append(value)
                    elif key == 'tenant_code':
                        where_clauses.append("tenant_code = %s")
                        params.append(value)
                    elif key == 'tenant_name':
                        where_clauses.append("tenant_name LIKE %s")
                        params.append(f"%{value}%")
                    elif key == 'status':
                        where_clauses.append("status = %s")
                        params.append(value)

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                count_query = f"""
                    SELECT COUNT(*) AS total FROM {tenant_table}
                    WHERE {where_sql}
                """
                cursor.execute(count_query, params)
                result = cursor.fetchone()
                return result['total'] if result and result['total'] else 0
            except Exception as e:
                logger.error(f"MySQL 租户条件计数失败: {e}")
                raise

    # ------------------------------
    # 公司表 - 按租户查询（用于租户删除前的业务检查）
    # ------------------------------
    def query_companies_by_tenant(self, tenant_id: int, lang: str = "zh") -> List[Dict]:
        """查询指定租户下的所有公司"""
        self._connect()
        company_table = self._get_company_table(lang)
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT company_id, company_name 
                    FROM {company_table}
                    WHERE tenant_id = %s 
                    LIMIT 5  -- 只查询前5条用于判断是否存在关联
                """
                cursor.execute(query, (tenant_id,))
                return cursor.fetchall()
            except Exception as e:
                logger.error(f"MySQL 按租户查询公司失败: {e}")
                raise

    # ------------------------------
    # 客户端版本表 - 查询当前生效版本
    # ------------------------------
    def query_latest_active_app_version(self) -> Optional[Dict]:
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = """
                    SELECT *
                    FROM sp_app_version
                    WHERE status = 1 AND edition_issue = 1
                    ORDER BY edition_version_code DESC, id DESC
                    LIMIT 1
                """
                cursor.execute(query)
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询当前生效客户端版本失败: {e}")
                raise

    # ------------------------------
    # 客户端版本表 - 查询最新发布版本（不区分是否发行）
    # ------------------------------
    def query_latest_published_app_version(self) -> Optional[Dict]:
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = """
                    SELECT *
                    FROM sp_app_version
                    WHERE status = 1
                    ORDER BY edition_version_code DESC, id DESC
                    LIMIT 1
                """
                cursor.execute(query)
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询最新发布客户端版本失败: {e}")
                raise

    # ------------------------------
    # 客户端版本表 - 按版本号查询
    # ------------------------------
    def query_app_version_by_version_code(self, edition_version_code: int) -> Optional[Dict]:
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = """
                    SELECT *
                    FROM sp_app_version
                    WHERE edition_version_code = %s
                    LIMIT 1
                """
                cursor.execute(query, (edition_version_code,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按版本号查询客户端版本失败: {e}")
                raise

    # ------------------------------
    # 客户端版本表 - 按ID查询
    # ------------------------------
    def query_app_version_by_id(self, version_id: int) -> Optional[Dict]:
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = """
                    SELECT *
                    FROM sp_app_version
                    WHERE id = %s
                    LIMIT 1
                """
                cursor.execute(query, (version_id,))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 按ID查询客户端版本失败: {e}")
                raise

    # ------------------------------
    # 客户端版本表 - 新增发布版本
    # ------------------------------
    def insert_app_version(
            self,
            edition_name: str,
            edition_version_code: int,
            describe_zh: str,
            describe_en: str,
            describe_th: str,
            edition_url: str,
            edition_force: int,
            package_type: int,
            edition_issue: int,
            edition_silence: int,
            published_by: Optional[str] = None,
    ) -> int:
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = """
                    INSERT INTO sp_app_version (
                        edition_name,
                        edition_version_code,
                        describe_zh,
                        describe_en,
                        describe_th,
                        edition_url,
                        edition_force,
                        package_type,
                        edition_issue,
                        edition_silence,
                        status,
                        published_at,
                        published_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), %s)
                """
                cursor.execute(
                    query,
                    (
                        edition_name,
                        edition_version_code,
                        describe_zh,
                        describe_en,
                        describe_th,
                        edition_url,
                        edition_force,
                        package_type,
                        edition_issue,
                        edition_silence,
                        published_by,
                    ),
                )
                version_id = cursor.lastrowid
                self.connection.commit()
                return version_id
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增客户端版本失败: {e}")
                raise

    # ------------------------------
    # 客户端版本表 - 撤销发布版本
    # ------------------------------
    def revoke_app_version(
            self,
            version_id: int,
            revoked_by: Optional[str] = None,
            revoke_reason: Optional[str] = None,
    ) -> None:
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = """
                    UPDATE sp_app_version
                    SET status = 2,
                        revoked_at = NOW(),
                        revoked_by = %s,
                        revoke_reason = %s,
                        updated_at = NOW()
                    WHERE id = %s AND status = 1
                """
                cursor.execute(query, (revoked_by, revoke_reason, version_id))
                self.connection.commit()
                if cursor.rowcount == 0:
                    raise ValueError(f"版本ID【{version_id}】不存在或不可撤销")
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 撤销客户端版本失败: {e}")
                raise

    # ------------------------------
    # 客户端版本表 - 分页查询
    # ------------------------------
    def query_app_versions_paginated(
            self,
            page: int = 1,
            page_size: int = 10,
            status: Optional[int] = None,
            edition_name: Optional[str] = None,
            edition_version_code: Optional[int] = None,
    ) -> Dict:
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                offset = (page - 1) * page_size
                where_clauses = []
                params = []

                if status is not None:
                    where_clauses.append("status = %s")
                    params.append(status)
                if edition_name:
                    where_clauses.append("edition_name LIKE %s")
                    params.append(f"%{edition_name}%")
                if edition_version_code is not None:
                    where_clauses.append("edition_version_code = %s")
                    params.append(edition_version_code)

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                count_sql = f"SELECT COUNT(*) AS total FROM sp_app_version WHERE {where_sql}"
                cursor.execute(count_sql, tuple(params))
                total_row = cursor.fetchone() or {}
                total = int(total_row.get("total", 0))

                query = f"""
                    SELECT *
                    FROM sp_app_version
                    WHERE {where_sql}
                    ORDER BY edition_version_code DESC, id DESC
                    LIMIT %s OFFSET %s
                """
                query_params = list(params) + [page_size, offset]
                cursor.execute(query, tuple(query_params))
                rows = cursor.fetchall()

                return {"data": rows, "total": total}
            except Exception as e:
                logger.error(f"MySQL 分页查询客户端版本失败: {e}")
                raise
