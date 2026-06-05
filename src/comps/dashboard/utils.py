# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime, timedelta
from fastapi import HTTPException
from typing import Tuple


# =============================================================================
# 业务语种解析与表名路由
# =============================================================================
#
# Dashboard 多语种改造统一约定：
#   - zh 复用原表（无后缀）
#   - en / th 走后缀表
#   - 非法/缺失 lang 一律降级 zh
#   - 动态表名只能来自本文件 helper，禁止直接拼接前端参数
# =============================================================================

SUPPORTED_LANGS = {"zh", "en", "th"}
DEFAULT_LANG = "zh"


def resolve_lang(lang: str | None) -> str:
    """解析业务语种，非法或缺失降级为 zh。"""
    if not lang:
        return DEFAULT_LANG
    normalized = str(lang).strip().lower()
    return normalized if normalized in SUPPORTED_LANGS else DEFAULT_LANG


def table_name(base: str, lang: str | None) -> str:
    """按业务语种路由业务表名（zh 复用原表，其它语种使用后缀表）。"""
    normalized = resolve_lang(lang)
    return base if normalized == DEFAULT_LANG else f"{base}_{normalized}"


def sop_info_table(lang: str | None) -> str:
    return table_name("sp_sop_info", lang)


def exam_record_table(lang: str | None) -> str:
    return table_name("sp_exam_record", lang)


def course_table(lang: str | None) -> str:
    return table_name("sp_course", lang)


def material_table(lang: str | None) -> str:
    return table_name("sp_material", lang)


def learning_record_table(lang: str | None) -> str:
    return table_name("sp_learning_record", lang)


def company_table(lang: str | None) -> str:
    return table_name("sp_company", lang)


def department_table(lang: str | None) -> str:
    return table_name("sp_department", lang)


def position_table(lang: str | None) -> str:
    return table_name("sp_position", lang)


def milvus_collection_name(base_collection: str, lang: str | None) -> str:
    """按业务语种路由 Milvus 集合名（zh 复用原集合，其它语种走后缀集合）。"""
    normalized = resolve_lang(lang)
    return base_collection if normalized == DEFAULT_LANG else f"{base_collection}_{normalized}"


# =============================================================================
# 时间范围工具
# =============================================================================


def get_standard_month_range(date: datetime | None = None) -> Tuple[datetime, datetime]:
    """
    获取标准月的开始和结束日期

    Args:
        date: 参考日期，默认为当前日期

    Returns:
        (month_start, month_end): 月的开始和结束时间
    """
    if date is None:
        date = datetime.now()

    # 月初
    month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 下个月的第一天减一秒
    if date.month == 12:
        next_month = month_start.replace(year=date.year + 1, month=1)
    else:
        next_month = month_start.replace(month=date.month + 1)

    month_end = next_month - timedelta(microseconds=1)

    return month_start, month_end

def get_standard_week_range(date: datetime | None = None) -> Tuple[datetime, datetime]:
    """
    获取标准周的开始和结束日期（周一00:00:00 到周日23:59:59）

    Args:
        date: 参考日期，默认为当前日期

    Returns:
        (week_start, week_end): 周的开始和结束时间
    """
    if date is None:
        date = datetime.now()

    # 获取当前日期是星期几（0=周一，6=周日）
    weekday = date.weekday()

    # 计算周一
    week_start = date - timedelta(days=weekday)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # 计算周日
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)

    return week_start, week_end

def get_previous_week_range(reference_date: datetime= None) -> Tuple[datetime, datetime]:
    """
    获取上一周的标准周范围（周一 00:00:00 到周日 23:59:59）

    Args:
        reference_date: 参考日期，默认为当前日期

    Returns:
        (previous_start, previous_end): 上一周的开始和结束时间
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 先获取本周一
    current_start, _ = get_standard_week_range(reference_date)

    # 上周一是本周一减去 7 天
    previous_start = current_start - timedelta(days=7)
    previous_end = previous_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)

    return previous_start, previous_end


def get_standard_quarter_range(date: datetime | None = None) -> Tuple[datetime, datetime]:
    """
    获取标准季度的开始和结束日期

    Args:
        date: 参考日期，默认为当前日期

    Returns:
        (quarter_start, quarter_end): 季度的开始和结束时间
    """
    if date is None:
        date = datetime.now()

    quarter = (date.month - 1) // 3
    start_month = quarter * 3 + 1

    quarter_start = date.replace(
        month=start_month,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if start_month == 10:
        next_quarter_start = quarter_start.replace(year=date.year + 1, month=1)
    else:
        next_quarter_start = quarter_start.replace(month=start_month + 3)

    quarter_end = next_quarter_start - timedelta(microseconds=1)
    return quarter_start, quarter_end


def get_standard_period_range(
        period: str = "week",
        date: datetime | None = None,
) -> Tuple[datetime, datetime]:
    """
    根据周期标识获取标准时间范围

    Args:
        period: 周期类型，支持 week / month / quarter
        date: 参考日期，默认为当前日期

    Returns:
        对应周期的开始和结束时间

    Raises:
        HTTPException: 周期类型不支持时抛出
    """
    normalized_period = (period or "week").strip().lower()

    if normalized_period == "week":
        return get_standard_week_range(date)

    if normalized_period == "month":
        return get_standard_month_range(date)

    if normalized_period == "quarter":
        return get_standard_quarter_range(date)

    raise HTTPException(
        status_code=400,
        detail="period 参数仅支持 week、month、quarter",
    )


def parse_date_param(date_str: str, is_end: bool = False) -> datetime:
    """
    解析日期参数字符串

    Args:
        date_str: 日期字符串，格式 YYYY-MM-DD
        is_end: 是否为结束日期（如果是，设置为当天23:59:59）

    Returns:
        解析后的datetime对象

    Raises:
        HTTPException: 日期格式错误时抛出
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if is_end:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return dt
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"日期格式错误: {date_str}，应为 YYYY-MM-DD"
        )


def validate_date_range(start_date: datetime, end_date: datetime):
    """
    验证日期范围的有效性

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Raises:
        HTTPException: 日期范围无效时抛出
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="开始日期不能晚于结束日期"
        )


def format_compare_result(current_value: float, previous_value: float,
                          is_percentage: bool = False) -> str:
    """
    格式化对比结果

    Args:
        current_value: 当前值
        previous_value: 前一个值
        is_percentage: 是否为百分比类型

    Returns:
        格式化的对比字符串，如 "+322" 或 "-10" 或 "+2.35"
    """
    diff = current_value - previous_value

    if diff == 0:
        return ""

    if is_percentage:
        return f"{diff:+.2f}"
    else:
        return f"{int(diff):+d}"


def get_previous_period_range(current_start: datetime, current_end: datetime) -> Tuple[datetime, datetime]:
    """
    计算前一周期的开始和结束时间
    """
    previous_end = current_start - timedelta(seconds=1)
    previous_start = previous_end - (current_end - current_start)
    previous_start = previous_start.replace(hour=0, minute=0, second=0, microsecond=0)
    return previous_start, previous_end


def get_client_ip(request) -> str:
    """
    获取客户端真实IP地址

    Args:
        request: FastAPI Request对象

    Returns:
        IP地址字符串
    """
    # 优先从 X-Forwarded-For 获取（代理情况）
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # 从 X-Real-IP 获取
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # 直接连接的IP
    return request.client.host if request.client else "unknown"


def get_user_agent(request) -> str:
    """
    获取用户浏览器标识

    Args:
        request: FastAPI Request对象

    Returns:
        User-Agent字符串
    """
    return request.headers.get("User-Agent", "unknown")[:512]  # 限制长度
