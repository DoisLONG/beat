# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import string
from datetime import datetime
import random

import pymysql
from threading import Lock

from pymysql.cursors import DictCursor

from comps import CustomLogger
import os
from typing import Optional, Dict, List
import json

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

    # ------------------------------
    # 多语种业务表路由
    # 规则：JWT.lang 是唯一来源；zh 复用原表，en/th 走后缀表；非法值降级为 zh
    # 与 system-common / account 已落地口径完全一致
    # ------------------------------
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

    # learn 自身内容主数据
    def _get_course_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_course", lang)

    def _get_video_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_video", lang)

    def _get_material_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_material", lang)

    # learn 学习行为数据
    def _get_learning_record_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_learning_record", lang)

    def _get_course_progress_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_course_progress", lang)

    def _get_user_learning_summary_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_user_learning_summary", lang)

    # learn 读侧依赖的组织表（与 system-common 同口径）
    def _get_tenant_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_tenant", lang)

    def _get_company_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_company", lang)

    def _get_department_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_department", lang)

    def _get_position_table(self, lang: Optional[str] = "zh") -> str:
        return self._table_name("sp_position", lang)

    # 通用岗位三语种名称映射（与 system-common 已落地常量一致）
    _GENERAL_POSITION_NAME = {
        "zh": "通用岗位",
        "en": "General Position",
        "th": "ตำแหน่งทั่วไป",
    }

    def _get_general_position_name(self, lang: Optional[str] = "zh") -> str:
        return self._GENERAL_POSITION_NAME[self._resolve_lang(lang)]

    # 课程/素材分类 多语种静态映射
    # key = 存入数据库的 code（语言无关），value = 各语种展示标签
    # 未来迁移到字典表时：code 保持不变，只需删除此常量 + 改为 DB 查询
    _CATEGORY_MAP: Dict[str, Dict[str, str]] = {
        "safety_training":  {"zh": "安全培训", "en": "Safety Training",    "th": "การฝึกอบรมด้านความปลอดภัย"},
        "skill_upgrade":    {"zh": "技能提升", "en": "Skill Improvement", "th": "การพัฒนาทักษะ"},
        "onboarding":       {"zh": "入职培训", "en": "Onboarding Training","th": "การฝึกอบรมพนักงานใหม่"},
        "product_training": {"zh": "产品培训", "en": "Product Training",   "th": "การฝึกอบรมผลิตภัณฑ์"},
    }

    # 反向映射：任意语种 label → code，用于写入时规范化
    _CATEGORY_REVERSE_MAP: Dict[str, str] = {
        label: code
        for code, labels in _CATEGORY_MAP.items()
        for label in labels.values()
    }
    # backward compatibility: historical english label
    _CATEGORY_REVERSE_MAP["Skill Development"] = "skill_upgrade"

    @classmethod
    def _normalize_category(cls, category: Optional[str]) -> Optional[str]:
        """将任意语种 label 或已有 code 统一转为 code 存入 DB；未识别的值原样保留。"""
        if not category:
            return category
        if category in cls._CATEGORY_MAP:          # 已经是 code
            return category
        return cls._CATEGORY_REVERSE_MAP.get(category, category)

    @classmethod
    def _translate_category(cls, code: Optional[str], lang: Optional[str] = "zh") -> Optional[str]:
        """将 DB 中的 code 翻译为指定语种的展示 label；未识别的 code 原样返回。"""
        if not code:
            return code
        labels = cls._CATEGORY_MAP.get(code)
        if not labels:
            return code
        safe_lang = lang if lang in ("zh", "en", "th") else "zh"
        return labels.get(safe_lang, labels["zh"])

    def get_category_options(self, lang: Optional[str] = "zh") -> List[str]:
        """返回所有课程/素材分类标签列表（按 lang 翻译）。
        未来迁字典表时只需替换此方法体，调用方不用改。
        """
        safe_lang = lang if lang in ("zh", "en", "th") else "zh"
        return [labels.get(safe_lang, labels["zh"]) for labels in self._CATEGORY_MAP.values()]

    # 在 MySQLClient 类中添加以下方法（接在现有代码后面）

    # ------------------------------
    # 课程模块（course）相关方法 - 程念负责
    # ------------------------------
    def insert_course_with_videos(
            self,
            course_id: str,
            title: str,
            code: str = None,
            category: str = None,
            cover_url: str = None,
            description: str = None,
            tags: str = None,
            status: str = "draft",
            videos: List[Dict] = None,
            keywordslist: str = None,
            position_id: int = None,
            tenant_id: int = None,  # 新增：租户ID
            lang: Optional[str] = "zh"  # 多语种：按 JWT.lang 路由业务表
    ) -> Dict:
        """新增课程记录（包含租户和岗位信息）"""
        tenant_table = self._get_tenant_table(lang)
        position_table = self._get_position_table(lang)
        course_table = self._get_course_table(lang)
        video_table = self._get_video_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 开始事务
                cursor.execute("START TRANSACTION")

                # 验证租户是否存在
                if tenant_id:
                    cursor.execute(
                        f"SELECT tenant_id FROM {tenant_table} WHERE tenant_id = %s AND status = 1 LIMIT 1",
                        (tenant_id,)
                    )
                    if not cursor.fetchone():
                        raise ValueError(f"租户ID不存在或已停用: {tenant_id}")

                # 验证岗位是否存在
                if position_id:
                    cursor.execute(
                        f"SELECT position_id FROM {position_table} WHERE position_id = %s LIMIT 1",
                        (position_id,)
                    )
                    if not cursor.fetchone():
                        raise ValueError(f"岗位ID不存在: {position_id}")

                # 1. 插入课程记录
                category = self._normalize_category(category)
                course_query = f"""
                    INSERT INTO {course_table} (
                        course_id, title, code, category, cover_url, description,
                        tags, status, video_count, total_duration, keywordslist,
                        position_id, version_code, tenant_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                # 计算视频总数和总时长
                video_count = len(videos) if videos else 0
                total_duration = 0
                if videos:
                    total_duration = sum(video.get('duration', 0) for video in videos)

                # 初始版本号为 v1
                version_code = "v1"

                cursor.execute(course_query, (
                    course_id, title, code, category, cover_url, description,
                    tags, status, video_count, total_duration, keywordslist,
                    position_id, version_code, tenant_id
                ))

                # 2. 如果有视频，插入视频记录
                video_ids = []
                if videos:
                    random_chars = ''.join(random.choices(string.ascii_uppercase, k=3))
                    random_nums = ''.join(random.choices(string.digits, k=3))
                    random_suffix = f"{random_chars}{random_nums}"
                    for index, video_data in enumerate(videos, start=1):
                        video_id = f"VIDEO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random_suffix}_{index}"
                        video_title = video_data.get('title')
                        video_url = video_data.get('video_url')
                        video_duration = video_data.get('duration', 0)
                        video_order_index = video_data.get('order_index', index)

                        video_query = f"""
                            INSERT INTO {video_table} (
                                video_id, course_id, title, video_url, duration, order_index
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(video_query, (
                            video_id, course_id, video_title, video_url,
                            video_duration, video_order_index
                        ))
                        video_ids.append(video_id)

                # 提交事务
                self.connection.commit()
                logger.info(f"租户【{tenant_id}】课程【{title}】新增成功，课程ID: {course_id}，版本: {version_code}")

                return {
                    "course_id": course_id,
                    "video_ids": video_ids,
                    "version_code": version_code,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 新增课程失败: {e}")
                raise

    def update_course_with_videos(
            self,
            course_id: str,
            title: str = None,
            category: str = None,
            description: str = None,
            status: str = None,
            videos: List[Dict] = None,
            keywordslist: str = None,
            position_id: int = None,
            tenant_id: int = None,  # 新增：租户ID（用于权限验证）
            lang: Optional[str] = "zh"  # 多语种：按 JWT.lang 路由业务表
    ) -> Dict:
        """更新课程记录（自动更新版本号，包含租户验证）"""
        position_table = self._get_position_table(lang)
        course_table = self._get_course_table(lang)
        video_table = self._get_video_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 开始事务
                cursor.execute("START TRANSACTION")

                # 1. 获取当前课程信息和版本号，同时验证租户权限
                cursor.execute(
                    f"""
                    SELECT title, version_code, position_id, tenant_id 
                    FROM {course_table} 
                    WHERE course_id = %s AND is_deleted = 0
                    LIMIT 1
                    """,
                    (course_id,)
                )
                course_info = cursor.fetchone()

                if not course_info:
                    raise ValueError(f"课程不存在: {course_id}")

                current_title, current_version, current_position_id, current_tenant_id = course_info

                # 验证租户权限（如果提供了tenant_id）
                # if tenant_id and current_tenant_id != tenant_id:
                #     raise ValueError(f"无权操作此课程，课程属于租户{current_tenant_id}")

                # 2. 验证岗位是否存在（如果提供了新的position_id）
                new_position_id = position_id if position_id is not None else current_position_id
                if new_position_id:
                    cursor.execute(
                        f"SELECT position_id FROM {position_table} WHERE position_id = %s LIMIT 1",
                        (new_position_id,)
                    )
                    if not cursor.fetchone():
                        raise ValueError(f"岗位ID不存在: {new_position_id}")

                # 3. 计算新版本号（每次更新自动加1）
                new_version = self._increment_version(current_version)

                # 4. 更新课程记录
                course_update_fields = []
                course_params = []

                if title is not None:
                    course_update_fields.append("title = %s")
                    course_params.append(title)
                if category is not None:
                    course_update_fields.append("category = %s")
                    course_params.append(self._normalize_category(category))
                if description is not None:
                    course_update_fields.append("description = %s")
                    course_params.append(description)
                if status is not None:
                    course_update_fields.append("status = %s")
                    course_params.append(status)
                if keywordslist is not None:
                    course_update_fields.append("keywordslist = %s")
                    course_params.append(keywordslist)
                if position_id is not None:
                    course_update_fields.append("position_id = %s")
                    course_params.append(position_id)

                # 如果有视频，更新视频计数和总时长
                if videos is not None:
                    video_count = len(videos)
                    total_duration = sum(video.get('duration', 0) for video in videos)
                    course_update_fields.append("video_count = %s")
                    course_update_fields.append("total_duration = %s")
                    course_params.extend([video_count, total_duration])

                # 添加版本更新
                course_update_fields.append("version_code = %s")
                course_params.append(new_version)

                if course_update_fields:
                    course_update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    course_query = f"""
                        UPDATE {course_table} 
                        SET {', '.join(course_update_fields)} 
                        WHERE course_id = %s
                    """
                    course_params.append(course_id)
                    cursor.execute(course_query, tuple(course_params))

                # 5. 如果有视频信息，处理视频更新
                if videos is not None:
                    # 先删除原有的视频（逻辑删除）
                    delete_video_query = f"DELETE From {video_table} WHERE course_id = %s"
                    cursor.execute(delete_video_query, (course_id,))

                    # 插入新的视频记录
                    random_chars = ''.join(random.choices(string.ascii_uppercase, k=3))
                    random_nums = ''.join(random.choices(string.digits, k=3))
                    random_suffix = f"{random_chars}{random_nums}"
                    for index, video_data in enumerate(videos, start=1):
                        video_id = f"VIDEO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random_suffix}_{index}"
                        video_title = video_data.get('title')
                        video_url = video_data.get('video_url')
                        video_duration = video_data.get('duration', 0)
                        video_order_index = video_data.get('order_index', index)

                        video_query = f"""
                            INSERT INTO {video_table} (
                                video_id, course_id, title, video_url, duration, order_index
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE 
                                title = VALUES(title),
                                video_url = VALUES(video_url),
                                duration = VALUES(duration),
                                order_index = VALUES(order_index),
                                updated_at = CURRENT_TIMESTAMP
                        """
                        cursor.execute(video_query, (
                            video_id, course_id, video_title, video_url,
                            video_duration, video_order_index
                        ))

                # 提交事务
                self.connection.commit()
                logger.info(
                    f"租户【{current_tenant_id}】课程ID【{course_id}】更新成功，版本从 {current_version} 更新到 {new_version}")

                return {
                    "success": True,
                    "old_version": current_version,
                    "new_version": new_version,
                    "tenant_id": current_tenant_id
                }
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新课程失败: {e}")
                raise

    def _increment_version(self, version: str) -> str:
        """版本号递增逻辑"""
        if not version:
            return "v1"

        try:
            # 提取版本号中的数字部分
            if version.startswith('v') or version.startswith('V'):
                version_num = version[1:]
            else:
                version_num = version

            # 尝试转换为数字
            version_num_int = int(version_num)
            return f"v{version_num_int + 1}"
        except (ValueError, TypeError):
            # 如果解析失败，返回 v1
            return "v1"

    def delete_course_logic(self, course_id: str, tenant_id: int = None, lang: Optional[str] = "zh") -> bool:
        """逻辑删除课程（包含租户验证）"""
        course_table = self._get_course_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 验证课程存在且属于指定租户
                # if tenant_id:
                #     cursor.execute(
                #         """
                #         SELECT course_id FROM sp_course
                #         WHERE course_id = %s AND tenant_id = %s AND is_deleted = 0
                #         LIMIT 1
                #         """,
                #         (course_id, tenant_id)
                #     )
                #     if not cursor.fetchone():
                #         raise ValueError(f"课程不存在或无权删除: {course_id}")

                query = f"UPDATE {course_table} SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE course_id = %s"
                cursor.execute(query, (course_id,))
                self.connection.commit()
                logger.info(f"课程ID【{course_id}】已逻辑删除")
                return True
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除课程失败: {e}")
                raise

    def query_course_list(
            self,
            keyword: str = None,
            category: str = None,
            status: str = None,
            position_id: int = None,
            department_id: int = None,
            company_id: int = None,
            position_name: str = None,
            department_name: str = None,
            company_name: str = None,
            tenant_id: int = None,  # 新增：租户ID筛选（None 表示 OWNER 跨租户全量）
            offset: int = 0,
            limit: int = 20,
            lang: Optional[str] = "zh"  # 多语种：按 JWT.lang 路由业务/组织表
    ):
        """课程列表查询（关联岗位+部门+公司表，包含租户筛选）"""
        course_table = self._get_course_table(lang)
        position_table = self._get_position_table(lang)
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        tenant_table = self._get_tenant_table(lang)
        general_position_name = self._get_general_position_name(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = ["c.is_deleted = 0"]
                params = []

                # 租户条件（OWNER 上游传 None 表示跨租户；普通用户必填以保证隔离）
                if tenant_id is not None:
                    where_clauses.append("c.tenant_id = %s")
                    params.append(tenant_id)

                # 基础条件（课程表）
                if keyword:
                    where_clauses.append("(c.title LIKE %s OR c.code LIKE %s OR c.description LIKE %s)")
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

                if category:
                    where_clauses.append("c.category = %s")
                    params.append(self._normalize_category(category))
                    where_clauses.append("c.status = %s")
                    params.append(status)

                # if position_id:
                #     where_clauses.append("c.position_id = %s")
                #     params.append(position_id)

                # 通用岗位文案按 lang 取，避免 zh/en/th 下 SQL 文本字面量失效
                cursor.execute(
                        f"""SELECT position_id FROM {position_table} 
                           WHERE tenant_id = %s AND position_name = %s""",
                        (tenant_id, general_position_name)
                    )
                general_positions = cursor.fetchall()

                if position_id:

                    if general_positions:
                        # 构建IN条件
                        general_position_ids = [str(p['position_id']) for p in general_positions]
                        placeholders = ', '.join(['%s'] * len(general_position_ids))

                        # 条件：指定的个人岗位 OR 通用岗位
                        where_clauses.append(f"(c.position_id = %s OR c.position_id IN ({placeholders}))")
                        params.append(position_id)
                        params.extend(general_position_ids)
                    else:
                        # 如果没有通用岗位，只查询指定岗位
                        where_clauses.append("c.position_id = %s")
                        params.append(position_id)

                # 关联表条件
                if department_id:
                    where_clauses.append("p.department_id = %s")
                    params.append(department_id)

                if company_id:
                    where_clauses.append("d.company_id = %s")
                    params.append(company_id)

                if position_name:
                    where_clauses.append("p.position_name LIKE %s")
                    params.append(f"%{position_name}%")

                if department_name:
                    where_clauses.append("d.department_name LIKE %s")
                    params.append(f"%{department_name}%")

                if company_name:
                    where_clauses.append("co.company_name LIKE %s")
                    params.append(f"%{company_name}%")

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                # 查询数据，关联岗位、部门和公司表
                query = f"""
                            SELECT 
                                c.course_id,
                                c.title,
                                c.code,
                                c.category,
                                c.cover_url,
                                c.description,
                                c.tags,
                                c.status,
                                c.video_count,
                                c.total_duration,
                                c.keywordslist,
                                c.position_id,
                                c.version_code,
                                c.tenant_id,  -- 返回租户ID
                                c.created_at,
                                c.updated_at,
                                -- 岗位信息
                                p.position_name,
                                -- 部门信息
                                d.department_id,
                                d.department_name,
                                -- 公司信息
                                co.company_id,
                                co.company_name,
                                -- 租户信息
                                t.tenant_name
                            FROM {course_table} c
                            LEFT JOIN {position_table} p ON c.position_id = p.position_id
                            LEFT JOIN {department_table} d ON p.department_id = d.department_id
                            LEFT JOIN {company_table} co ON d.company_id = co.company_id
                            LEFT JOIN {tenant_table} t ON c.tenant_id = t.tenant_id  -- 关联租户表
                            WHERE {where_sql}
                            ORDER BY c.created_at DESC
                            LIMIT %s OFFSET %s
                        """
                params.extend([limit, offset])
                cursor.execute(query, params)
                items = cursor.fetchall()

                # 解析JSON字段
                for item in items:
                    item['category'] = self._translate_category(item.get('category'), lang)
                    if item.get('tags') and isinstance(item['tags'], str):
                        try:
                            item['tags'] = json.loads(item['tags'])
                        except:
                            item['tags'] = []

                    if item.get('keywordslist') and isinstance(item['keywordslist'], str):
                        try:
                            item['keywordslist'] = json.loads(item['keywordslist'])
                        except:
                            item['keywordslist'] = []

                # 查询总数
                count_query = f"""
                            SELECT COUNT(*) as total 
                            FROM {course_table} c
                            LEFT JOIN {position_table} p ON c.position_id = p.position_id
                            LEFT JOIN {department_table} d ON p.department_id = d.department_id
                            LEFT JOIN {company_table} co ON d.company_id = co.company_id
                            WHERE {where_sql}
                        """
                cursor.execute(count_query, params[:-2] if len(params) > 2 else [])
                total_result = cursor.fetchone()
                total = total_result['total'] if total_result else 0

                return {
                    "total": total,
                    "items": items,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                logger.error(f"MySQL 查询课程列表失败: {e}")
                raise

    def query_course_info(self, course_id: str, tenant_id: int = None, lang: Optional[str] = "zh"):
        """课程详情（包含视频列表和关键词列表，包含租户验证）"""
        course_table = self._get_course_table(lang)
        video_table = self._get_video_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                # 1. 查询课程基本信息，加入租户验证
                where_clause = "course_id = %s AND is_deleted = 0"
                params = [course_id]

                # OWNER 上游传 None 表示跨租户访问；普通用户必填 tenant_id 限定隔离
                if tenant_id is not None:
                    where_clause += " AND tenant_id = %s"
                    params.append(tenant_id)

                course_query = f"""
                    SELECT 
                        course_id, title, code, category, cover_url, description,
                        tags, status, video_count, total_duration, keywordslist,
                        tenant_id, position_id,
                        created_at, updated_at
                    FROM {course_table} 
                    WHERE {where_clause}
                    LIMIT 1
                """
                cursor.execute(course_query, params)
                course_info = cursor.fetchone()

                if not course_info:
                    return None

                # 2. 查询课程的视频列表
                videos_query = f"""
                    SELECT 
                        video_id, title as video_title, video_url, 
                        duration, order_index, created_at, updated_at
                    FROM {video_table} 
                    WHERE course_id = %s
                    ORDER BY order_index ASC, created_at ASC
                """
                cursor.execute(videos_query, (course_id,))
                videos = cursor.fetchall()

                # 将视频信息整合到课程详情中
                course_info['videos'] = videos
                course_info['category'] = self._translate_category(course_info.get('category'), lang)

                # 解析keywordslist（如果是字符串，转换为JSON对象）
                if course_info.get('keywordslist') and isinstance(course_info['keywordslist'], str):
                    try:
                        course_info['keywordslist'] = json.loads(course_info['keywordslist'])
                    except:
                        course_info['keywordslist'] = []

                # 解析tags
                if course_info.get('tags') and isinstance(course_info['tags'], str):
                    try:
                        course_info['tags'] = json.loads(course_info['tags'])
                    except:
                        course_info['tags'] = []

                return course_info
            except Exception as e:
                logger.error(f"MySQL 查询课程详情失败: {e}")
                raise

    # ------------------------------
    # 学习资料模块（material）相关方法 - 程念负责
    # ------------------------------
    def upload_material(
            self,
            material_id: str,
            title: str,
            file_url: str,
            tenant_id: int,  # 新增
            description: str = None,
            category: str = None,
            course_id: str = None,
            position_id: int = None,
            file_type: str = None,
            size: int = None,
            lang: Optional[str] = "zh"  # 多语种：按 JWT.lang 路由业务表
    ) -> Dict:
        """新增学习资料记录（包含租户信息）"""
        tenant_table = self._get_tenant_table(lang)
        material_table = self._get_material_table(lang)
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

                # 插入资料记录
                category = self._normalize_category(category)
                query = f"""
                    INSERT INTO {material_table} (
                        material_id, title, description, category, course_id, 
                        file_type, file_url, size, position_id, tenant_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                cursor.execute(query, (
                    material_id, title, description, category, course_id,
                    file_type, file_url, size, position_id, tenant_id
                ))

                self.connection.commit()
                logger.info(f"租户【{tenant_id}】资料【{title}】上传成功，资料ID: {material_id}")

                return {
                    "material_id": material_id,
                    "title": title,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 上传资料失败: {e}")
                raise

    def update_material_info(
            self,
            material_id: str,
            tenant_id: int,  # 新增
            title: str = None,
            description: str = None,
            category: str = None,
            course_id: str = None,
            position_id: int = None,
            lang: Optional[str] = "zh"  # 多语种：按 JWT.lang 路由业务表
    ) -> bool:
        """更新学习资料信息（包含租户验证）"""
        material_table = self._get_material_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 构建更新字段
                update_fields = []
                params = []

                if title is not None:
                    update_fields.append("title = %s")
                    params.append(title)
                if description is not None:
                    update_fields.append("description = %s")
                    params.append(description)
                if category is not None:
                    update_fields.append("category = %s")
                    params.append(self._normalize_category(category))
                    update_fields.append("course_id = %s")
                    params.append(course_id)
                if position_id is not None:
                    # position_id为0表示清除关联
                    if position_id == 0:
                        update_fields.append("position_id = NULL")
                    else:
                        update_fields.append("position_id = %s")
                        params.append(position_id)

                if not update_fields:
                    return True  # 没有要更新的字段

                update_fields.append("updated_at = CURRENT_TIMESTAMP")

                # 添加WHERE条件（包含租户验证）
                query = f"""
                    UPDATE {material_table} 
                    SET {', '.join(update_fields)} 
                    WHERE material_id = %s AND tenant_id = %s AND is_deleted = 0
                """
                params.extend([material_id, tenant_id])

                cursor.execute(query, tuple(params))
                self.connection.commit()

                affected_rows = cursor.rowcount
                if affected_rows > 0:
                    logger.info(f"租户【{tenant_id}】资料ID【{material_id}】更新成功")
                    return True
                else:
                    logger.warning(f"租户【{tenant_id}】资料ID【{material_id}】不存在或无权更新")
                    return False
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新资料失败: {e}")
                raise

    def delete_material_logic(self, material_id: str, tenant_id: int, lang: Optional[str] = "zh") -> bool:
        """逻辑删除学习资料（包含租户验证）"""
        material_table = self._get_material_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                query = f"""
                    UPDATE {material_table} 
                    SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE material_id = %s AND is_deleted = 0
                """
                cursor.execute(query, (material_id))
                self.connection.commit()

                affected_rows = cursor.rowcount
                if affected_rows > 0:
                    logger.info(f"资料ID【{material_id}】已逻辑删除")
                    return True
                else:
                    logger.warning(f"资料ID【{material_id}】不存在或已删除")
                    return False
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 删除资料失败: {e}")
                raise

    # ------------------------------
    # 岗位表 - 查询（按ID）
    # ------------------------------
    def query_position_by_id(self, position_id: int, tenant_id: int = None, lang: Optional[str] = "zh") -> Optional[Dict]:
        """查询岗位信息（支持租户过滤；按 lang 路由组织表）"""
        position_table = self._get_position_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = ["position_id = %s"]
                params = [position_id]

                # 如果提供了租户ID，则加入租户过滤条件
                if tenant_id:
                    where_clauses.append("tenant_id = %s")
                    params.append(tenant_id)

                query = f"""
                    SELECT 
                        position_id,
                        position_name,
                        department_id,
                        tenant_id
                    FROM {position_table} 
                    WHERE {' AND '.join(where_clauses)}
                    LIMIT 1
                """
                cursor.execute(query, tuple(params))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询岗位信息失败: {e}")
                raise

    def query_material_by_id_and_tenant(self, material_id: str, tenant_id: int, lang: Optional[str] = "zh") -> Optional[Dict]:
        """根据资料ID和租户ID查询资料信息"""
        material_table = self._get_material_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = f"""
                    SELECT * FROM {material_table} 
                    WHERE material_id = %s AND tenant_id = %s AND is_deleted = 0
                    LIMIT 1
                """
                cursor.execute(query, (material_id, tenant_id))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询资料信息失败: {e}")
                raise

    def query_material_categories_by_tenant(self, tenant_id: Optional[int] = None, lang: Optional[str] = "zh") -> List[str]:
        """查询指定租户下的所有资料分类（tenant_id=None 表示 OWNER 跨租户）。
        从 DB 取 DISTINCT code，翻译为当前 lang 的 label 返回；
        未识别的自定义 code 原样返回，保持向前兼容。
        """
        material_table = self._get_material_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                if tenant_id is None:
                    query = f"""
                        SELECT DISTINCT category 
                        FROM {material_table} 
                        WHERE is_deleted = 0 AND category IS NOT NULL
                        ORDER BY category
                    """
                    cursor.execute(query)
                else:
                    query = f"""
                        SELECT DISTINCT category 
                        FROM {material_table} 
                        WHERE tenant_id = %s AND is_deleted = 0 AND category IS NOT NULL
                        ORDER BY category
                    """
                    cursor.execute(query, (tenant_id,))
                results = cursor.fetchall()
                codes = [row[0] for row in results if row[0]]
                return [self._translate_category(code, lang) for code in codes]
            except Exception as e:
                logger.error(f"MySQL 查询资料分类失败: {e}")
                raise

    def query_materials_list(
            self,
            tenant_id: int,  # 新增：租户ID（None 表示 OWNER 跨租户全量）
            keyword: str = None,
            category: str = None,
            course_id: str = None,
            position_id: int = None,
            department_id: int = None,
            company_id: int = None,
            position_name: str = None,
            department_name: str = None,
            company_name: str = None,
            offset: int = 0,
            limit: int = 20,
            lang: Optional[str] = "zh"  # 多语种：按 JWT.lang 路由业务/组织表
    ) -> Dict:
        """学习资料列表查询（包含租户筛选）"""
        material_table = self._get_material_table(lang)
        position_table = self._get_position_table(lang)
        department_table = self._get_department_table(lang)
        company_table = self._get_company_table(lang)
        general_position_name = self._get_general_position_name(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = ["m.is_deleted = 0"]
                params = []

                # OWNER 上游传 None 表示跨租户；普通用户必填 tenant_id 限定隔离
                if tenant_id is not None:
                    where_clauses.append("m.tenant_id = %s")
                    params.append(tenant_id)

                # 基础条件
                if keyword:
                    where_clauses.append("(m.title LIKE %s OR m.description LIKE %s)")
                    params.extend([f"%{keyword}%", f"%{keyword}%"])

                if category:
                    where_clauses.append("m.category = %s")
                    params.append(self._normalize_category(category))

                if course_id:
                    where_clauses.append("m.course_id = %s")
                    params.append(course_id)

                # 通用岗位文案按 lang 取，避免 zh/en/th 下 SQL 文本字面量失效
                cursor.execute(
                        f"""SELECT position_id FROM {position_table} 
                           WHERE tenant_id = %s AND position_name = %s""",
                        (tenant_id, general_position_name)
                    )
                general_positions = cursor.fetchall()

                if position_id:

                    if general_positions:
                        # 构建IN条件
                        general_position_ids = [str(p['position_id']) for p in general_positions]
                        placeholders = ', '.join(['%s'] * len(general_position_ids))

                        # 条件：指定的个人岗位 OR 通用岗位
                        where_clauses.append(f"(m.position_id = %s OR m.position_id IN ({placeholders}))")
                        params.append(position_id)
                        params.extend(general_position_ids)
                    else:
                        # 如果没有通用岗位，只查询指定岗位
                        where_clauses.append("m.position_id = %s")
                        params.append(position_id)

                # if position_id:
                #     where_clauses.append("m.position_id = %s")
                #     params.append(position_id)

                # 查询总数
                count_query = f"""
                    SELECT COUNT(*) as total 
                    FROM {material_table} m 
                    WHERE {' AND '.join(where_clauses)}
                """
                cursor.execute(count_query, tuple(params))
                total_result = cursor.fetchone()
                total = total_result['total'] if total_result else 0

                # 查询数据（关联岗位、部门、公司表）
                select_query = f"""
                    SELECT 
                        m.id,
                        m.material_id,
                        m.title,
                        m.description,
                        m.category,
                        m.course_id,
                        m.file_type,
                        m.file_url,
                        m.size,
                        m.position_id,
                        m.tenant_id,
                        m.created_at,
                        m.updated_at,
                        p.position_name,
                        d.department_id,
                        d.department_name,
                        co.company_id,
                        co.company_name
                    FROM {material_table} m
                    LEFT JOIN {position_table} p ON m.position_id = p.position_id AND p.tenant_id = m.tenant_id
                    LEFT JOIN {department_table} d ON p.department_id = d.department_id
                    LEFT JOIN {company_table} co ON d.company_id = co.company_id
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY m.created_at DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])
                cursor.execute(select_query, tuple(params))
                items = cursor.fetchall()

                for item in items:
                    item['category'] = self._translate_category(item.get('category'), lang)

                return {
                    "total": total,
                    "items": items
                }
            except Exception as e:
                logger.error(f"MySQL 查询资料列表失败: {e}")
                raise

    def query_accessible_file_reference(
            self,
            file_uri: str,
            tenant_id: int,
            position_id: int | None = None,
    ) -> Optional[Dict]:
        """查询当前租户/岗位是否有权访问指定的内部文件 URI。"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                course_position_clause, course_position_params = self._build_position_scope(
                    cursor,
                    table_alias="c",
                    tenant_id=tenant_id,
                    position_id=position_id,
                )
                material_position_clause, material_position_params = self._build_position_scope(
                    cursor,
                    table_alias="m",
                    tenant_id=tenant_id,
                    position_id=position_id,
                )

                cursor.execute(
                    f"""
                    SELECT
                        'video' AS resource_type,
                        v.video_id AS resource_id,
                        v.title AS resource_name,
                        v.video_url AS storage_uri,
                        c.course_id AS parent_id
                    FROM sp_video v
                    INNER JOIN sp_course c ON c.course_id = v.course_id
                    WHERE v.video_url = %s
                      AND c.is_deleted = 0
                      AND (%s = 1 OR c.tenant_id = %s)
                      {course_position_clause}
                    LIMIT 1
                    """,
                    (file_uri, tenant_id, tenant_id, *course_position_params),
                )
                record = cursor.fetchone()
                if record:
                    return record

                cursor.execute(
                    f"""
                    SELECT
                        'course_cover' AS resource_type,
                        c.course_id AS resource_id,
                        c.title AS resource_name,
                        c.cover_url AS storage_uri,
                        c.course_id AS parent_id
                    FROM sp_course c
                    WHERE c.cover_url = %s
                      AND c.is_deleted = 0
                      AND (%s = 1 OR c.tenant_id = %s)
                      {course_position_clause}
                    LIMIT 1
                    """,
                    (file_uri, tenant_id, tenant_id, *course_position_params),
                )
                record = cursor.fetchone()
                if record:
                    return record

                cursor.execute(
                    f"""
                    SELECT
                        'material' AS resource_type,
                        m.material_id AS resource_id,
                        m.title AS resource_name,
                        m.file_url AS storage_uri,
                        m.course_id AS parent_id
                    FROM sp_material m
                    WHERE m.file_url = %s
                      AND m.is_deleted = 0
                      AND (%s = 1 OR m.tenant_id = %s)
                      {material_position_clause}
                    LIMIT 1
                    """,
                    (file_uri, tenant_id, tenant_id, *material_position_params),
                )
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询文件访问权限失败: {e}")
                raise

    def _build_position_scope(
            self,
            cursor,
            table_alias: str,
            tenant_id: int,
            position_id: int | None,
            lang: Optional[str] = "zh",
    ) -> tuple[str, list[int]]:
        """构建岗位可见性 SQL 片段。

        通用岗位文案与 position 表均按 lang 路由，
        避免 en/th 语种下查不到通用岗位记录。
        """
        if tenant_id == 1 or not position_id:
            return "", []

        position_table = self._get_position_table(lang)
        general_position_name = self._get_general_position_name(lang)

        cursor.execute(
            f"""
            SELECT position_id
            FROM {position_table}
            WHERE tenant_id = %s AND position_name = %s
            """,
            (tenant_id, general_position_name),
        )
        general_positions = cursor.fetchall()
        params: list[int] = [position_id]
        placeholders = ""
        if general_positions:
            general_position_ids = [int(item["position_id"]) for item in general_positions]
            placeholders = ", ".join(["%s"] * len(general_position_ids))
            params.extend(general_position_ids)
            return f" AND ({table_alias}.position_id = %s OR {table_alias}.position_id IN ({placeholders}))", params
        return f" AND {table_alias}.position_id = %s", params

    def query_tenant_by_id(self, tenant_id: int, lang: Optional[str] = "zh") -> Optional[Dict]:
        """查询租户信息（按 lang 路由组织表）"""
        tenant_table = self._get_tenant_table(lang)
        self._connect()
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
    # 学习统计模块相关方法 - 程念负责
    # ------------------------------
    def query_video_learning_statistics(
            self,
            start_date: str = None,
            end_date: str = None,
            course_id: str = None,
            tenant_id: int = None,  # 新增：租户ID
            offset: int = 0,
            limit: int = 20,
            lang: Optional[str] = "zh"
    ):
        """视频学习统计分页查询（管理端：用户视频学习时长统计，包含租户隔离）"""
        learning_record_table = self._get_learning_record_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                # 验证租户权限
                # if not tenant_id:
                #     raise ValueError("租户ID不能为空")

                # 基础查询：按用户统计学习时长和视频数量
                base_query = f"""
                    SELECT 
                        lr.user_id,
                        u.name,
                        SUM(lr.watch_seconds) as total_watch_seconds,
                        COUNT(DISTINCT lr.video_id) as total_video_count         
                    FROM {learning_record_table} lr
                    LEFT JOIN sp_user u ON lr.user_id = u.id
                """

                where_clauses = ["lr.tenant_id = %s"]  # 租户条件
                params = [tenant_id]

                # 构建查询条件
                if start_date:
                    where_clauses.append("DATE(lr.start_time) >= %s")
                    params.append(start_date)

                if end_date:
                    where_clauses.append("DATE(lr.start_time) <= %s")
                    params.append(end_date)

                if course_id:
                    where_clauses.append("lr.course_id = %s")
                    params.append(course_id)

                where_sql = " AND ".join(where_clauses)

                # 查询分页数据
                query = f"""
                    {base_query}
                    WHERE {where_sql}
                    GROUP BY lr.user_id, u.name
                    ORDER BY total_watch_seconds DESC
                    LIMIT %s OFFSET %s
                """

                params.extend([limit, offset])
                cursor.execute(query, params)
                items = cursor.fetchall()

                # 查询总数
                count_query = f"""
                    SELECT COUNT(DISTINCT lr.user_id) as total
                    FROM {learning_record_table} lr
                    LEFT JOIN sp_user u ON lr.user_id = u.id
                    WHERE {where_sql}
                """
                cursor.execute(count_query, params[:-2] if len(params) > 2 else [])
                total_result = cursor.fetchone()
                total = total_result['total'] if total_result else 0

                return {
                    "total": total,
                    "items": items,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                logger.error(f"MySQL 查询视频学习统计失败: {e}")
                raise

    def query_user_learning_summary(self, user_id: int, tenant_id: int = None, lang: Optional[str] = "zh"):
        """用户学习统计概览（个人仪表盘，包含租户验证）"""
        learning_record_table = self._get_learning_record_table(lang)
        course_progress_table = self._get_course_progress_table(lang)
        course_table = self._get_course_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                # 验证用户是否属于指定租户
                if tenant_id:
                    # 验证用户是否属于该租户
                    cursor.execute(
                        "SELECT id FROM sp_user WHERE id = %s AND tenant_id = %s AND is_active = 1 LIMIT 1",
                        (user_id, tenant_id)
                    )
                    if not cursor.fetchone():
                        raise ValueError(f"用户不存在或不属于租户{tenant_id}")

                user_query = """
                    SELECT name
                    FROM sp_user
                    WHERE id = %s AND is_active = 1
                """
                user_params = [user_id]
                if tenant_id:
                    user_query += " AND tenant_id = %s"
                    user_params.append(tenant_id)
                user_query += " LIMIT 1"
                cursor.execute(user_query, user_params)
                user_info = cursor.fetchone() or {}

                # 1. 获取总学习时长和视频数量
                total_query = f"""
                    SELECT 
                        COALESCE(SUM(watch_seconds), 0) as total_watch_seconds,
                        COUNT(DISTINCT video_id) as total_video_count,
                        COUNT(DISTINCT course_id) as total_course_count
                    FROM {learning_record_table} 
                    WHERE user_id = %s
                """
                total_params = [user_id]

                if tenant_id:
                    total_query += " AND tenant_id = %s"
                    total_params.append(tenant_id)

                cursor.execute(total_query, total_params)
                total_stats = cursor.fetchone() or {}

                # 2. 获取今日学习时长
                today_query = f"""
                    SELECT COALESCE(SUM(watch_seconds), 0) as today_watch_seconds
                    FROM {learning_record_table} 
                    WHERE user_id = %s AND DATE(start_time) = CURDATE()
                """
                today_params = [user_id]

                if tenant_id:
                    today_query += " AND tenant_id = %s"
                    today_params.append(tenant_id)

                cursor.execute(today_query, today_params)
                today_stats = cursor.fetchone() or {}

                # 3. 获取课程进度列表
                course_progress_query = f"""
                    SELECT 
                        c.course_id,
                        c.title as course_title,
                        cp.progress_percent,
                        c.total_duration,
                        cp.last_learn_time
                    FROM {course_table} c
                    INNER JOIN {course_progress_table} cp
                        ON c.course_id = cp.course_id AND cp.user_id = %s
                """
                course_params = [user_id]

                if tenant_id:
                    course_progress_query += " AND c.tenant_id = %s"
                    course_params.append(tenant_id)

                course_progress_query += " ORDER BY cp.last_learn_time DESC"

                cursor.execute(course_progress_query, course_params)
                course_progress = cursor.fetchall()

                # 计算每个课程的进度百分比
                course_progress_list = []
                for course in course_progress:
                    progress_percent = course.get('progress_percent', 0)
                    course_progress_list.append({
                        "course_id": course.get('course_id'),
                        "course_title": course.get('course_title'),
                        "progress_percent": round(progress_percent, 2),
                        "last_learn_time": course.get('last_learn_time')
                    })

                return {
                    "user_id": user_id,
                    "user_name": user_info.get("name"),
                    "total_watch_seconds": total_stats.get('total_watch_seconds', 0),
                    "today_watch_seconds": today_stats.get('today_watch_seconds', 0),
                    "total_video_count": total_stats.get('total_video_count', 0),
                    "total_course_count": total_stats.get('total_course_count', 0),
                    "course_progress_list": course_progress_list
                }
            except Exception as e:
                logger.error(f"MySQL 查询用户学习统计失败: {e}")
                raise

    def query_tenant_learning_summary(
            self,
            tenant_id: int = None,
            offset: int = 0,
            limit: int = 20,
            lang: Optional[str] = "zh",
    ) -> Dict:
        """查询租户下所有用户学习汇总（管理端总览）。

        - tenant_id 为空：查询全部租户
        - tenant_id 有值：仅查询指定租户
        """
        learning_record_table = self._get_learning_record_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clause = ""
                params = []
                if tenant_id:
                    where_clause = "WHERE u.tenant_id = %s"
                    params.append(tenant_id)

                # 查询总数
                count_query = f"""
                    SELECT COUNT(*) AS total
                    FROM sp_user u
                    {where_clause}
                """
                cursor.execute(count_query, params)
                total_row = cursor.fetchone() or {}
                total = int(total_row.get("total") or 0)

                # 分页查询
                query_params = [*params, limit, offset]

                query = f"""
                    SELECT
                        u.id AS user_id,
                        u.name AS user_name,
                        u.tenant_id,
                        COALESCE(ls.total_watch_seconds, 0) AS total_watch_seconds,
                        COALESCE(today.today_watch_seconds, 0) AS today_watch_seconds,
                        COALESCE(ls.total_video_count, 0) AS total_video_count,
                        COALESCE(ls.total_course_count, 0) AS total_course_count
                    FROM sp_user u
                    LEFT JOIN (
                        SELECT
                            user_id,
                            tenant_id,
                            COALESCE(SUM(watch_seconds), 0) AS total_watch_seconds,
                            COUNT(DISTINCT video_id) AS total_video_count,
                            COUNT(DISTINCT course_id) AS total_course_count
                        FROM {learning_record_table}
                        GROUP BY user_id, tenant_id
                    ) ls ON ls.user_id = u.id AND ls.tenant_id = u.tenant_id
                    LEFT JOIN (
                        SELECT
                            user_id,
                            tenant_id,
                            COALESCE(SUM(watch_seconds), 0) AS today_watch_seconds
                        FROM {learning_record_table}
                        WHERE DATE(start_time) = CURDATE()
                        GROUP BY user_id, tenant_id
                    ) today ON today.user_id = u.id AND today.tenant_id = u.tenant_id
                    {where_clause}
                    ORDER BY total_watch_seconds DESC, u.id ASC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(query, query_params)
                items = cursor.fetchall()

                return {
                    "total": total,
                    "items": items,
                }
            except Exception as e:
                logger.error(f"MySQL 查询租户学习汇总失败: {e}")
                raise

    def insert_learning_session(
            self,
            session_id: str,
            user_id: int,
            course_id: str,
            video_id: str,
            from_position: int = 0,
            tenant_id: int = None,  # 新增：租户ID
            lang: Optional[str] = "zh"
    ) -> Dict:
        """创建学习会话（开始学习，包含租户验证）"""
        learning_record_table = self._get_learning_record_table(lang)
        course_table = self._get_course_table(lang)
        video_table = self._get_video_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 检查用户是否存在且属于指定租户
                if tenant_id:
                    cursor.execute(
                        "SELECT id, tenant_id FROM sp_user WHERE id = %s AND tenant_id = %s AND is_active = 1 LIMIT 1",
                        (user_id, tenant_id)
                    )
                    user_result = cursor.fetchone()
                    if not user_result:
                        raise ValueError(f"用户ID不存在或不属于租户{tenant_id}")
                else:
                    cursor.execute(
                        "SELECT id, tenant_id FROM sp_user WHERE id = %s AND is_active = 1 LIMIT 1",
                        (user_id,)
                    )
                    user_result = cursor.fetchone()
                    if not user_result:
                        raise ValueError(f"用户ID不存在: {user_id}")

                # 检查课程是否存在且属于指定租户
                course_query = f"SELECT course_id, tenant_id FROM {course_table} WHERE course_id = %s AND is_deleted = 0"
                if tenant_id:
                    course_query += " AND tenant_id = %s"
                    cursor.execute(course_query, (course_id, tenant_id))
                else:
                    cursor.execute(course_query, (course_id,))

                course_result = cursor.fetchone()
                if not course_result:
                    raise ValueError(f"课程ID不存在: {course_id}")

                # 检查视频是否存在且属于该课程
                cursor.execute(
                    f"SELECT video_id FROM {video_table} WHERE video_id = %s AND course_id = %s LIMIT 1",
                    (video_id, course_id)
                )
                if not cursor.fetchone():
                    raise ValueError(f"视频ID不存在或不属于该课程: {video_id}")

                # 获取用户的tenant_id（如果未提供）
                if not tenant_id and user_result:
                    tenant_id = user_result[1] if len(user_result) > 1 else None

                # 插入学习会话记录
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                query = f"""
                    INSERT INTO {learning_record_table} (
                        session_id, user_id, course_id, video_id, tenant_id,
                        start_time, from_position
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    session_id, user_id, course_id, video_id, tenant_id,
                    start_time, from_position
                ))
                self.connection.commit()

                logger.info(f"租户【{tenant_id}】用户【{user_id}】开始学习会话【{session_id}】")
                return {
                    "session_id": session_id,
                    "start_time": start_time,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 创建学习会话失败: {e}")
                raise

    def _apply_session_progress(
            self,
            cursor,
            session_id: str,
            session_watch_seconds: int,
            position: int,
            is_completed: bool,
            tenant_id: int,
            user_id: int,
            close_session: bool,
            lang: Optional[str] = "zh",
    ) -> Dict:
        """
        统一的会话累计写入逻辑（供 heartbeat 与 end 复用）

        - 入参 session_watch_seconds 为“本次会话累计观看时长”
        - 服务端按差值累计，避免重复计时
        - close_session=True 时写入 end_time
        """
        learning_record_table = self._get_learning_record_table(lang)
        video_table = self._get_video_table(lang)
        # 获取会话信息（加入租户与用户验证）
        if close_session:
            session_query = (
                "SELECT user_id, course_id, video_id, start_time, from_position, "
                "watch_seconds, end_time "
                f"FROM {learning_record_table} "
                "WHERE session_id = %s AND tenant_id = %s AND user_id = %s "
                "LIMIT 1"
            )
        else:
            session_query = (
                "SELECT user_id, course_id, video_id, start_time, from_position, "
                "watch_seconds, end_time "
                f"FROM {learning_record_table} "
                "WHERE session_id = %s AND tenant_id = %s AND user_id = %s "
                "AND end_time IS NULL "
                "LIMIT 1"
            )
        cursor.execute(session_query, (session_id, tenant_id, user_id))
        session = cursor.fetchone()
        if not session:
            raise ValueError(f"学习会话不存在或已结束: {session_id}")

        (
            record_user_id,
            course_id,
            video_id,
            start_time,
            from_position,
            current_watch_seconds,
            current_end_time,
        ) = session

        current_watch_seconds = int(current_watch_seconds or 0)
        session_watch_seconds = max(int(session_watch_seconds or 0), 0)
        delta_watch_seconds = max(session_watch_seconds - current_watch_seconds, 0)
        new_watch_seconds = max(session_watch_seconds, current_watch_seconds)

        # 计算观看进度
        cursor.execute(
            f"SELECT duration FROM {video_table} WHERE video_id = %s LIMIT 1",
            (video_id,)
        )
        video = cursor.fetchone()
        duration = int(video[0]) if video and video[0] else 0

        watch_progress = 0.0
        if duration > 0:
            if is_completed:
                watch_progress = 1.0
            else:
                watch_progress = min(position / duration, 1.0) if position > 0 else 0.0

        # 更新学习记录
        if close_session:
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            update_query = f"""
                UPDATE {learning_record_table} 
                SET end_time = %s,
                    watch_seconds = %s,
                    end_position = %s,
                    watch_progress = GREATEST(watch_progress, %s),
                    is_completed = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
            """
            cursor.execute(update_query, (
                end_time, new_watch_seconds, position,
                watch_progress, is_completed, session_id
            ))
        else:
            update_query = f"""
                UPDATE {learning_record_table} 
                SET watch_seconds = %s,
                    end_position = %s,
                    watch_progress = GREATEST(watch_progress, %s),
                    is_completed = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
            """
            cursor.execute(update_query, (
                new_watch_seconds, position,
                watch_progress, is_completed, session_id
            ))

        # 课程进度按差值累计
        self.upsert_course_progress(
            user_id=record_user_id,
            course_id=course_id,
            video_id=video_id,
            watched_seconds=delta_watch_seconds,
            progress_percent=watch_progress,
            last_position=position,
            is_completed=is_completed,
            tenant_id=tenant_id,
            lang=lang
        )

        # 用户学习汇总按差值累计；仅在 end 且本次首次标记完成时算视频完成数
        video_count_inc = 1 if (close_session and is_completed) else 0
        self.update_user_learning_summary(
            user_id=record_user_id,
            watch_seconds=delta_watch_seconds,
            video_count=video_count_inc,
            tenant_id=tenant_id,
            lang=lang
        )

        return {
            "session_id": session_id,
            "course_id": course_id,
            "video_id": video_id,
            "delta_watch_seconds": delta_watch_seconds,
            "session_watch_seconds": new_watch_seconds,
            "is_completed": bool(is_completed),
            "closed": bool(close_session),
        }

    def heartbeat_learning_session(
            self,
            session_id: str,
            session_watch_seconds: int,
            position: int,
            is_completed: bool,
            tenant_id: int,
            user_id: int,
            lang: Optional[str] = "zh",
    ) -> Dict:
        """心跳上报：按累计值入参，服务端按差值累计学习时长"""
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                result = self._apply_session_progress(
                    cursor=cursor,
                    session_id=session_id,
                    session_watch_seconds=session_watch_seconds,
                    position=position,
                    is_completed=is_completed,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    close_session=False,
                    lang=lang,
                )
                self.connection.commit()
                logger.info(
                    f"租户【{tenant_id}】用户【{user_id}】会话【{session_id}】心跳累计："
                    f"session={result['session_watch_seconds']}s, delta={result['delta_watch_seconds']}s"
                )
                return result
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 心跳上报失败: {e}")
                raise

    def end_learning_session(
            self,
            session_id: str,
            session_watch_seconds: int,
            position: int,
            tenant_id: int,
            user_id: int,
            is_completed: bool = False,
            lang: Optional[str] = "zh",
    ) -> Dict:
        """结束学习会话（按累计值收尾，避免与心跳重复累计）"""
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                result = self._apply_session_progress(
                    cursor=cursor,
                    session_id=session_id,
                    session_watch_seconds=session_watch_seconds,
                    position=position,
                    is_completed=is_completed,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    close_session=True,
                    lang=lang,
                )
                self.connection.commit()
                logger.info(
                    f"租户【{tenant_id}】用户【{user_id}】会话【{session_id}】结束，"
                    f"session={result['session_watch_seconds']}s, delta={result['delta_watch_seconds']}s"
                )
                return result
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 结束学习会话失败: {e}")
                raise

    def update_user_learning_summary(
            self,
            user_id: int,
            watch_seconds: int = 0,
            video_count: int = 0,
            course_count: int = 0,
            tenant_id: int = None,  # 新增：租户ID
            lang: Optional[str] = "zh"
    ) -> bool:
        """更新用户学习汇总统计（包含租户ID）"""
        summary_table = self._get_user_learning_summary_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 先检查是否存在
                check_query = f"SELECT id FROM {summary_table} WHERE user_id = %s"
                check_params = [user_id]

                if tenant_id:
                    check_query += " AND tenant_id = %s"
                    check_params.append(tenant_id)

                cursor.execute(check_query, check_params)
                existing = cursor.fetchone()

                if existing:
                    # 更新
                    update_query = f"""
                        UPDATE {summary_table} 
                        SET total_watch_seconds = total_watch_seconds + %s,
                            today_watch_seconds = IF(DATE(last_learn_time) = CURDATE(), 
                                                    today_watch_seconds + %s, %s),
                            total_video_count = total_video_count + %s,
                            total_course_count = GREATEST(total_course_count, %s),
                            tenant_id = COALESCE(%s, tenant_id),
                            last_learn_time = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                    """
                    cursor.execute(update_query, (
                        watch_seconds, watch_seconds, watch_seconds,
                        video_count, course_count, tenant_id, user_id
                    ))
                else:
                    # 插入
                    insert_query = f"""
                        INSERT INTO {summary_table} (
                            user_id, total_watch_seconds, today_watch_seconds,
                            total_video_count, total_course_count, tenant_id, last_learn_time
                        ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """
                    cursor.execute(insert_query, (
                        user_id, watch_seconds, watch_seconds,
                        video_count, course_count, tenant_id
                    ))

                self.connection.commit()
                logger.info(f"租户【{tenant_id}】用户【{user_id}】学习统计已更新")
                return True
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新学习统计失败: {e}")

    def query_user_course_progress_list(
            self,
            user_id: int,
            course_id: str = None,
            tenant_id: int = None,  # 新增：租户ID验证
            offset: int = 0,
            limit: int = 20,
            lang: Optional[str] = "zh"
    ) -> Dict:
        """查询用户课程学习进度列表（管理端，包含租户验证）"""
        course_progress_table = self._get_course_progress_table(lang)
        course_table = self._get_course_table(lang)
        learning_record_table = self._get_learning_record_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                # 构建查询条件
                where_clauses = ["lr.user_id = %s"]
                params = [user_id]

                if tenant_id:
                    where_clauses.append("lr.tenant_id = %s")
                    params.append(tenant_id)

                if course_id:
                    where_clauses.append("lr.course_id = %s")
                    params.append(course_id)

                where_sql = " AND ".join(where_clauses)

                # 查询用户学习进度
                query = f"""
                    SELECT 
                        lr.user_id,
                        u.name,
                        lr.course_id,
                        c.title as course_title,
                        c.total_duration,
                        lr.progress_percent,
                        lr.last_learn_time,
                        lr.tenant_id
                    FROM {course_progress_table} lr
                    LEFT JOIN sp_user u ON lr.user_id = u.id
                    LEFT JOIN {course_table} c ON lr.course_id = c.course_id
                    WHERE {where_sql} AND c.is_deleted = 0
                    ORDER BY last_learn_time DESC
                    LIMIT %s OFFSET %s
                """

                params.extend([limit, offset])
                cursor.execute(query, params)
                items = cursor.fetchall()

                # 计算进度百分比
                for item in items:
                    total_duration = item.get('total_duration', 0)
                    course_id = item.get('course_id')

                    if tenant_id:
                        progress_query = f"""
                            SELECT COALESCE(SUM(watch_seconds), 0) as total_watched
                            FROM {learning_record_table} 
                            WHERE user_id = %s AND course_id = %s AND tenant_id = %s
                        """
                        cursor.execute(progress_query, (user_id, course_id, tenant_id))
                    else:
                        progress_query = f"""
                            SELECT COALESCE(SUM(watch_seconds), 0) as total_watched
                            FROM {learning_record_table} 
                            WHERE user_id = %s AND course_id = %s
                        """
                        cursor.execute(progress_query, (user_id, course_id))

                    result = cursor.fetchone()
                    watched_seconds = result.get('total_watched', 0) if result else 0

                    progress_percent = 0.0
                    if total_duration > 0:
                        progress_percent = min(watched_seconds / total_duration, 1.0)
                        progress_percent = round(progress_percent, 2)

                    item['progress_percent'] = progress_percent

                # 查询总数
                count_query = f"""
                    SELECT COUNT(DISTINCT lr.course_id) as total
                    FROM {course_progress_table} lr
                    LEFT JOIN {course_table} c ON lr.course_id = c.course_id
                    WHERE {where_sql} AND c.is_deleted = 0
                """
                cursor.execute(count_query, params[:-2] if len(params) > 2 else [])
                total_result = cursor.fetchone()
                total = total_result.get('total', 0) if total_result else 0

                return {
                    "total": total,
                    "items": items
                }
            except Exception as e:
                logger.error(f"MySQL 查询用户课程进度列表失败: {e}")
                raise

    def query_tenant_course_progress_list(
            self,
            tenant_id: int = None,
            offset: int = 0,
            limit: int = 20,
            lang: Optional[str] = "zh",
    ) -> Dict:
        """查询租户下所有用户课程学习进度列表（管理端总览）。

        - tenant_id 为空：查询全部租户
        - tenant_id 有值：仅查询指定租户
        """
        course_progress_table = self._get_course_progress_table(lang)
        course_table = self._get_course_table(lang)
        learning_record_table = self._get_learning_record_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                where_clauses = ["c.is_deleted = 0"]
                params = []

                if tenant_id:
                    where_clauses.append("lr.tenant_id = %s")
                    params.append(tenant_id)

                where_sql = " AND ".join(where_clauses)

                # 查询总数
                count_query = f"""
                    SELECT COUNT(*) AS total
                    FROM {course_progress_table} lr
                    LEFT JOIN {course_table} c ON lr.course_id = c.course_id
                    WHERE {where_sql}
                """
                cursor.execute(count_query, params)
                total_row = cursor.fetchone() or {}
                total = int(total_row.get("total") or 0)

                # 分页查询
                query_params = [*params, limit, offset]

                query = f"""
                    SELECT
                        lr.user_id,
                        u.name,
                        lr.course_id,
                        c.title AS course_title,
                        c.total_duration,
                        lr.last_learn_time,
                        lr.tenant_id,
                        COALESCE(w.total_watched, 0) AS watched_seconds
                    FROM {course_progress_table} lr
                    LEFT JOIN sp_user u ON lr.user_id = u.id
                    LEFT JOIN {course_table} c ON lr.course_id = c.course_id
                    LEFT JOIN (
                        SELECT user_id, course_id, tenant_id, COALESCE(SUM(watch_seconds), 0) AS total_watched
                        FROM {learning_record_table}
                        GROUP BY user_id, course_id, tenant_id
                    ) w ON w.user_id = lr.user_id
                       AND w.course_id = lr.course_id
                       AND w.tenant_id = lr.tenant_id
                    WHERE {where_sql}
                    ORDER BY lr.last_learn_time DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(query, query_params)
                items = cursor.fetchall()

                for item in items:
                    total_duration = int(item.get('total_duration') or 0)
                    watched_seconds = int(item.get('watched_seconds') or 0)
                    if total_duration > 0:
                        item['progress_percent'] = round(min(watched_seconds / total_duration, 1.0), 2)
                    else:
                        item['progress_percent'] = 0.0

                return {
                    "total": total,
                    "items": items,
                }
            except Exception as e:
                logger.error(f"MySQL 查询租户课程进度列表失败: {e}")
                raise

    # ------------------------------
    # 学习进度模块相关方法
    # ------------------------------
    def upsert_course_progress(
            self,
            user_id: int,
            course_id: str,
            video_id: str,
            watched_seconds: int = 0,
            progress_percent: float = 0.0,
            last_position: int = 0,
            is_completed: bool = False,
            tenant_id: int = None,  # 新增：租户ID
            lang: Optional[str] = "zh"
    ) -> bool:
        """插入或更新课程学习进度（包含租户ID）"""
        course_progress_table = self._get_course_progress_table(lang)
        self._connect()
        with self.connection.cursor() as cursor:
            try:
                # 先检查是否存在
                check_query = f"""
                    SELECT id FROM {course_progress_table} 
                    WHERE user_id = %s AND course_id = %s AND video_id = %s
                """
                cursor.execute(check_query, (user_id, course_id, video_id))
                existing = cursor.fetchone()

                if existing:
                    # 更新
                    update_query = f"""
                        UPDATE {course_progress_table} 
                        SET watched_seconds = watched_seconds + %s,
                            progress_percent = GREATEST(progress_percent, %s),
                            last_position = GREATEST(last_position, %s),
                            is_completed = %s,
                            tenant_id = COALESCE(%s, tenant_id),  -- 更新租户ID（如果提供）
                            last_learn_time = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND course_id = %s AND video_id = %s
                    """
                    cursor.execute(update_query, (
                        watched_seconds, progress_percent, last_position,
                        is_completed, tenant_id, user_id, course_id, video_id
                    ))
                else:
                    # 插入
                    insert_query = f"""
                        INSERT INTO {course_progress_table} (
                            user_id, course_id, video_id, watched_seconds, progress_percent,
                            last_position, is_completed, tenant_id, last_learn_time
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """
                    cursor.execute(insert_query, (
                        user_id, course_id, video_id, watched_seconds, progress_percent,
                        last_position, is_completed, tenant_id
                    ))

                self.connection.commit()
                logger.info(f"租户【{tenant_id}】用户【{user_id}】课程【{course_id}】学习进度已更新")
                return True
            except Exception as e:
                self.connection.rollback()
                logger.error(f"MySQL 更新学习进度失败: {e}")
                raise

    def query_course_progress(self, user_id: int, course_id: str):
        """查询用户指定课程的学习进度"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                query = """
                    SELECT * From sp_course_progress 
                    WHERE user_id = %s AND course_id = %s
                    LIMIT 1
                """
                cursor.execute(query, (user_id, course_id))
                return cursor.fetchone()
            except Exception as e:
                logger.error(f"MySQL 查询学习进度失败: {e}")
                raise

    # ------------------------------
    # 学习统计模块相关方法
    # ------------------------------
    def query_course_learning_progress(
            self,
            user_id: int,
            course_id: str,
            tenant_id: int = None,  # 新增：租户ID验证
            lang: Optional[str] = "zh"
    ) -> Dict:
        """查询用户课程学习进度（个人，包含租户验证）"""
        course_table = self._get_course_table(lang)
        video_table = self._get_video_table(lang)
        course_progress_table = self._get_course_progress_table(lang)
        learning_record_table = self._get_learning_record_table(lang)
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                # # 1. 验证用户和课程属于同一租户
                # if tenant_id:
                #     # 验证用户
                #     cursor.execute(
                #         "SELECT id FROM sp_user WHERE id = %s AND tenant_id = %s LIMIT 1",
                #         (user_id, tenant_id)
                #     )
                #     if not cursor.fetchone():
                #         raise ValueError(f"用户不存在或不属于租户{tenant_id}")
                #
                #     # 验证课程
                #     cursor.execute(
                #         "SELECT course_id FROM sp_course WHERE course_id = %s AND tenant_id = %s AND is_deleted = 0 LIMIT 1",
                #         (course_id, tenant_id)
                #     )
                #     if not cursor.fetchone():
                #         raise ValueError(f"课程不存在或不属于租户{tenant_id}")

                # 2. 查询课程信息
                cursor.execute(
                    f"""
                    SELECT title, total_duration, video_count, tenant_id 
                    FROM {course_table} 
                    WHERE course_id = %s AND is_deleted = 0
                    LIMIT 1
                    """,
                    (course_id,)
                )
                course = cursor.fetchone()

                if not course:
                    raise ValueError(f"课程不存在: {course_id}")

                course_title = course.get('title', '')
                course_tenant_id = course.get('tenant_id')

                # 3. 查询课程下所有视频（以 sp_video 为主表，LEFT JOIN 学习进度）
                if tenant_id:
                    videos_query = f"""
                        SELECT 
                            v.video_id,
                            v.duration AS total_duration,
                            v.order_index,
                            cp.last_position,
                            cp.is_completed
                        FROM {video_table} v
                        LEFT JOIN {course_progress_table} cp
                            ON cp.course_id = v.course_id
                           AND cp.video_id = v.video_id
                           AND cp.user_id = %s
                           AND cp.tenant_id = %s
                        WHERE v.course_id = %s
                        ORDER BY v.order_index ASC
                    """
                    cursor.execute(videos_query, (user_id, tenant_id, course_id))
                else:
                    videos_query = f"""
                        SELECT 
                            v.video_id,
                            v.duration AS total_duration,
                            v.order_index,
                            cp.last_position,
                            cp.is_completed
                        FROM {video_table} v
                        LEFT JOIN {course_progress_table} cp
                            ON cp.course_id = v.course_id
                           AND cp.video_id = v.video_id
                           AND cp.user_id = %s
                        WHERE v.course_id = %s
                        ORDER BY v.order_index ASC
                    """
                    cursor.execute(videos_query, (user_id, course_id))

                rows = cursor.fetchall()

                # 4. 查询每个视频的累计观看时长（来自 sp_learning_record）
                videos = []
                for row in rows:
                    video_id = row.get('video_id')
                    total_duration = int(row.get('total_duration') or 0)
                    last_position = int(row.get('last_position') or 0)
                    is_completed = bool(row.get('is_completed') or 0)

                    if tenant_id:
                        cursor.execute(
                            f"""
                            SELECT COALESCE(SUM(watch_seconds), 0) AS watched
                            FROM {learning_record_table}
                            WHERE user_id = %s AND course_id = %s AND video_id = %s AND tenant_id = %s
                            """,
                            (user_id, course_id, video_id, tenant_id)
                        )
                    else:
                        cursor.execute(
                            f"""
                            SELECT COALESCE(SUM(watch_seconds), 0) AS watched
                            FROM {learning_record_table}
                            WHERE user_id = %s AND course_id = %s AND video_id = %s
                            """,
                            (user_id, course_id, video_id)
                        )
                    watched_row = cursor.fetchone() or {}
                    watched_seconds = int(watched_row.get('watched') or 0)

                    if total_duration > 0:
                        progress_percent = round(min(watched_seconds / total_duration, 1.0), 2)
                    else:
                        progress_percent = 0.0

                    videos.append({
                        "video_id": video_id or "",
                        "total_duration": total_duration,
                        "watched_seconds": watched_seconds,
                        "progress_percent": progress_percent,
                        "last_position": last_position,
                        "is_completed": is_completed,
                    })

                return {
                    "course_id": course_id,
                    "course_title": course_title,
                    "tenant_id": course_tenant_id,
                    "videos": videos,
                }
            except Exception as e:
                logger.error(f"MySQL 查询课程学习进度失败: {e}")
                raise


    def count_video_learning_statistics(self, **conditions) -> int:
        """视频学习统计计数"""
        self._connect()
        with self.connection.cursor(DictCursor) as cursor:
            try:
                count_query = """
                    SELECT COUNT(DISTINCT lr.user_id) as total
                    From sp_learning_record lr
                    LEFT JOIN sp_user u ON lr.user_id = u.id
                """

                where_clauses = []
                params = []

                if 'start_date' in conditions and conditions['start_date']:
                    where_clauses.append("DATE(lr.start_time) >= %s")
                    params.append(conditions['start_date'])

                if 'end_date' in conditions and conditions['end_date']:
                    where_clauses.append("DATE(lr.start_time) <= %s")
                    params.append(conditions['end_date'])

                if 'course_id' in conditions and conditions['course_id']:
                    where_clauses.append("lr.course_id = %s")
                    params.append(conditions['course_id'])

                if 'user_id' in conditions and conditions['user_id']:
                    where_clauses.append("lr.user_id = %s")
                    params.append(conditions['user_id'])

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                query = f"{count_query} WHERE {where_sql}"
                cursor.execute(query, params)

                result = cursor.fetchone()
                return result['total'] if result and result['total'] else 0
            except Exception as e:
                logger.error(f"MySQL 统计视频学习数据失败: {e}")
                raise
