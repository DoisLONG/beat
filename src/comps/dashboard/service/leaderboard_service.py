# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
LeaderboardService - 排行榜维护服务

职责：在用户提交/更新考试成绩后，重新计算该 SOP 的排行榜并写入 sp_sop_leaderboard 表。
查询排行榜数据请使用 RankingService.get_ranking()，不应在此处实现查询逻辑。

触发时机（业务侧调用）：
    1. 用户新完成一次考试，写入 sp_exam_record 后调用 update_leaderboard(sop_id, tenant_id)
    2. 管理员调整某用户成绩后同样触发

排名规则：
    - 每个用户取最新一次考试记录（start_time DESC）
    - 首先按分数降序排列
    - 分数相同者，考试开始时间升序（用时短者优先）
"""

from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from comps import CustomLogger
from comps.dashboard.models.model import SOPLeaderboard, User
from comps.dashboard.utils import exam_record_table, resolve_lang

logger = CustomLogger("leaderboard_service", "INFO")


class LeaderboardService:
    """排行榜维护服务 - 负责在考试记录变更后刷新 sp_sop_leaderboard"""

    def __init__(self, db: Session):
        """
        Args:
            db: 数据库会话（调用方负责 commit / rollback）
        """
        self.db = db

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def update_leaderboard(self, sop_id: int, tenant_id: int, data_lang: str = "zh") -> int:
        """
        核心方法：重新计算指定 SOP 的排行榜并持久化到 sp_sop_leaderboard。

        步骤：
            1. 从 sp_exam_record{_lang} 查询该 SOP 下每个用户的最新成绩并排名
            2. 读取 sp_sop_leaderboard 中已存在的排名（按 tenant + lang 隔离）
            3. 逐行 upsert：更新 rank / score / last_rank / rank_change / update_time
            4. 删除已不在新排名中的历史记录（用户成绩已被移除的场景）

        Args:
            sop_id:    SOP ID（必须来自当前 data_lang 的 sp_sop_info*）
            tenant_id: 租户 ID（用于隔离数据）
            data_lang: 业务语种（zh/en/th），决定考试记录表和排行榜分区

        Returns:
            本次更新/插入影响的行数
        """
        data_lang = resolve_lang(data_lang)
        logger.info(
            f"开始更新排行榜 - sop_id={sop_id}, tenant_id={tenant_id}, data_lang={data_lang}"
        )

        # 1. 计算新排名
        new_ranking: List[Dict] = self._compute_ranking(sop_id, tenant_id, data_lang)

        if not new_ranking:
            logger.info(
                f"SOP {sop_id} (lang={data_lang}) 暂无考试记录，跳过排行榜更新"
            )
            return 0

        # 2. 读取现有排行榜（用于 rank_change 计算）
        existing_map: Dict[int, int] = self._get_existing_rank_map(sop_id, tenant_id, data_lang)

        # 3. Upsert 逐行写入
        now = datetime.now()
        upserted = 0

        new_user_ids = set()
        for item in new_ranking:
            uid: int = item["user_id"]
            new_user_ids.add(uid)

            current_rank: int = item["rank"]
            score: float = item["score"]

            old_rank = existing_map.get(uid)  # None 表示新上榜

            rank_change = (old_rank - current_rank) if old_rank is not None else None

            row = (
                self.db.query(SOPLeaderboard)
                .filter(
                    SOPLeaderboard.sop_id == sop_id,
                    SOPLeaderboard.user_id == uid,
                    SOPLeaderboard.tenant_id == tenant_id,
                    SOPLeaderboard.lang == data_lang,
                )
                .first()
            )

            if row is None:
                # 新上榜用户
                row = SOPLeaderboard(
                    sop_id=sop_id,
                    user_id=uid,
                    tenant_id=tenant_id,
                    lang=data_lang,
                    rank=current_rank,
                    score=score,
                    last_rank=None,
                    rank_change=None,  # 新上榜无变化数据
                    update_time=now,
                )
                self.db.add(row)
            else:
                # 已上榜用户：记录旧排名再更新
                row.last_rank = row.rank
                row.rank = current_rank
                row.score = score
                row.rank_change = rank_change
                row.update_time = now

            upserted += 1

        # 4. 删除已不在新排名中的历史记录
        if existing_map:
            stale_user_ids = set(existing_map.keys()) - new_user_ids
            if stale_user_ids:
                deleted = (
                    self.db.query(SOPLeaderboard)
                    .filter(
                        SOPLeaderboard.sop_id == sop_id,
                        SOPLeaderboard.tenant_id == tenant_id,
                        SOPLeaderboard.lang == data_lang,
                        SOPLeaderboard.user_id.in_(stale_user_ids),
                    )
                    .delete(synchronize_session=False)
                )
                logger.info(
                    f"SOP {sop_id} (lang={data_lang}) 清理过期排行榜记录 {deleted} 条"
                )

        self.db.flush()
        self.db.commit()
        logger.info(
            f"排行榜更新完成 - sop_id={sop_id}, tenant_id={tenant_id}, "
            f"data_lang={data_lang}, upserted={upserted} 条"
        )
        return upserted

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _compute_ranking(self, sop_id: int, tenant_id: int, data_lang: str) -> List[Dict]:
        """
        从 sp_exam_record{_lang} 计算排名：每用户取最新一次记录，
        按分数降序、开始时间升序排列。

        Args:
            sop_id:    SOP ID
            tenant_id: 租户 ID
            data_lang: 业务语种

        Returns:
            排名列表，每项 {"rank": int, "user_id": int, "score": float}
        """
        exam_table = exam_record_table(data_lang)

        sql = text(f"""
            WITH latest_exam AS (
                SELECT
                    er.user_id,
                    er.accumulated_score,
                    er.start_time,
                    ROW_NUMBER() OVER (
                        PARTITION BY er.user_id
                        ORDER BY er.start_time DESC
                    ) AS rn
                FROM {exam_table} er
                JOIN sp_user u ON u.id = CAST(er.user_id AS UNSIGNED)
                WHERE er.sop_id    = :sop_id
                  AND u.tenant_id  = :tenant_id
                  AND u.lang       = :data_lang
                  AND u.deleted_at IS NULL
            )
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY le.accumulated_score DESC, le.start_time ASC
                ) AS rank_num,
                CAST(le.user_id AS UNSIGNED) AS user_id,
                le.accumulated_score         AS score
            FROM latest_exam le
            WHERE le.rn = 1
            ORDER BY rank_num
        """)

        rows = self.db.execute(
            sql, {"sop_id": sop_id, "tenant_id": tenant_id, "data_lang": data_lang}
        ).fetchall()

        return [
            {
                "rank": row.rank_num,
                "user_id": int(row.user_id),
                "score": float(row.score) if row.score is not None else 0.0,
            }
            for row in rows
        ]

    def _get_existing_rank_map(self, sop_id: int, tenant_id: int, data_lang: str) -> Dict[int, int]:
        """
        读取当前排行榜表中该 SOP + 语种的排名映射。

        Returns:
            {user_id: rank} 字典；空字典表示尚无排行榜记录
        """
        rows = (
            self.db.query(SOPLeaderboard.user_id, SOPLeaderboard.rank)
            .filter(
                SOPLeaderboard.sop_id == sop_id,
                SOPLeaderboard.tenant_id == tenant_id,
                SOPLeaderboard.lang == data_lang,
            )
            .all()
        )
        return {row.user_id: row.rank for row in rows}
