# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from comps import CustomLogger
from comps.dashboard.models.model import DashboardStatistics, User, UserSession
from comps.dashboard.config.base_config import (
    ACTIVE_USER_DAYS,
    ACTIVE_USER_MIN_SECONDS,
    EXAM_PASS_SCORE
)
from comps.dashboard.utils import (
    format_compare_result,
    get_previous_period_range,
    resolve_lang,
    exam_record_table,
    learning_record_table,
)
logger = CustomLogger("dashboard_statistics", "INFO")


class StatisticsService:
    """统计服务类"""

    def __init__(self, db: Session, tenant_id: int, data_lang: str = "zh"):
        """
        初始化统计服务

        Args:
            db: 数据库会话
            tenant_id: 租户ID
            data_lang: 业务语种（zh/en/th），决定考试/学习记录表路由及用户语种过滤
        """
        self.db = db
        self.tenant_id = tenant_id
        self.data_lang = resolve_lang(data_lang)

    def calculate_total_users(self, as_of_date: datetime = None) -> int:
        """
        计算总用户量（当前租户 + 当前 data_lang 下的活跃用户）

        Args:
            as_of_date: 截止日期，可选

        Returns:
            用户总数
        """
        try:
            from sqlalchemy import func
            query = self.db.query(func.count(User.id)).filter(
                User.tenant_id == self.tenant_id,
                User.lang == self.data_lang,
                User.is_active == True,
                User.deleted_at.is_(None)
            )

            if as_of_date:
                query = query.filter(User.created_at <= as_of_date)

            count = query.scalar() or 0

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 总用户量: {count}"
            )
            return count
        except Exception as e:
            logger.error(f"计算总用户量失败: {str(e)}")
            raise

    def calculate_active_users(
            self,
            days: int = None,
            min_seconds: int = None,
            start_date: datetime = None,
            end_date: datetime = None
    ) -> int:
        """
        计算活跃用户数
        定义：时间范围内累计在线时长 >= min_seconds 秒的当前语种用户

        Args:
            days: 统计最近N天，默认使用配置值 (当没有提供 start_date 和 end_date 时)
            min_seconds: 最少在线时长（秒），默认使用配置值
            start_date: 开始日期，可选
            end_date: 结束日期，可选

        Returns:
            活跃用户数
        """
        if min_seconds is None:
            min_seconds = ACTIVE_USER_MIN_SECONDS

        try:
            from sqlalchemy import func
            # 计算每个用户在时间范围内的总在线时长
            # NOTE: TIMESTAMPDIFF is MySQL-specific
            subquery = self.db.query(
                UserSession.user_id,
                func.sum(
                    func.timestampdiff(
                        text("SECOND"),
                        UserSession.login_time,
                        func.coalesce(UserSession.last_active_time, UserSession.login_time)
                    )
                ).label('total_seconds')
            ).join(
                User,
                User.id == UserSession.user_id
            ).filter(
                User.tenant_id == self.tenant_id,
                User.lang == self.data_lang,
                User.is_active == True,
                User.deleted_at.is_(None),
                UserSession.tenant_id == self.tenant_id
            )

            if start_date and end_date:
                subquery = subquery.filter(UserSession.login_time >= start_date, UserSession.login_time <= end_date)
            else:
                if days is None:
                    days = ACTIVE_USER_DAYS
                cutoff_time = datetime.now() - timedelta(days=days)
                subquery = subquery.filter(UserSession.login_time >= cutoff_time)

            subquery = subquery.group_by(UserSession.user_id).subquery()

            # 统计满足最小在线时长的用户数
            active_count = self.db.query(
                func.count(subquery.c.user_id)
            ).filter(
                subquery.c.total_seconds >= min_seconds
            ).scalar() or 0

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 活跃用户数: {active_count} "
                f"(>= {min_seconds}秒)"
            )
            return active_count
        except Exception as e:
            logger.error(f"计算活跃用户数失败: {str(e)}")
            raise

    def calculate_total_learn_seconds(
            self,
            start_date: datetime = None,
            end_date: datetime = None
    ) -> int:
        """
        计算总学习时长（秒）
        来源：
        1. sp_learning_record{_lang}.watch_seconds
        2. sp_exam_record{_lang} 的考试时长（end_time - start_time）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            总学习时长（秒）
        """
        try:
            lr_table = learning_record_table(self.data_lang)
            er_table = exam_record_table(self.data_lang)

            # 1. 学习记录时长
            lr_where = ["tenant_id = :tenant_id"]
            lr_params: Dict[str, Any] = {"tenant_id": self.tenant_id}

            if start_date:
                lr_where.append("start_time >= :start_date")
                lr_params["start_date"] = start_date
            if end_date:
                lr_where.append("end_time <= :end_date")
                lr_params["end_date"] = end_date

            learn_sql = text(
                f"SELECT COALESCE(SUM(watch_seconds), 0) AS s "
                f"FROM {lr_table} WHERE {' AND '.join(lr_where)}"
            )
            learn_seconds = self.db.execute(learn_sql, lr_params).scalar() or 0

            # 2. 考试记录时长
            # NOTE: ExamRecord.user_id is String(255) but User.id is Integer — CAST required
            er_where = [
                "u.tenant_id = :tenant_id",
                "u.lang = :data_lang",
                "er.start_time IS NOT NULL",
                "er.end_time IS NOT NULL",
            ]
            er_params: Dict[str, Any] = {"tenant_id": self.tenant_id, "data_lang": self.data_lang}

            if start_date:
                er_where.append("er.start_time >= :start_date")
                er_params["start_date"] = start_date
            if end_date:
                er_where.append("er.end_time <= :end_date")
                er_params["end_date"] = end_date

            exam_sql = text(
                f"SELECT COALESCE("
                f"SUM(TIMESTAMPDIFF(SECOND, er.start_time, er.end_time)), 0) AS s "
                f"FROM {er_table} er "
                f"JOIN sp_user u ON u.id = CAST(er.user_id AS UNSIGNED) "
                f"WHERE {' AND '.join(er_where)}"
            )
            exam_seconds = self.db.execute(exam_sql, er_params).scalar() or 0

            total_seconds = int(learn_seconds) + int(exam_seconds)

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 总学习时长: {total_seconds}秒 "
                f"(学习: {learn_seconds}秒, 考试: {exam_seconds}秒)"
            )
            return total_seconds
        except Exception as e:
            logger.error(f"计算总学习时长失败: {str(e)}")
            raise

    def calculate_avg_pass_rate(
            self,
            start_date: datetime = None,
            end_date: datetime = None,
            pass_score: float = None
    ) -> float:
        """
        计算平均达标率
        达标定义：accumulated_score >= pass_score（默认60分）
        去重规则：按 (user_id, position_id) 组合去重，保留最高分

        Args:
            start_date: 开始日期
            end_date: 结束日期
            pass_score: 及格分数，默认使用配置值

        Returns:
            平均达标率（百分比，如 78.55）
        """
        if pass_score is None:
            pass_score = EXAM_PASS_SCORE

        try:
            er_table = exam_record_table(self.data_lang)

            where = [
                "u.tenant_id = :tenant_id",
                "u.lang = :data_lang",
                "er.accumulated_score IS NOT NULL",
            ]
            params: Dict[str, Any] = {"tenant_id": self.tenant_id, "data_lang": self.data_lang}

            if start_date:
                where.append("er.start_time >= :start_date")
                params["start_date"] = start_date
            if end_date:
                where.append("er.end_time <= :end_date")
                params["end_date"] = end_date

            sql = text(
                f"SELECT er.id, er.user_id, er.position_id, er.accumulated_score "
                f"FROM {er_table} er "
                f"JOIN sp_user u ON u.id = CAST(er.user_id AS UNSIGNED) "
                f"WHERE {' AND '.join(where)}"
            )
            records = self.db.execute(sql, params).fetchall()

            if not records:
                logger.info(
                    f"租户 {self.tenant_id} (lang={self.data_lang}) 暂无考试记录"
                )
                return 0.0

            # 按 (user_id, position_id) 去重，保留最高分
            unique_exams: Dict[Any, float] = {}
            for record in records:
                key = (record.user_id, record.position_id)
                if key not in unique_exams or record.accumulated_score > unique_exams[key]:
                    unique_exams[key] = record.accumulated_score

            # 计算达标率
            total_count = len(unique_exams)
            passed_count = sum(
                1 for score in unique_exams.values() if score >= pass_score
            )

            pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0.0

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 平均达标率: {pass_rate:.2f}% "
                f"({passed_count}/{total_count})"
            )
            return round(pass_rate, 2)
        except Exception as e:
            logger.error(f"计算平均达标率失败: {str(e)}")
            raise

    def calculate_exam_count(
            self,
            start_date: datetime = None,
            end_date: datetime = None
    ) -> int:
        """
        计算考试场次

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            考试场次
        """
        try:
            er_table = exam_record_table(self.data_lang)

            where = ["u.tenant_id = :tenant_id", "u.lang = :data_lang"]
            params: Dict[str, Any] = {"tenant_id": self.tenant_id, "data_lang": self.data_lang}

            if start_date:
                where.append("er.start_time >= :start_date")
                params["start_date"] = start_date
            if end_date:
                where.append("er.end_time <= :end_date")
                params["end_date"] = end_date

            sql = text(
                f"SELECT COUNT(er.id) AS c "
                f"FROM {er_table} er "
                f"JOIN sp_user u ON u.id = CAST(er.user_id AS UNSIGNED) "
                f"WHERE {' AND '.join(where)}"
            )
            count = self.db.execute(sql, params).scalar() or 0

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 考试场次: {count}"
            )
            return int(count)
        except Exception as e:
            logger.error(f"计算考试场次失败: {str(e)}")
            raise

    def get_statistics_with_comparison(
            self,
            current_start: datetime,
            current_end: datetime
    ) -> Dict[str, Any]:
        """
        获取统计数据及环比对比

        Args:
            current_start: 当前周期开始时间
            current_end: 当前周期结束时间

        Returns:
            包含当前数据和对比数据的字典
        """
        try:
            # 计算前一周期的时间范围
            previous_start, previous_end = get_previous_period_range(current_start, current_end)

            logger.info(f"当前周期: {current_start} ~ {current_end}")

            # 当前周期数据
            current_data = {
                'total_users': self.calculate_total_users(as_of_date=current_end),
                'active_users': self.calculate_active_users(start_date=current_start, end_date=current_end),
                'total_learn_seconds': self.calculate_total_learn_seconds(
                    current_start, current_end
                ),
                'avg_pass_rate': self.calculate_avg_pass_rate(
                    current_start, current_end
                ),
                'exam_count': self.calculate_exam_count(
                    current_start, current_end
                )
            }

            logger.info(f"前一周期: {previous_start} ~ {previous_end}")
            # 前一周期数据：优先尝试从历史快照中查询
            snapshot = self.db.query(DashboardStatistics).filter(
                DashboardStatistics.tenant_id == self.tenant_id,
                DashboardStatistics.lang == self.data_lang,
                DashboardStatistics.period_type == "week",
                DashboardStatistics.period_start == previous_start.date(),
                DashboardStatistics.period_end == previous_end.date()
            ).first()

            if snapshot:
                logger.info(
                    f"命中缓存快照: tenant={self.tenant_id} lang={self.data_lang} "
                    f"week ({previous_start.date()} ~ {previous_end.date()})"
                )
                previous_data = {
                    'total_users': snapshot.total_users,
                    'active_users': snapshot.active_users,
                    'total_learn_seconds': snapshot.total_learn_seconds,
                    'avg_pass_rate': snapshot.avg_pass_rate,
                    'exam_count': snapshot.exam_count
                }
            else:
                logger.info(
                    f"未命中快照，降级实时计算: tenant={self.tenant_id} "
                    f"lang={self.data_lang} week ({previous_start.date()} ~ {previous_end.date()})"
                )
                previous_data = {
                    'total_users': self.calculate_total_users(as_of_date=previous_end),
                    'active_users': self.calculate_active_users(start_date=previous_start, end_date=previous_end),
                    'total_learn_seconds': self.calculate_total_learn_seconds(
                        previous_start, previous_end
                    ),
                    'avg_pass_rate': self.calculate_avg_pass_rate(
                        previous_start, previous_end
                    ),
                    'exam_count': self.calculate_exam_count(
                        previous_start, previous_end
                    )
                }

            # 计算差值（环比增长）
            comparison = {}
            for key in current_data:
                is_pct = (key == 'avg_pass_rate')
                comparison[key] = format_compare_result(current_data[key], previous_data[key], is_percentage=is_pct)

            return {
                'current': current_data,
                'previous': previous_data,
                'comparison': comparison
            }
        except Exception as e:
            logger.error(f"获取对比数据失败: {str(e)}")
            # 返回默认值
            return {
                'current': {
                    'total_users': 0,
                    'active_users': 0,
                    'total_learn_seconds': 0,
                    'avg_pass_rate': 0.0,
                    'exam_count': 0
                },
                'previous': {
                    'total_users': 0,
                    'active_users': 0,
                    'total_learn_seconds': 0,
                    'avg_pass_rate': 0.0,
                    'exam_count': 0
                },
                'comparison': {
                    'total_users': "",
                    'active_users': "",
                    'total_learn_seconds': "",
                    'avg_pass_rate': "",
                    'exam_count': ""
                }
            }

    def save_statistics_snapshot(
            self,
            period_type: str,
            period_start: datetime,
            period_end: datetime,
            stats: Dict[str, Any]
    ):
        """
        保存统计快照到数据库

        Args:
            period_type: 周期类型（day/week/month）
            period_start: 周期开始日期
            period_end: 周期结束日期
            stats: 统计数据字典
        """
        try:
            snapshot = DashboardStatistics(
                tenant_id=self.tenant_id,
                lang=self.data_lang,
                period_type=period_type,
                period_start=period_start.date(),
                period_end=period_end.date(),
                total_users=stats.get('total_users', 0),
                active_users=stats.get('active_users', 0),
                total_learn_seconds=stats.get('total_learn_seconds', 0),
                avg_pass_rate=stats.get('avg_pass_rate', 0.0),
                exam_count=stats.get('exam_count', 0)
            )

            self.db.add(snapshot)
            self.db.commit()

            logger.info(
                f"保存统计快照成功 - 租户: {self.tenant_id}, lang: {self.data_lang}, "
                f"周期: {period_type}, {period_start.date()} ~ {period_end.date()}"
            )
        except Exception as e:
            logger.error(f"保存统计快照失败: {str(e)}")
            self.db.rollback()
