# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from comps import CustomLogger
from comps.account.config import SESSION_TIMEOUT
from comps.account.model import User, get_user_session_model

logger = CustomLogger("account_session", "INFO")


class SessionService:
    """会话管理服务类"""

    def __init__(self, db: Session, lang: str = "zh"):
        """
        初始化会话服务

        Args:
            db: 数据库会话
            lang: 业务语种（zh/en/th），决定路由到哪张 sp_user_session_* 表
        """
        self.db = db
        self._model = get_user_session_model(lang)

    def get_or_create_session(
            self,
            user_id: int,
            tenant_id: int,
            ip_address: str | None = None,
            user_agent: str | None = None
    ):
        """
        获取或创建用户会话

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            ip_address: 客户端IP地址
            user_agent: 浏览器标识

        Returns:
            UserSession对象
        """
        m = self._model
        try:
            # 查找最近的未登出会话
            current_session = self.db.query(m).filter(
                m.user_id == user_id,
                m.tenant_id == tenant_id,
                m.logout_time.is_(None)
            ).order_by(m.login_time.desc()).first()

            now = datetime.now()

            # 如果存在活跃会话且未超时，返回该会话
            if current_session:
                time_since_active = (now - current_session.last_active_time).total_seconds()
                if time_since_active <= SESSION_TIMEOUT:
                    return current_session
                else:
                    # 会话超时，自动登出
                    current_session.logout_time = current_session.last_active_time
                    self.db.commit()
                    logger.info(f"会话 {current_session.session_id} 已超时自动登出")

            # 创建新会话
            new_session = m(
                session_id=str(uuid.uuid4()),
                user_id=user_id,
                tenant_id=tenant_id,
                login_time=now,
                last_active_time=now,
                ip_address=ip_address,
                user_agent=user_agent
            )

            self.db.add(new_session)
            self.db.commit()
            self.db.refresh(new_session)

            logger.info(
                f"创建新会话 - 用户: {user_id}, 租户: {tenant_id}, "
                f"会话ID: {new_session.session_id}"
            )

            return new_session
        except Exception as e:
            logger.error(f"获取或创建会话失败: {str(e)}")
            self.db.rollback()
            raise

    def update_heartbeat(
            self,
            user_id: int,
            tenant_id: int
    ) -> bool:
        """
        更新用户心跳（最后活跃时间）

        Args:
            user_id: 用户ID
            tenant_id: 租户ID

        Returns:
            是否更新成功
        """
        m = self._model
        try:
            current_session = self.db.query(m).filter(
                m.user_id == user_id,
                m.tenant_id == tenant_id,
                m.logout_time.is_(None)
            ).order_by(m.login_time.desc()).first()

            now = datetime.now()

            if current_session:
                current_session.last_active_time = now
                current_session.updated_at = now
                self.db.commit()
                logger.debug(f"更新用户 {user_id} 心跳时间: {now}")
                return True
            else:
                logger.warning(f"用户 {user_id} 没有活跃会话，无法更新心跳")
                return False
        except Exception as e:
            logger.error(f"更新心跳失败: {str(e)}")
            self.db.rollback()
            return False

    def logout_user(
            self,
            user_id: int,
            tenant_id: int
    ) -> int:
        """
        用户登出，关闭所有活跃会话

        Args:
            user_id: 用户ID
            tenant_id: 租户ID

        Returns:
            关闭的会话数量
        """
        m = self._model
        try:
            active_sessions = self.db.query(m).filter(
                m.user_id == user_id,
                m.tenant_id == tenant_id,
                m.logout_time.is_(None)
            ).all()

            now = datetime.now()
            count = 0

            for session in active_sessions:
                session.logout_time = now
                session.updated_at = now
                count += 1

            self.db.commit()

            logger.info(f"用户 {user_id} 登出，关闭 {count} 个会话")
            return count
        except Exception as e:
            logger.error(f"用户登出失败: {str(e)}")
            self.db.rollback()
            return 0

    def cleanup_expired_sessions(self, days: int = 30):
        """
        清理过期会话记录

        Args:
            days: 保留最近N天的记录，默认30天
        """
        m = self._model
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            deleted_count = self.db.query(m).filter(
                m.created_at < cutoff_date
            ).delete()

            self.db.commit()

            logger.info(f"清理过期会话记录: {deleted_count} 条")
            return deleted_count
        except Exception as e:
            logger.error(f"清理过期会话失败: {str(e)}")
            self.db.rollback()
            return 0

    def get_user_online_duration(
            self,
            user_id: int,
            tenant_id: int,
            start_date: datetime = None,
            end_date: datetime = None
    ) -> int:
        """
        获取用户在指定时间范围内的总在线时长（秒）

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            总在线时长（秒）
        """
        m = self._model
        try:
            from sqlalchemy import func, text

            query = self.db.query(
                func.sum(
                    func.timestampdiff(
                        text("SECOND"),
                        m.login_time,
                        func.coalesce(m.last_active_time, m.login_time)
                    )
                )
            ).filter(
                m.user_id == user_id,
                m.tenant_id == tenant_id
            )

            if start_date:
                query = query.filter(m.login_time >= start_date)
            if end_date:
                query = query.filter(m.login_time <= end_date)

            total_seconds = query.scalar() or 0

            logger.info(f"用户 {user_id} 总在线时长: {total_seconds}秒")
            return total_seconds
        except Exception as e:
            logger.error(f"获取用户在线时长失败: {str(e)}")
            return 0

    def get_user_statistics(
            self,
            tenant_id: int | None = None,
            days: int = 7,
            min_online_minutes: int = 30
    ) -> dict:
        """
        获取活跃用户数和总用户数

        活跃用户定义：近N天累计在线时长 >= min_online_minutes 分钟

        Args:
            tenant_id: 租户ID，None 表示统计全部租户
            days: 统计近N天，默认7天
            min_online_minutes: 活跃阈值（分钟），默认30分钟

        Returns:
            {"total_users": int, "active_users": int, "active_rate": float}
        """
        m = self._model
        try:
            from sqlalchemy import func, text

            # 1. 查询总用户数（sp_user 不分表）
            total_query = self.db.query(func.count(User.id)).filter(
                User.is_active == True,
                User.deleted_at.is_(None)
            )
            if tenant_id is not None:
                total_query = total_query.filter(User.tenant_id == tenant_id)
            total_users = total_query.scalar() or 0

            # 2. 查询活跃用户数（近N天在线 >= min_online_minutes 分钟）
            cutoff_date = datetime.now() - timedelta(days=days)
            min_seconds = min_online_minutes * 60

            subquery = self.db.query(
                m.user_id.label("user_id"),
                func.sum(
                    func.timestampdiff(
                        text("SECOND"),
                        m.login_time,
                        func.coalesce(m.last_active_time, m.login_time)
                    )
                ).label("total_seconds")
            ).filter(
                m.login_time >= cutoff_date
            )
            if tenant_id is not None:
                subquery = subquery.filter(m.tenant_id == tenant_id)
            subquery = subquery.group_by(m.user_id).subquery()

            active_users = self.db.query(func.count()).select_from(subquery).filter(
                subquery.c.total_seconds >= min_seconds
            ).scalar() or 0

            # 3. 计算活跃率
            active_rate = round(active_users / total_users, 2) if total_users > 0 else 0.0

            logger.info(
                f"用户统计 - 租户: {tenant_id or '全部'}, "
                f"总用户: {total_users}, 活跃用户: {active_users}, 活跃率: {active_rate}"
            )

            return {
                "total_users": total_users,
                "active_users": active_users,
                "active_rate": active_rate
            }
        except Exception as e:
            logger.error(f"获取用户统计失败: {str(e)}")
            raise
