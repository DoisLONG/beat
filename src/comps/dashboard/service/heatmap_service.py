# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import math
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from sqlalchemy.exc import SQLAlchemyError
from comps import CustomLogger
from comps.dashboard.models.model import User, UserSession
from comps.dashboard.utils import resolve_lang

logger = CustomLogger("heatmap_service", "INFO")


class HeatmapService:
    def __init__(self, db: Session, tenant_id: int, data_lang: str = "zh") -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.data_lang = resolve_lang(data_lang)

    def get_heatmap_by_month(self, target_month: date, department_id: int | None = None) -> list[dict]:
        """
        根据指定月份查询用户活动热力图数据
        """
        start_date = target_month.replace(day=1)
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
        return self._query_and_build_heatmap(start_date, end_date, department_id)

    def get_heatmap_by_days(self, target_date: date, days: int = 30, department_id: int | None = None) -> list[dict]:
        """
        根据指定日期往前推 days 天查询用户活动热力图数据
        """
        end_date = target_date
        start_date = target_date - timedelta(days=days - 1)
        return self._query_and_build_heatmap(start_date, end_date, department_id)

    def _query_and_build_heatmap(self, start_date: date, end_date: date, department_id: int | None = None) -> list[dict]:
        """
        查询指定日期范围内的用户活动热力图数据
        数据粒度为每2小时一个数据点
        """
        try:

            # 构建基础查询，关联 UserSession 和 User
            query = (
                self.db.query(
                    func.date(UserSession.login_time).label("stat_date"),
                    (func.hour(UserSession.login_time) / 2).cast(Integer).label("time_slot"),
                    func.count(func.distinct(UserSession.user_id)).label("user_count")
                )
                .join(User, User.id == UserSession.user_id)
                .filter(
                    UserSession.tenant_id == self.tenant_id,
                    User.lang == self.data_lang,
                    UserSession.login_time >= start_date,
                    UserSession.login_time < (end_date + timedelta(days=1))
                )
            )

            # 如果指定了部门，则添加筛选
            if department_id:
                query = query.filter(User.department_id == department_id)

            # 按日期和时间段分组
            results = query.group_by("stat_date", "time_slot").order_by("stat_date", "time_slot").all()

            # 预先生成所有可能的时间点，用于填充空值
            all_points = {}
            current_date = start_date
            while current_date <= end_date:
                for i in range(12):  # 12个两小时时间段
                    all_points[(current_date.isoformat(), i)] = {"count": 0}
                current_date += timedelta(days=1)

            # 填充真实数据
            for r in results:
                stat_date_iso = r.stat_date.isoformat() if hasattr(r.stat_date, 'isoformat') else str(r.stat_date)
                if (stat_date_iso, r.time_slot) in all_points:
                    all_points[(stat_date_iso, r.time_slot)]["count"] = r.user_count

            # 找到当月查询结果中的最大在线人数
            max_count = max((data["count"] for data in all_points.values()), default=0)

            # 格式化输出并计算level
            heatmap_data = []
            for (stat_date, time_slot), data in all_points.items():
                count = data["count"]
                level = 0
                if max_count > 0 and count > 0:
                    # 使用 math.ceil 和 log 来实现更平滑的等级分布
                    # 将等级映射到 1-10，而不是 0-9
                    level = min(10, math.ceil(count / max_count * 10))

                start_hour = time_slot * 2
                end_hour = start_hour + 2
                heatmap_data.append({
                    "date": stat_date,
                    "time_period": f"{start_hour:02d}:00-{end_hour:02d}:00",
                    "count": count,
                    "level": level
                })

            return heatmap_data

        except SQLAlchemyError as e:
            logger.exception(f"查询热力图数据失败: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"热力图服务异常: {str(e)}")
            raise
