# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import asyncio
from datetime import datetime, timedelta, date
from fastapi import Request, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from comps import opea_microservices, register_microservice, CustomLogger
from comps.account.auth import require_auth_dict
from comps.dashboard.config.base_config import SERVICE_NAME, DASHBOARD_HOST, DASHBOARD_PORT
from comps.dashboard.config.database import get_db
from comps.dashboard.models.schema import TriggerTaskRequest
from comps.dashboard.utils import (
    get_standard_period_range,
    get_standard_week_range,
    parse_date_param,
    validate_date_range
)
from comps.dashboard.service.sop_announcement_service import SOPAnnouncementService
from comps.dashboard.service.heatmap_service import HeatmapService
from comps.dashboard.service.ranking_service import RankingService
from comps.dashboard.service.leaderboard_service import LeaderboardService
from comps.dashboard.service.task_board_service import TaskBoardService
from comps.dashboard.service.statistics_service import StatisticsService
from comps.dashboard.service.resource_summary_service import ResourceSummaryService
from comps.dashboard.scheduler import start_scheduler, weekly_snapshot_task, daily_activity_snapshot_task

logger = CustomLogger("dashboard", os.getenv("LOG_LEVEL", "INFO"))


# ==================== API 接口 ====================

# 任务ID到可调用函数的映射
TASK_REGISTRY = {
    "daily_activity_snapshot": daily_activity_snapshot_task,
    "weekly_summary_snapshot": weekly_snapshot_task,
}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/overview",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"],
)
@require_auth_dict()
async def dashboard_overview(
    request: Request,
    start_date_str: str | None = Query(None, alias="start_date", description="起始日期 (YYYY-MM-DD)"),
    end_date_str: str | None = Query(None, alias="end_date", description="结束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user: dict = None
):
    """Dashboard 顶部统计总览接口"""
    try:
        # 1. 获取租户ID
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="无法获取租户信息")

        # 2. 解析和验证日期参数
        if start_date_str and end_date_str:
            # 同时提供 start_date 和 end_date
            start_date = parse_date_param(start_date_str)
            end_date = parse_date_param(end_date_str, is_end=True)
            # 验证是否为标准周
            if start_date.weekday() != 0 or ((end_date.date() - start_date.date()) != timedelta(days=6)):
                raise HTTPException(status_code=400, detail="查询范围不是标准周")

        elif start_date_str or end_date_str:
            # 只提供一个日期
            ref_date_str = start_date_str or end_date_str
            ref_date = parse_date_param(ref_date_str)
            start_date, end_date = get_standard_week_range(ref_date)
        else:
            # 不提供任何日期
            start_date, end_date = get_standard_week_range()

        # 执行通用验证
        validate_date_range(start_date, end_date)

        logger.info(
            f"查询统计数据 - 租户: {tenant_id}, 用户: {user.get('id')}, "
            f"当前周期: {start_date} ~ {end_date}"
        )

        # 3. 调用统计服务
        data_lang = user.get("lang", "zh")
        stats_service = StatisticsService(db, tenant_id, data_lang=data_lang)
        result = stats_service.get_statistics_with_comparison(start_date, end_date)

        # 4. 构建返回数据
        response_data = {
            "total_users": {"statistics_user_count": result['current']['total_users'], "compare_result": result['comparison']['total_users']},
            "active_users": {"statistics_active_users": result['current']['active_users'], "compare_result": result['comparison']['active_users']},
            "total_learn_seconds": {"statistics_learn_seconds": result['current']['total_learn_seconds'], "compare_result": result['comparison']['total_learn_seconds']},
            "avg_pass_rate": {"statistics_avg_pass_rate": result['current']['avg_pass_rate'], "compare_result": result['comparison']['avg_pass_rate']},
            "exam_count": {"statistics_exam_count": result['current']['exam_count'], "compare_result": result['comparison']['exam_count']}
        }
        return {"status": 200, "message": "查询成功", "data": response_data}
    except HTTPException as e:
        logger.error(f"Dashboard 查询失败: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Dashboard 查询异常: {str(e)}")
        return {"status": 500, "message": f"服务器错误: {str(e)}", "data": None}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/resource-summary",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"],
)
@require_auth_dict()
async def get_resource_summary(request: Request, db: Session = Depends(get_db), user: dict = None):
    """资源总览接口"""
    try:
        # 1. 获取租户ID
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="无法获取租户信息")

        # 2. 调用服务获取数据
        data_lang = user.get("lang", "zh")
        service = ResourceSummaryService(db, tenant_id, data_lang=data_lang)
        summary_data = service.get_summary()

        # 3. 构建返回数据
        return {"status": 200, "message": "查询成功", "data": [summary_data]}

    except HTTPException as e:
        logger.exception(f"资源总览查询失败: {e.detail}")
        return {"status": e.status_code, "message": f"资源总览查询失败", "data": None}
    except Exception as e:
        logger.exception(f"资源总览查询异常: {str(e)}")
        return {"status": 500, "message": f"服务器错误", "data": None}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/trigger-task",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["POST"],
)
async def trigger_scheduler_task(payload: TriggerTaskRequest):
    """手动触发一个或多个后台定时任务"""
    results = {}
    for task_id in payload.task_ids:
        if task_id not in TASK_REGISTRY:
            results[task_id] = "失败：任务ID不存在"
            # logger.warning(f"用户 {user.get('id')} 尝试触发一个不存在的任务: {task_id}")
            continue

        task_func = TASK_REGISTRY[task_id]
        task_params = payload.params.get(task_id, {}) if payload.params is not None else {}

        try:
            # 在后台线程中执行任务，避免阻塞API
            await asyncio.to_thread(task_func, **task_params)
            results[task_id] = "成功触发"
            logger.info(f"成功触发任务: {task_id}，参数: {task_params}")
        except Exception as e:
            error_message = f"执行失败: {str(e)}"
            results[task_id] = error_message
            logger.error(f"手动触发任务 {task_id} 失败: {error_message}")

    all_successful = all("成功" in res for res in results.values())
    status_code = 200 if all_successful else 400

    return {
        "status": status_code,
        "message": "任务触发完成，请查看详情",
        "data": results
    }


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/heatmap",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"],
)
@require_auth_dict()
async def heatmap(
    request: Request,
    mode: str = Query("days", description="查询模式：'days' (按天数推) 或 'month' (按自然月)"),
    month_str: str | None = Query(None, alias="month", description="查询月份 (YYYY-MM)，仅 mode='month' 时有效"),
    target_date_str: str | None = Query(None, alias="target_date", description="目标日期 (YYYY-MM-DD)，仅 mode='days' 时有效"),
    days: int = Query(30, description="往前推的天数，仅 mode='days' 时有效"),
    department_id: int | None = Query(None, description="部门ID"),
    db: Session = Depends(get_db),
    user: dict = None
):
    """查询用户会话热力图数据（支持按自然月或指定天数范围）"""
    try:
        # 1. 获取租户ID
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            return {"status": 400, "message": "无法获取租户信息", "data": None}

        service = HeatmapService(db, tenant_id, data_lang=user.get("lang", "zh"))

        # 2. 根据模式处理逻辑
        if mode == "month":
            # 兼容旧逻辑：按月查询
            if month_str:
                try:
                    target_month = datetime.strptime(month_str, "%Y-%m").date()
                except ValueError:
                    return {"status": 400, "message": "月份格式不正确，请使用 YYYY-MM"}
            else:
                target_month = date.today()
            
            heatmap_data = service.get_heatmap_by_month(target_month, department_id)

        elif mode == "days":
            # 新逻辑：指定日期前N天
            if target_date_str:
                try:
                    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                except ValueError:
                    return {"status": 400, "message": "日期格式不正确，请使用 YYYY-MM-DD"}
            else:
                target_date = date.today()
                
            heatmap_data = service.get_heatmap_by_days(target_date, days, department_id)
            
        else:
            return {"status": 400, "message": "mode 参数错误", "data": None}

        return {"status": 200, "message": "查询成功", "data": heatmap_data}
    except HTTPException as e:
        logger.exception(f"Heatmap 查询失败: {e.detail}")
        return {"status": e.status_code, "message": f"Heatmap 获取失败: {e.detail}", "data": None}
    except Exception as e:
        logger.exception(f"Heatmap 查询异常: {str(e)}")
        return {"status": 500, "message": f"服务器错误: {str(e)}", "data": None}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/department-exam",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"]
)
@require_auth_dict()
async def department_exam(
        request: Request,
        department_id: int | None = Query(None, description="部门ID"),
        db: Session = Depends(get_db),
        user: dict = None
):
    """
    部门完成度
    """
    return {
        "status": 200,
        "message": "查询成功",
        "data": {
            "summary": {
                "overall_completion_rate": 78.24,
                "completion_growth": 12.4,
                "active_sop_count": 156,
                "total_sop_count": 2324,
                "pending_count": 1156,
                "due_soon_count": 128
            },
            "list": [
                {
                    "task_id": 101,
                    "task_name": "【演示】制造业展会留存问题",
                    "health_score": 55,
                    "completion_rate": 97.5,
                    "pending_count": 55,
                    "completed_count": 58,
                    "status": "RUNNING",
                    "trend": [72, 80, 88, 92, 97]
                },
                {
                    "task_id": 102,
                    "task_name": "【演示】银行大堂经理问题",
                    "health_score": 33,
                    "completion_rate": 93.5,
                    "pending_count": 52,
                    "completed_count": 58,
                    "status": "RUNNING",
                    "trend": [60, 70, 82, 90, 93]
                },
                {
                    "task_id": 103,
                    "task_name": "银行大堂经理问题文字占位",
                    "health_score": 33,
                    "completion_rate": 91.5,
                    "pending_count": 50,
                    "completed_count": 58,
                    "status": "RUNNING",
                    "trend": [55, 65, 76, 85, 91]
                },
                {
                    "task_id": 104,
                    "task_name": "【演示】银行大堂经理问题",
                    "health_score": 33,
                    "completion_rate": 96.5,
                    "pending_count": 54,
                    "completed_count": 58,
                    "status": "RUNNING",
                    "trend": [70, 82, 90, 95, 96]
                },
                {
                    "task_id": 105,
                    "task_name": "【演示】银行大堂经理问题",
                    "health_score": 33,
                    "completion_rate": 72.5,
                    "pending_count": 24,
                    "completed_count": 58,
                    "status": "CLOSED",
                    "trend": [40, 55, 63, 68, 72]
                }
            ]
        }
    }


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/health",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"],
)
async def health_check():
    """健康检查接口"""
    return {"status": 200, "message": "Dashboard service is running", "timestamp": datetime.now().isoformat()}


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/announcements",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"],
)
@require_auth_dict()
async def get_announcements(
        request: Request,
        start_date: str | None = Query(None, description="新SOP的起始日期 (YYYY-MM-DD)，默认为7天前"),
        warning_window: int = Query(7, description="到期预警窗口（天数），默认为7天"),
        db: Session = Depends(get_db),
        user: dict = None
):
    """
    Dashboard 公告数据展示接口
    
    用于展示 SOP 相关的公告信息，包括：
    - 新增的 SOP（在指定日期之后生效）
    - 即将到期的 SOP（在预警窗口内到期）
    
    查询参数：
        - start_date: 新SOP的起始日期 (YYYY-MM-DD)，可选，默认为7天前
        - warning_window: 到期预警窗口（天数），可选，默认为7天
    
    返回格式：
    {
        "status": 200,
        "message": "查询成功",
        "data": {
            "new": [
                {
                    "id": 1,
                    "title": "安全生产SOP",
                    "start_time": "2026-03-01",
                    "end_time": "2026-12-31",
                    "position_id": "101",
                    "sop_version": "v1.0"
                }
            ],
            "expiring": [
                {
                    "id": 2,
                    "title": "末班车SOP",
                    "start_time": "2025-01-01",
                    "end_time": "2026-03-10",
                    "days_left": 4,
                    "time_left": 4,
                    "time_left_unit": "day",
                    "position_id": "102",
                    "sop_version": "v2.1"
                }
            ],
            "summary": {
                "new_count": 1,
                "expiring_count": 1,
                "query_date": "2026-03-06"
            }
        }
    }
    """
    try:
        # 1. 获取租户ID
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="无法获取租户信息")

        # 2. 初始化服务并查询数据
        sop_service = SOPAnnouncementService(db, tenant_id, data_lang=user.get("lang", "zh"))
        announcements = sop_service.get_announcements(
            start_date=start_date,
            warning_window=warning_window
        )

        # 4. 返回结果
        logger.info(f"租户 {tenant_id} 查询公告成功: 新增 {announcements['summary']['new_count']} 个, "
                   f"即将到期 {announcements['summary']['expiring_count']} 个")

        return {
            "status": 200,
            "message": "查询成功",
            "data": announcements
        }

    except ValueError as e:
        logger.error(f"参数错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"参数错误: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询公告失败: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/sops",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"],
)
@require_auth_dict()
async def get_sops(
        request: Request,
        keyword: str | None = Query(None, description="SOP 名称关键词模糊匹配"),
        department_id: int | None = Query(None, description="部门ID，筛选该部门相关的 SOP"),
        start_time: str | None = Query(None, description="筛选 SOP 起始时间 (YYYY-MM-DD)"),
        end_time: str | None = Query(None, description="筛选 SOP 结束时间 (YYYY-MM-DD)"),
        db: Session = Depends(get_db),
        user: dict = None
):
    """
    SOP 列表查询接口

    支持按关键词、部门、时间范围筛选 SOP 列表。

    查询参数：
        - keyword: SOP 名称关键词模糊匹配，可选
        - department_id: 部门ID，筛选该部门相关的 SOP，可选
        - start_time: 筛选 SOP 起始时间 (YYYY-MM-DD)，可选
        - end_time: 筛选 SOP 结束时间 (YYYY-MM-DD)，可选

    返回格式：
    {
        "status": 200,
        "message": "查询成功",
        "data": [
            {"sop_id": 1, "sop_title": "年度英语能力测验"},
            {"sop_id": 2, "sop_title": "季度客户管理考试"}
        ]
    }
    """
    try:
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="无法获取租户信息")

        service = RankingService(db, tenant_id, data_lang=user.get("lang", "zh"))
        result = service.get_sop_list(
            keyword=keyword,
            department_id=department_id,
            start_time=start_time,
            end_time=end_time
        )

        logger.info(f"租户 {tenant_id} 查询 SOP 列表成功，共 {len(result)} 条")
        return {
            "status": 200,
            "message": "查询成功",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询 SOP 列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/task-board",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["GET"],
)
@require_auth_dict()
async def get_task_board(
        request: Request,
        period: str = Query("week", description="周期类型 week / month / quarter"),
        start_date_param: str | None = Query(None, alias="start_date", description="已废弃，请勿使用"),
        end_date_param: str | None = Query(None, alias="end_date", description="已废弃，请勿使用"),
        ref_date_param: str | None = Query(None, alias="ref_date", description="已废弃，请勿使用"),
        db: Session = Depends(get_db),
        user: dict = None
):
    """
    学习任务看板接口

    查询参数：
        - period: 周期类型 week / month / quarter，可选，默认 week

    说明：
        - 仅按 period 对应的标准周期查询
        - 未提供 period 时默认按 week 查询
        - 不再支持 start_date、end_date、ref_date 参数
    """
    try:
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="无法获取租户信息")

        if start_date_param or end_date_param or ref_date_param:
            raise HTTPException(
                status_code=400,
                detail="任务看板接口仅支持 period 参数，不再支持 start_date、end_date、ref_date",
            )

        start_date, end_date = get_standard_period_range(period)

        validate_date_range(start_date, end_date)

        service = TaskBoardService(db, tenant_id, data_lang=user.get("lang", "zh"))
        result = service.get_task_board(start_date, end_date)

        logger.info(
            f"任务看板查询成功 - 租户: {tenant_id}, 用户: {user.get('id')}, "
            f"时间范围: {start_date.date()} ~ {end_date.date()}, 任务数: {len(result['list'])}"
        )

        return {
            "status": 200,
            "message": "查询成功",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"任务看板查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/ranking",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["POST"],
)
@require_auth_dict()
async def get_ranking(
        request: Request,
        db: Session = Depends(get_db),
        user: dict = None
):
    """
    成绩排行接口

    根据 sop_id 返回该 SOP 的考试信息和用户成绩排行。

    请求体：
        {
            "sop_id": 1
        }

    返回格式：
    {
        "status": 200,
        "message": "查询成功",
        "data": {
            "exam_info": {
                "sop_id": 1,
                "sop_title": "年度英语能力测验",
                "department": "销售部",
                "start_time": "2023-01-01",
                "end_time": "2023-01-31",
                "total_participants": 100,
                "completed_participants": 80,
                "completion_rate": 80.0
            },
            "ranking": [
                {"rank": 1, "user_id": 101, "user_name": "张三", "department": "销售部", "score": 98.5, "rank_change": 2}
            ],
            "count": 6
        }
    }
    """
    try:
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="无法获取租户信息")

        body = await request.json()
        sop_id = body.get("sop_id")

        if sop_id is None or not isinstance(sop_id, int):
            raise HTTPException(status_code=400, detail="sop_id 参数缺失或格式错误")

        service = RankingService(db, tenant_id, data_lang=user.get("lang", "zh"))
        result = service.get_ranking(sop_id)

        logger.info(f"租户 {tenant_id} 查询 SOP {sop_id} 成绩排行成功")
        return {
            "status": 200,
            "message": "查询成功",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询成绩排行失败: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@register_microservice(
    name=SERVICE_NAME,
    endpoint="/api/dashboard/leaderboard/recalculate",
    host=DASHBOARD_HOST,
    port=DASHBOARD_PORT,
    methods=["POST"],
)
async def recalculate_leaderboard(
        request: Request,
        db: Session = Depends(get_db)
):
    """
    触发排行榜重算接口

    由其他服务在考试结束后调用，重新计算指定 SOP 的排行榜并写入 sp_sop_leaderboard。

    请求体：
        {
            "sop_id": 1,
            "tenant_id": 123
        }

    返回格式：
    {
        "status": 200,
        "message": "排行榜重算成功",
        "data": {
            "sop_id": 1,
            "affected_rows": 20
        }
    }
    """
    try:

        body = await request.json()
        sop_id = body.get("sop_id")
        tenant_id = body.get("tenant_id")
        data_lang = body.get("data_lang", "zh")

        if sop_id is None or not isinstance(sop_id, int):
            raise HTTPException(status_code=400, detail="sop_id 参数缺失或格式错误")
        if tenant_id is None or not isinstance(tenant_id, int):
            raise HTTPException(status_code=400, detail="tenant_id 参数缺失或格式错误")
        if not isinstance(data_lang, str):
            raise HTTPException(status_code=400, detail="data_lang 参数格式错误")

        service = LeaderboardService(db)
        affected = service.update_leaderboard(sop_id, tenant_id, data_lang=data_lang)

        logger.info(
            f"租户 {tenant_id}/{data_lang} 触发 SOP {sop_id} 排行榜重算，影响 {affected} 条记录"
        )
        return {
            "status": 200,
            "message": "排行榜重算成功",
            "data": {
                "sop_id": sop_id,
                "data_lang": data_lang,
                "affected_rows": affected
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"排行榜重算失败: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


# ==================== 启动服务 ====================

if __name__ == "__main__":
    # 启动后台定时任务调度器
    start_scheduler()

    logger.info(f"启动 Dashboard 服务 - Host: {DASHBOARD_HOST}, Port: {DASHBOARD_PORT}")
    opea_microservices[SERVICE_NAME].start()
