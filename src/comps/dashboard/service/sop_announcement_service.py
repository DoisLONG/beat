# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import text

from comps import CustomLogger
from comps.dashboard.utils import resolve_lang, sop_info_table

logger = CustomLogger("sop_announcement", "INFO")


class SOPAnnouncementService:
    """SOP公告服务类 - 用于查询新增和即将到期的SOP"""

    def __init__(self, db: Session, tenant_id: int, data_lang: str = "zh"):
        """
        初始化SOP公告服务

        Args:
            db: 数据库会话
            tenant_id: 租户ID
            data_lang: 业务语种（zh/en/th），决定 SOP 表路由
        """
        self.db = db
        self.tenant_id = tenant_id
        self.data_lang = resolve_lang(data_lang)

    @staticmethod
    def _get_today() -> date:
        """获取当前日期，便于测试替换。"""
        return date.today()

    @staticmethod
    def _get_now() -> datetime:
        """获取当前时间，便于测试替换。"""
        return datetime.now()

    def _calculate_days_left(self, end_date: date) -> int | float:
        """兼容旧字段：计算剩余天数；当天截止时返回 0.x。"""
        today = self._get_today()
        if end_date > today:
            return (end_date - today).days

        end_of_day = datetime.combine(end_date, time.max)
        remaining_days = (end_of_day - self._get_now()).total_seconds() / 86400
        return round(max(remaining_days, 0.0), 2)

    def _calculate_time_left(self, end_date: date) -> Dict[str, Any]:
        """计算展示用剩余时间；当天截止时切换为小时。"""
        today = self._get_today()
        if end_date > today:
            return {
                "time_left": (end_date - today).days,
                "time_left_unit": "day",
            }

        end_of_day = datetime.combine(end_date, time.max)
        remaining_hours = (end_of_day - self._get_now()).total_seconds() / 3600
        return {
            "time_left": round(max(remaining_hours, 0.0), 2),
            "time_left_unit": "hour",
        }

    def get_new_sops(self, start_date: str) -> List[Dict[str, Any]]:
        """
        查询指定日期之后生效的新SOP

        Args:
            start_date: 开始日期字符串，格式：YYYY-MM-DD

        Returns:
            新SOP列表，每个元素包含 SOP 基本信息
        """
        try:
            # 解析日期字符串
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            today = self._get_today()

            sop_table = sop_info_table(self.data_lang)

            sql = text(
                f"SELECT id, title, start_time, end_time, position_id, sop_version "
                f"FROM {sop_table} "
                f"WHERE tenant_id = :tenant_id "
                f"  AND start_time IS NOT NULL "
                f"  AND start_time >= :start_dt "
                f"  AND (end_time IS NULL OR end_time >= :today) "
                f"ORDER BY start_time DESC"
            )
            rows = self.db.execute(
                sql,
                {"tenant_id": self.tenant_id, "start_dt": start_dt, "today": today},
            ).fetchall()

            result = []
            for row in rows:
                result.append({
                    "id": row.id,
                    "title": row.title,
                    "start_time": row.start_time.strftime("%Y-%m-%d") if row.start_time else None,
                    "end_time": row.end_time.strftime("%Y-%m-%d") if row.end_time else None,
                    "position_id": row.position_id,
                    "sop_version": row.sop_version,
                })

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 查询到 {len(result)} 个新SOP "
                f"(起始日期: {start_date})"
            )
            return result

        except ValueError as e:
            logger.error(f"日期格式错误: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"查询新SOP失败: {str(e)}")
            return []

    def get_expiring_sops(self, warning_window: int = 7) -> List[Dict[str, Any]]:
        """
        查询即将到期的SOP（在指定天数内到期的SOP）

        Args:
            warning_window: 预警窗口期（天数），默认7天

        Returns:
            即将到期的SOP列表，包含兼容字段 days_left，以及展示字段 time_left / time_left_unit
        """
        try:
            today = self._get_today()
            warning_date = today + timedelta(days=warning_window)

            sop_table = sop_info_table(self.data_lang)

            sql = text(
                f"SELECT id, title, start_time, end_time, position_id, sop_version "
                f"FROM {sop_table} "
                f"WHERE tenant_id = :tenant_id "
                f"  AND end_time IS NOT NULL "
                f"  AND end_time >= :today "
                f"  AND end_time <= :warning_date "
                f"ORDER BY end_time ASC"
            )
            rows = self.db.execute(
                sql,
                {
                    "tenant_id": self.tenant_id,
                    "today": today,
                    "warning_date": warning_date,
                },
            ).fetchall()

            result = []
            for row in rows:
                if row.end_time:
                    days_left = self._calculate_days_left(row.end_time)
                    time_left_info = self._calculate_time_left(row.end_time)
                    result.append({
                        "id": row.id,
                        "title": row.title,
                        "start_time": row.start_time.strftime("%Y-%m-%d") if row.start_time else None,
                        "end_time": row.end_time.strftime("%Y-%m-%d"),
                        "days_left": days_left,
                        "time_left": time_left_info["time_left"],
                        "time_left_unit": time_left_info["time_left_unit"],
                        "position_id": row.position_id,
                        "sop_version": row.sop_version,
                    })

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 查询到 {len(result)} 个即将到期的SOP "
                f"(预警窗口: {warning_window}天)"
            )
            return result

        except Exception as e:
            logger.error(f"查询即将到期SOP失败: {str(e)}")
            return []

    def get_announcements(
        self,
        start_date: str | None = None,
        warning_window: int = 7
    ) -> Dict[str, Any]:
        """
        获取公告数据（包括新SOP和即将到期的SOP）

        Args:
            start_date: 新SOP的起始日期，可选，默认为7天前
            warning_window: 到期预警窗口（天数），默认7天

        Returns:
            包含新SOP和即将到期SOP的字典
        """
        try:
            # 如果未提供起始日期，默认查询7天内的新SOP
            if not start_date:
                default_start = self._get_today() - timedelta(days=7)
                start_date = default_start.strftime("%Y-%m-%d")

            new_sops = self.get_new_sops(start_date)
            expiring_sops = self.get_expiring_sops(warning_window)

            return {
                "new": new_sops,
                "expiring": expiring_sops,
                "summary": {
                    "new_count": len(new_sops),
                    "expiring_count": len(expiring_sops),
                    "query_date": self._get_today().strftime("%Y-%m-%d")
                }
            }

        except Exception as e:
            logger.error(f"获取公告数据失败: {str(e)}")
            return {
                "new": [],
                "expiring": [],
                "summary": {
                    "new_count": 0,
                    "expiring_count": 0,
                    "query_date": self._get_today().strftime("%Y-%m-%d")
                }
            }
