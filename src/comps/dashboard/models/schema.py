# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, Field
from typing import Optional, Any, List


class DashboardQueryParams(BaseModel):
    """Dashboard 查询参数"""
    start_date: Optional[str] = Field(None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="结束日期 (YYYY-MM-DD)")
    period_type: Optional[str] = Field("week", description="对比周期类型 (day/week/month)")

class TotalUsersStat(BaseModel):
    statistics_user_count: int
    compare_result: str = ""

class ActiveUsersStat(BaseModel):
    statistics_active_users: int
    compare_result: str = ""

class TotalLearnSecondsStat(BaseModel):
    statistics_learn_seconds: int
    compare_result: str = ""

class AvgPassRateStat(BaseModel):
    statistics_avg_pass_rate: float
    compare_result: str = ""

class ExamCountStat(BaseModel):
    statistics_exam_count: int
    compare_result: str = ""


class DashboardOverviewData(BaseModel):
    """Dashboard 总览数据"""
    total_users: TotalUsersStat = Field(..., description="总用户量")
    active_users: ActiveUsersStat = Field(..., description="活跃用户")
    total_learn_seconds: TotalLearnSecondsStat = Field(..., description="总学习时长")
    avg_pass_rate: AvgPassRateStat = Field(..., description="平均达标率")
    exam_count: ExamCountStat = Field(..., description="考试场次")


class DashboardResponse(BaseModel):
    """Dashboard API 响应"""
    status: int
    message: str
    data: Optional[DashboardOverviewData] = None


class HeartbeatResponse(BaseModel):
    """心跳响应"""
    status: int
    message: str


class RankingRequest(BaseModel):
    """成绩排行请求参数"""
    sop_id: int = Field(..., description="SOP ID")


class SOPListItem(BaseModel):
    """SOP 列表项"""
    sop_id: int = Field(..., description="SOP ID")
    sop_title: str = Field(..., description="SOP 标题")


class ExamInfoData(BaseModel):
    """考试信息数据"""
    sop_id: int = Field(..., description="SOP ID")
    sop_title: str = Field("", description="SOP 标题")
    department: str = Field("", description="所属部门")
    start_time: Optional[str] = Field(None, description="开始时间")
    end_time: Optional[str] = Field(None, description="结束时间")
    total_participants: int = Field(0, description="应考人数")
    completed_participants: int = Field(0, description="已完成考试人数")
    completion_rate: float = Field(0.0, description="完成率")


class RankingUserItem(BaseModel):
    """排行榜用户项"""
    rank: int = Field(..., description="排名")
    user_id: int = Field(..., description="用户ID")
    user_name: str = Field("", description="用户姓名")
    department: str = Field("", description="所属部门")
    score: float = Field(0.0, description="考试得分")
    rank_change: int = Field(0, description="排名变化")


class TaskBoardItem(BaseModel):
    """任务看板列表项"""
    task_id: int = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    task_type: str = Field(..., description="任务类型（video/sop）")
    participant_count: int = Field(0, description="实参人数")
    should_participant_count: int = Field(0, description="应参人数")
    study_duration: float = Field(0.0, description="学习时长（小时）")
    health_status: float = Field(0.0, description="健康值")


class TaskBoardData(BaseModel):
    """任务看板数据"""
    list: List[TaskBoardItem] = Field(default_factory=list, description="任务列表")


class TaskBoardResponse(BaseModel):
    """任务看板响应"""
    status: int
    message: str
    data: TaskBoardData


class TriggerTaskRequest(BaseModel):
    task_ids: list[str] = Field(..., description="要触发的任务ID列表")
    params: dict[str, Any] | None = Field(None, description="传递给任务的可选参数")
