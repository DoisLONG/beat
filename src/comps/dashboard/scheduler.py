# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import atexit
from datetime import datetime, timedelta, date
from sqlalchemy import func, distinct
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from comps import CustomLogger
from comps.dashboard.config.database import SessionLocal
from comps.dashboard.config.base_config import (
    CRON_WEEKLY_DAY_OF_WEEK, CRON_WEEKLY_HOUR, CRON_WEEKLY_MINUTE,
    CRON_DAILY_HOUR, CRON_DAILY_MINUTE
)
from comps.dashboard.service.statistics_service import StatisticsService
from comps.dashboard.models.model import Tenant, User, UserSession, UserActivity
from comps.dashboard.utils import SUPPORTED_LANGS

logger = CustomLogger("dashboard_scheduler", os.getenv("LOG_LEVEL", "INFO"))

# 初始化全局调度器
scheduler = BackgroundScheduler()


def get_all_tenant_ids() -> list[int]:
    """获取系统中所有活跃的租户ID"""
    db = SessionLocal()
    try:
        # 从 sp_tenant 表获取所有启用的、未过期的租户
        now = datetime.now()
        tenants = db.query(Tenant.tenant_id).filter(
            Tenant.status == 1,
            (Tenant.expire_time.is_(None) | (Tenant.expire_time > now))
        ).all()
        logger.info(f"查询到 {len(tenants)} 个活跃租户")
        return [t[0] for t in tenants]
    except Exception as e:
        logger.error(f"获取活跃租户列表失败: {str(e)}")
        return []
    finally:
        db.close()


def daily_activity_snapshot_task(target_date_str: str | None = None):
    """
    每日定时任务：计算并持久化前一天的日活跃用户数 (DAU)
    Args:
        target_date_str: 可选，指定计算哪一天的日活，格式 YYYY-MM-DD。
                         如果不提供，则自动计算昨天。
    """
    logger.info("开始执行每日用户活动快照任务...")
    db = SessionLocal()
    try:
        # 1. 确定目标日期
        if target_date_str:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        else:
            target_date = date.today() - timedelta(days=1)

        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())

        logger.info(f"将为所有租户生成日活快照，目标日期: {target_date}")

        # 2. 查询前一天所有活跃的用户会话，按 (tenant_id, lang) 分组
        # 活跃定义：会话的 [login_time, last_active_time] 与目标日期有重叠
        # lang 取自 sp_user.lang，缺失时回落 'zh'
        active_sessions = (
            db.query(
                UserSession.tenant_id,
                func.coalesce(User.lang, "zh").label("lang"),
                func.count(distinct(UserSession.user_id)).label("dau")
            )
            .join(User, User.id == UserSession.user_id)
            .filter(
                UserSession.login_time <= day_end,
                UserSession.last_active_time >= day_start
            )
            .group_by(UserSession.tenant_id, func.coalesce(User.lang, "zh"))
            .all()
        )

        if not active_sessions:
            logger.info("在指定日期内未找到任何用户活动。")
            return

        # 3. 保存或更新统计结果到 sp_user_activity 表 (按 tenant_id + lang + stat_date)
        for session in active_sessions:
            tenant_id = session.tenant_id
            lang = session.lang or "zh"
            dau_count = session.dau

            # 检查记录是否已存在
            existing_activity = db.query(UserActivity).filter(
                UserActivity.tenant_id == tenant_id,
                UserActivity.lang == lang,
                UserActivity.stat_date == target_date
            ).first()

            if existing_activity:
                # 如果存在，则更新
                existing_activity.active_users = dau_count
                logger.info(f"更新租户 {tenant_id}/{lang} 在 {target_date} 的日活为: {dau_count}")
            else:
                # 如果不存在，则创建
                new_activity = UserActivity(
                    tenant_id=tenant_id,
                    lang=lang,
                    stat_date=target_date,
                    active_users=dau_count
                )
                db.add(new_activity)
                logger.info(f"创建租户 {tenant_id}/{lang} 在 {target_date} 的日活为: {dau_count}")
        
        db.commit()
        logger.info(f"每日用户活动快照任务成功完成，共处理 {len(active_sessions)} 个租户。")

    except Exception as e:
        logger.error(f"执行每日用户活动快照任务失败: {str(e)}")
        db.rollback()
    finally:
        db.close()


def generate_and_save_snapshot(
    tenant_id: int,
    period_type: str,
    start_date: datetime,
    end_date: datetime,
    data_lang: str = "zh",
):
    """为指定租户 + 语种生成并保存特定周期的统计快照"""
    db = SessionLocal()
    try:
        service = StatisticsService(db, tenant_id, data_lang=data_lang)

        # 获取截至该周期结束时的数据
        stats = {
            'total_users': service.calculate_total_users(as_of_date=end_date),
            'active_users': service.calculate_active_users(start_date=start_date, end_date=end_date),
            'total_learn_seconds': service.calculate_total_learn_seconds(start_date, end_date),
            'avg_pass_rate': service.calculate_avg_pass_rate(start_date, end_date),
            'exam_count': service.calculate_exam_count(start_date, end_date)
        }

        # 保存快照
        service.save_statistics_snapshot(
            period_type=period_type,
            period_start=start_date,
            period_end=end_date,
            stats=stats
        )
        logger.info(
            f"成功保存租户 {tenant_id}/{data_lang} 的 {period_type} 维度统计快照: "
            f"{start_date.date()} ~ {end_date.date()}"
        )
    except Exception as e:
        logger.error(f"保存租户 {tenant_id}/{data_lang} 快照失败: {str(e)}")
        db.rollback()
    finally:
        db.close()


def weekly_snapshot_task(week_start: str | None = None):
    """每周定时任务：计算并持久化上周的统计数据 (默认周一凌晨执行)
    Args:
        week_start: 可选，指定任意一天的日期，格式 YYYY-MM-DD， 计算所属周的上一周
                   如果不提供，使用当前日期自动计算上一周

    示例：
        - week_start="2026-03-10" (周二) -> 计算 2026-03-02(周一) ~ 2026-03-08(周日)
        - week_start="2026-03-07" (周六) -> 计算 2026-02-23(周一) ~ 2026-03-01(周日)
    """
    logger.info("开始执行每周统计快照任务...")

    # 1. 确定参考日期
    if week_start:
        try:
            ref_date = datetime.strptime(week_start, "%Y-%m-%d")
        except ValueError:
            logger.error(f"无效的日期格式: {week_start}. 请使用 YYYY-MM-DD.")
            return
    else:
        ref_date = datetime.now()

    # 2. 计算目标周的开始和结束日期
    # 首先找到参考日期所在周的周一 (weekday: Monday is 0 and Sunday is 6)
    monday_of_ref_week = ref_date - timedelta(days=ref_date.weekday())
    # 目标是计算上一周，所以再往前推7天找到上周一
    start_of_last_week = monday_of_ref_week - timedelta(days=7)
    # 上周日是上周一 + 6天
    end_of_last_week = start_of_last_week + timedelta(days=6)

    # 3. 设置完整的时间范围
    start_date = start_of_last_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_of_last_week.replace(hour=23, minute=59, second=59, microsecond=999999)

    logger.info(f"将为所有租户生成统计快照，时间范围: {start_date.date()} ~ {end_date.date()}")

    tenant_ids = get_all_tenant_ids()
    if not tenant_ids:
        logger.warning("未找到任何活跃的租户，任务结束。")
        return

    for tid in tenant_ids:
        for lang in SUPPORTED_LANGS:
            generate_and_save_snapshot(tid, "week", start_date, end_date, data_lang=lang)

    logger.info("每周统计快照任务执行完毕。")


def start_scheduler():
    """启动所有定时任务"""
    # 每日定时任务：统计前一天的日活用户
    scheduler.add_job(
        daily_activity_snapshot_task,
        CronTrigger(hour=CRON_DAILY_HOUR, minute=CRON_DAILY_MINUTE),
        id="daily_activity_snapshot",
        replace_existing=True
    )

    # 每周定时任务：统计上一周的整体数据
    scheduler.add_job(
        weekly_snapshot_task,
        CronTrigger(day_of_week=CRON_WEEKLY_DAY_OF_WEEK, hour=CRON_WEEKLY_HOUR, minute=CRON_WEEKLY_MINUTE),
        id="weekly_summary_snapshot",
        replace_existing=True
    )

    scheduler.start()
    logger.info("后台定时统计任务调度器已启动，配置已从环境变量加载")

    # 确保退出时关闭调度器
    atexit.register(lambda: scheduler.shutdown())
