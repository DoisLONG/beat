# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from comps import CustomLogger
from comps.dashboard.models.model import User
from comps.dashboard.utils import (
    resolve_lang,
    course_table,
    learning_record_table,
    sop_info_table,
    exam_record_table,
)

logger = CustomLogger("dashboard_task_board", "INFO")


class TaskBoardService:
    def __init__(self, db: Session, tenant_id: int, data_lang: str = "zh"):
        self.db = db
        self.tenant_id = tenant_id
        self.data_lang = resolve_lang(data_lang)

    def get_task_board(self, start_date: datetime, end_date: datetime) -> Dict[str, List[Dict[str, Any]]]:
        course_tasks = self._build_course_tasks(start_date, end_date)
        sop_tasks = self._build_sop_tasks(start_date, end_date)
        task_list = sorted(course_tasks + sop_tasks, key=lambda item: item["discovery_time"], reverse=True)

        return {
            "list": [
                {
                    "task_id": int(item["task_id"]),
                    "task_name": item["task_name"],
                    "task_type": item["task_type"],
                    "participant_count": int(item["participant_count"]),
                    "should_participant_count": int(item["should_participant_count"]),
                    "study_duration": float(item["study_duration"]),
                    "health_status": float(item["health_status"]),
                }
                for item in task_list
            ]
        }

    def _build_course_tasks(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        c_table = course_table(self.data_lang)
        courses = self.db.execute(
            text(
                f"SELECT id, course_id, title, position_id, created_at "
                f"FROM {c_table} "
                f"WHERE tenant_id = :tenant_id "
                f"  AND is_deleted = 0 "
                f"  AND created_at >= :start_date "
                f"  AND created_at <= :end_date "
                f"ORDER BY created_at DESC"
            ),
            {"tenant_id": self.tenant_id, "start_date": start_date, "end_date": end_date},
        ).fetchall()

        result: List[Dict[str, Any]] = []
        for course in courses:
            expected_count = self._count_expected_participants(course.position_id)
            participant_count = self._count_course_participants(course.course_id, course.position_id)
            total_seconds = self._sum_course_duration(course.course_id)

            result.append(
                {
                    "task_id": course.id,
                    "task_name": course.title,
                    "task_type": "video",
                    "participant_count": participant_count,
                    "should_participant_count": expected_count,
                    "study_duration": self._seconds_to_hours(total_seconds),
                    "health_status": self._calculate_health(participant_count, expected_count, total_seconds),
                    "discovery_time": course.created_at,
                }
            )

        return result

    def _build_sop_tasks(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        sop_tbl = sop_info_table(self.data_lang)
        sops = self.db.execute(
            text(
                f"SELECT id, title, position_id, start_time "
                f"FROM {sop_tbl} "
                f"WHERE tenant_id = :tenant_id "
                f"  AND start_time IS NOT NULL "
                f"  AND start_time >= :start_date "
                f"  AND start_time <= :end_date "
                f"ORDER BY start_time DESC"
            ),
            {
                "tenant_id": self.tenant_id,
                "start_date": start_date.date(),
                "end_date": end_date.date(),
            },
        ).fetchall()

        result: List[Dict[str, Any]] = []
        for sop in sops:
            normalized_position = self._normalize_position_id(sop.position_id)  # 当前sop的岗位获取
            expected_count = self._count_expected_participants(normalized_position)  # 岗位有多少人
            participant_count = self._count_sop_participants(sop.id, normalized_position)  # 实际学习了多少人
            total_seconds = self._sum_sop_duration(sop.id)  # 一共学习了多少秒

            result.append(
                {
                    "task_id": sop.id,
                    "task_name": sop.title,
                    "task_type": "sop",
                    "participant_count": participant_count,
                    "should_participant_count": expected_count,
                    "study_duration": self._seconds_to_hours(total_seconds),
                    "health_status": self._calculate_health(participant_count, expected_count, total_seconds),
                    "discovery_time": datetime.combine(sop.start_time, datetime.min.time()),
                }
            )

        return result

    def _normalize_position_id(self, position_id: str | int | None) -> int | None:
        if position_id is None:
            logger.warning("任务岗位为空，按0人处理")
            return None

        try:
            return int(position_id)
        except (ValueError, TypeError):
            logger.warning(f"岗位ID无法转换为整数: {position_id}")
            return None

    def _count_expected_participants(self, position_id: int | None) -> int:
        if position_id is None:
            return 0

        from sqlalchemy import func
        return (
            self.db.query(func.count(User.id))
            .filter(
                User.tenant_id == self.tenant_id,
                User.lang == self.data_lang,
                User.is_active == True,
                User.deleted_at.is_(None),
                User.position_id == position_id,
            )
            .scalar()
            or 0
        )

    def _count_course_participants(self, course_id: str, position_id: int | None) -> int:
        if position_id is None:
            return 0

        lr_table = learning_record_table(self.data_lang)
        count = self.db.execute(
            text(
                f"SELECT COUNT(DISTINCT lr.user_id) "
                f"FROM {lr_table} lr "
                f"JOIN sp_user u ON u.id = lr.user_id "
                f"WHERE lr.tenant_id = :tenant_id "
                f"  AND lr.course_id = :course_id "
                f"  AND u.tenant_id = :tenant_id "
                f"  AND u.lang = :data_lang "
                f"  AND u.deleted_at IS NULL "
                f"  AND u.position_id = :position_id"
            ),
            {
                "tenant_id": self.tenant_id,
                "course_id": course_id,
                "data_lang": self.data_lang,
                "position_id": position_id,
            },
        ).scalar() or 0
        return int(count)

    def _count_sop_participants(self, sop_id: int, position_id: int | None) -> int:
        er_table = exam_record_table(self.data_lang)
        params = {"tenant_id": self.tenant_id, "sop_id": sop_id, "data_lang": self.data_lang}
        position_filter = ""
        if position_id is not None:
            position_filter = "AND u.position_id = :position_id"
            params["position_id"] = position_id

        count = self.db.execute(
            text(
                f"SELECT COUNT(DISTINCT CAST(er.user_id AS UNSIGNED)) "
                f"FROM {er_table} er "
                f"JOIN sp_user u ON u.id = CAST(er.user_id AS UNSIGNED) "
                f"WHERE er.tenant_id = :tenant_id "
                f"  AND er.sop_id = :sop_id "
                f"  AND u.tenant_id = :tenant_id "
                f"  AND u.lang = :data_lang "
                f"  AND u.deleted_at IS NULL "
                f"  {position_filter}"
            ),
            params,
        ).scalar() or 0
        return int(count)

    def _sum_course_duration(self, course_id: str) -> int:
        lr_table = learning_record_table(self.data_lang)
        total_seconds = self.db.execute(
            text(
                f"SELECT COALESCE(SUM(watch_seconds), 0) "
                f"FROM {lr_table} "
                f"WHERE tenant_id = :tenant_id AND course_id = :course_id"
            ),
            {"tenant_id": self.tenant_id, "course_id": course_id},
        ).scalar() or 0
        return int(total_seconds)

    def _sum_sop_duration(self, sop_id: int) -> int:
        er_table = exam_record_table(self.data_lang)
        total_seconds = self.db.execute(
            text(
                f"SELECT COALESCE(SUM("
                f"  CASE WHEN start_time IS NOT NULL "
                f"        AND end_time IS NOT NULL "
                f"        AND end_time >= start_time "
                f"       THEN TIMESTAMPDIFF(SECOND, start_time, end_time) "
                f"       ELSE 0 END"
                f"), 0) "
                f"FROM {er_table} "
                f"WHERE tenant_id = :tenant_id AND sop_id = :sop_id"
            ),
            {"tenant_id": self.tenant_id, "sop_id": sop_id},
        ).scalar()
        return int(total_seconds or 0)

    @staticmethod
    def _seconds_to_hours(seconds: int) -> float:
        return round(seconds / 3600, 1)

    @staticmethod
    def _calculate_health(participant_count: int, should_participant_count: int, total_duration_seconds: int) -> float:
        if should_participant_count <= 0:
            return 0.0

        participation_score = (participant_count / should_participant_count) * 40

        baseline_seconds = should_participant_count * 4 * 3600
        if baseline_seconds <= 0:
            duration_base_score = 0.0
            duration_bonus = 0.0
        else:
            duration_base_score = min((total_duration_seconds / baseline_seconds) * 60, 60)
            duration_bonus = max((total_duration_seconds - baseline_seconds) / 3600, 0)

        return round(participation_score + duration_base_score + duration_bonus, 2)
