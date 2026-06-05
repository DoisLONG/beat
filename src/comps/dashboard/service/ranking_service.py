# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from comps import CustomLogger
from comps.dashboard.config.base_config import EXAM_PASS_SCORE
from comps.dashboard.models.model import User, Department, Position, SOPLeaderboard
from comps.dashboard.utils import resolve_lang, sop_info_table

logger = CustomLogger("ranking_service", "INFO")


class RankingService:
    """成绩排行服务类 - 提供 SOP 列表查询和成绩排行功能

    排行榜数据直接读取 sp_sop_leaderboard 表（由 LeaderboardService 维护），
    不在此处做实时排名计算，保证接口高性能。
    """

    def __init__(self, db: Session, tenant_id: int, data_lang: str = "zh"):
        self.db = db
        self.tenant_id = tenant_id
        self.data_lang = resolve_lang(data_lang)

    def get_sop_list(
        self,
        keyword: Optional[str] = None,
        department_id: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询 SOP 列表，支持关键词、部门、时间范围筛选"""
        try:
            sop_table = sop_info_table(self.data_lang)

            params: Dict[str, Any] = {"tenant_id": self.tenant_id}
            where_clauses = ["tenant_id = :tenant_id"]

            if keyword:
                # 使用参数化 LIKE 防止 SQL 注入
                where_clauses.append("title LIKE :keyword")
                params["keyword"] = f"%{keyword}%"

            if start_time:
                start_dt = datetime.strptime(start_time, "%Y-%m-%d").date()
                where_clauses.append("start_time >= :start_dt")
                params["start_dt"] = start_dt

            if end_time:
                end_dt = datetime.strptime(end_time, "%Y-%m-%d").date()
                where_clauses.append("start_time <= :end_dt")
                params["end_dt"] = end_dt

            if department_id is not None:
                # Position 不拆语种表，仍用 ORM
                position_rows = self.db.query(Position.position_id).filter(
                    Position.department_id == department_id
                ).all()
                dept_position_ids = [str(row.position_id) for row in position_rows]

                if not dept_position_ids:
                    return []

                # 用占位符列表绑定 IN 参数
                placeholders = []
                for idx, pid in enumerate(dept_position_ids):
                    key = f"pid_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = pid
                where_clauses.append(f"position_id IN ({', '.join(placeholders)})")

            sql = text(
                f"SELECT id, title FROM {sop_table} "
                f"WHERE {' AND '.join(where_clauses)} "
                f"ORDER BY created_at DESC"
            )

            rows = self.db.execute(sql, params).fetchall()
            result = [{"sop_id": row.id, "sop_title": row.title} for row in rows]

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) 查询 SOP 列表，"
                f"共 {len(result)} 条"
            )
            return result

        except Exception as e:
            logger.error(f"查询 SOP 列表失败: {str(e)}")
            return []

    def get_ranking(self, sop_id: int) -> Dict[str, Any]:
        """
        获取成绩排行数据。

        排行数据直接读取 sp_sop_leaderboard 表，按 tenant + lang 过滤。
        该表由 LeaderboardService.update_leaderboard() 在考试完成后维护。
        """
        try:
            exam_info = self._get_exam_info(sop_id)
            ranking_list = self._query_leaderboard(sop_id)
            count = len(ranking_list)

            logger.info(
                f"租户 {self.tenant_id} (lang={self.data_lang}) "
                f"查询 SOP {sop_id} 排行，共 {count} 条"
            )
            return {
                "exam_info": exam_info,
                "ranking": ranking_list,
                "count": count
            }

        except Exception as e:
            logger.error(f"查询成绩排行失败: {str(e)}")
            return {"exam_info": {}, "ranking": [], "count": 0}

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _query_leaderboard(self, sop_id: int) -> List[Dict[str, Any]]:
        """从 sp_sop_leaderboard 读取该 SOP + 当前语种的排行数据，关联用户和部门信息"""
        try:
            rows = (
                self.db.query(
                    SOPLeaderboard.rank,
                    SOPLeaderboard.user_id,
                    SOPLeaderboard.score,
                    SOPLeaderboard.rank_change,
                    SOPLeaderboard.last_rank,
                    User.name.label("user_name"),
                    Department.department_name.label("department_name"),
                )
                .join(User, User.id == SOPLeaderboard.user_id)
                .outerjoin(Department, Department.department_id == User.department_id)
                .filter(
                    SOPLeaderboard.sop_id == sop_id,
                    SOPLeaderboard.tenant_id == self.tenant_id,
                    SOPLeaderboard.lang == self.data_lang,
                    User.lang == self.data_lang,
                    User.deleted_at.is_(None),
                )
                .order_by(SOPLeaderboard.rank.asc())
                .all()
            )

            result = []
            for row in rows:
                result.append({
                    "rank": row.rank,
                    "user_id": row.user_id,
                    "user_name": row.user_name or "",
                    "department": row.department_name or "",
                    "score": float(row.score) if row.score is not None else 0.0,
                    # rank_change 为 None 表示新上榜，前端可展示 "NEW"
                    "rank_change": row.rank_change,
                })

            logger.info(
                f"SOP {sop_id} (lang={self.data_lang}) 排行榜共 {len(result)} 条记录"
            )
            return result

        except Exception as e:
            logger.error(f"读取排行榜表失败: {str(e)}")
            return []

    def _get_exam_info(self, sop_id: int) -> Dict[str, Any]:
        """获取考试基本信息及统计数据"""
        try:
            sop_table = sop_info_table(self.data_lang)
            sop_row = self.db.execute(
                text(
                    f"SELECT id, title, position_id, start_time, end_time "
                    f"FROM {sop_table} "
                    f"WHERE id = :sop_id AND tenant_id = :tenant_id"
                ),
                {"sop_id": sop_id, "tenant_id": self.tenant_id},
            ).fetchone()

            if not sop_row:
                logger.warning(
                    f"租户 {self.tenant_id} (lang={self.data_lang}) 未找到 SOP {sop_id}"
                )
                return {}

            # 安全地将 position_id 转换为整数
            try:
                position_ids: List[int] = [int(sop_row.position_id)] if sop_row.position_id else []
            except (ValueError, TypeError):
                logger.warning(
                    f"SOP {sop_id} 的 position_id '{sop_row.position_id}' 无法转换为整数"
                )
                position_ids = []

            total_participants = 0
            if position_ids:
                total_participants = self.db.query(
                    func.count(func.distinct(User.id))
                ).filter(
                    User.position_id.in_(position_ids),
                    User.tenant_id == self.tenant_id,
                    User.lang == self.data_lang,
                    User.deleted_at.is_(None)
                ).scalar() or 0
            # 完成数从 sp_sop_leaderboard 按 tenant + lang + score 过滤
            completed_participants = self.db.query(
                func.count(func.distinct(SOPLeaderboard.user_id))
            ).filter(
                SOPLeaderboard.sop_id == sop_id,
                SOPLeaderboard.tenant_id == self.tenant_id,
                SOPLeaderboard.lang == self.data_lang,
                SOPLeaderboard.score >= EXAM_PASS_SCORE
            ).scalar() or 0

            completion_rate = 0.0
            if total_participants > 0:
                completion_rate = round(completed_participants / total_participants * 100, 2)

            department = ""
            if position_ids:
                position = self.db.query(Position).filter(
                    Position.position_id == position_ids[0]
                ).first()
                if position and position.department_id:
                    dept = self.db.query(Department).filter(
                        Department.department_id == position.department_id
                    ).first()
                    if dept:
                        department = dept.department_name

            logger.info(
                f"SOP {sop_id} (lang={self.data_lang}) 考试信息: 应考 {total_participants} 人，"
                f"已完成 {completed_participants} 人，完成率 {completion_rate}%"
            )
            return {
                "sop_id": sop_row.id,
                "sop_title": sop_row.title,
                "department": department,
                "start_time": sop_row.start_time.strftime("%Y-%m-%d") if sop_row.start_time else None,
                "end_time": sop_row.end_time.strftime("%Y-%m-%d") if sop_row.end_time else None,
                "total_participants": total_participants,
                "completed_participants": completed_participants,
                "completion_rate": completion_rate
            }

        except Exception as e:
            logger.error(f"获取考试信息失败: {str(e)}")
            return {}
