# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Date, Float, Boolean, UniqueConstraint, Text
from enum import Enum
from sqlalchemy.sql import func

from comps.dashboard.config.database import Base


class UserRole(int, Enum):
    OWNER = 1
    ADMIN = 2
    USER = 3

    @staticmethod
    def is_valid_role(role: int) -> bool:
        if not role:
            return False
        return role in (
            UserRole.OWNER,
            UserRole.ADMIN,
            UserRole.USER,
        )

    @staticmethod
    def is_owner(role: int) -> bool:
        if not role:
            return False
        return role == UserRole.OWNER

    @staticmethod
    def is_admin(role: int) -> bool:
        if not role:
            return False
        return role in (UserRole.OWNER, UserRole.ADMIN)

    @staticmethod
    def is_grantable_role(role: int) -> bool:
        if not role:
            return False
        return role in (UserRole.ADMIN, UserRole.USER)



class DashboardStatistics(Base):
    """Dashboard 统计快照表 - 用于存储历史统计数据，便于快速对比"""
    __tablename__ = "sp_dashboard_statistics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    lang = Column(String(8), nullable=False, default="zh", index=True, comment='业务语种（zh/en/th）')
    period_type = Column(String(20), nullable=False, comment='周期类型：day/week/month')
    period_start = Column(Date, nullable=False, index=True, comment='周期开始日期')
    period_end = Column(Date, nullable=False, comment='周期结束日期')
    total_users = Column(Integer, default=0, comment='总用户数')
    active_users = Column(Integer, default=0, comment='活跃用户数')
    total_learn_seconds = Column(BigInteger, default=0, comment='总学习时长（秒）')
    avg_pass_rate = Column(Float, default=0.0, comment='平均达标率')
    exam_count = Column(Integer, default=0, comment='考试场次')
    created_at = Column(DateTime, server_default=func.now())


class SOPInfo(Base):
    """SOP信息表 - 标准操作流程文档管理"""
    __tablename__ = "sp_sop_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), nullable=True, comment='任务ID')
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    title = Column(String(255), nullable=False, comment='SOP标题')
    filename = Column(String(255), nullable=False, comment='文件名')
    file_uri = Column(String(512), nullable=True, comment='文件URI')
    task_status = Column(String(50), nullable=True, comment='任务状态')
    position_id = Column(String(255), nullable=True, comment='岗位ID')
    sop_version = Column(String(255), nullable=True, comment='SOP版本号')
    remark = Column(String(512), nullable=True, comment='备注')
    start_time = Column(Date, nullable=True, comment='SOP 生效时间')
    end_time = Column(Date, nullable=True, comment='SOP 到期时间')
    created_at = Column(DateTime, server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='更新时间')
    num_flag = Column(Integer, nullable=False, default=0, comment='数值标志')
    file_type = Column(String(255), nullable=True, comment='文件类型')
    percent = Column(String(255), nullable=True, default='0%', comment='完成百分比')
    lang = Column(String(255), nullable=True, comment='语言')


class LearningRecord(Base):
    """学习记录表 - 只读引用，数据写入由 learn 服务负责"""
    __tablename__ = "sp_learning_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True, comment='会话唯一标识')
    user_id = Column(Integer, nullable=False, index=True, comment='用户ID')
    course_id = Column(String(255), nullable=True, comment='课程ID')
    video_id = Column(String(255), nullable=True, comment='视频ID')
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    start_time = Column(DateTime, nullable=True, comment='开始时间')
    end_time = Column(DateTime, nullable=True, comment='结束时间')
    watch_seconds = Column(Integer, default=0, comment='观看时长（秒）')
    from_position = Column(Integer, nullable=True, comment='起始位置')
    end_position = Column(Integer, nullable=True, comment='结束位置')
    watch_progress = Column(Float, nullable=True, comment='观看进度')
    is_completed = Column(Boolean, default=False, comment='是否完成')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Course(Base):
    """课程表"""
    __tablename__ = "sp_course"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    course_id = Column(String(64), nullable=False, index=True, comment='课程唯一标识')
    title = Column(String(255), nullable=False, comment='课程标题')
    position_id = Column(Integer, nullable=True, comment='关联岗位ID')
    is_deleted = Column(Boolean, default=False, comment='是否已删除（逻辑删除）')
    created_at = Column(DateTime, server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='更新时间')

# 陪练明细表
class ExamRecord(Base):
    __tablename__ = "sp_exam_record"
    id = Column(String(32), primary_key=True, index=True)
    user_id = Column(String(255), nullable=True)
    position_id = Column(String(255), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    exam_category = Column(String(64), nullable=True)
    filename = Column(String(256), nullable=True)
    conversation_id = Column(String(64), nullable=True)
    summary = Column(Text, nullable=True)
    total_score = Column(Float, nullable=True)
    accumulated_score = Column(Float, nullable=True)
    total_questions = Column(Integer, nullable=True)
    answered_questions = Column(Integer, nullable=True)
    sop_id = Column(Integer, nullable=True, comment='SOP ID')
    tenant_id = Column(Integer, nullable=True, comment='租户ID')

class User(Base):
    __tablename__ = "sp_user"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    email = Column(String(256), index=True, nullable=False)
    tenant_id= Column(Integer, nullable=True)
    full_name = Column(String(256), nullable=True)
    telephone = Column(String(32), nullable=True)
    password = Column(String(256), nullable=False)
    avatar_url = Column(String(512), nullable=True)
    role_id = Column(Integer, default=UserRole.USER, nullable=False)
    company_id = Column(Integer, nullable=True)
    position_id = Column(Integer, nullable=True)
    department_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    lang = Column(String(8), nullable=True, comment='业务语种（zh/en/th）')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, nullable=True)

class Company(Base):
    __tablename__ = "sp_company"

    company_id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(256), nullable=False)
    tenant_id = Column(Integer, nullable=True)


class Department(Base):
    __tablename__ = "sp_department"

    department_id = Column(Integer, primary_key=True, index=True)
    department_name = Column(String(256), nullable=False)
    company_id = Column(Integer, nullable=True)

class Position(Base):
    __tablename__ = "sp_position"

    position_id = Column(Integer, primary_key=True, index=True)
    position_name = Column(String(256), nullable=False)
    department_id = Column(Integer, nullable=True)


class SOPLeaderboard(Base):
    """SOP 排行榜表 - 持久化存储每个 SOP 的用户排名快照，支持名次变化追踪"""
    __tablename__ = "sp_sop_leaderboard"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    sop_id = Column(Integer, nullable=False, index=True, comment='SOP ID')
    user_id = Column(Integer, nullable=False, index=True, comment='用户ID')
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    lang = Column(String(8), nullable=False, default="zh", index=True, comment='业务语种（zh/en/th）')
    rank = Column(Integer, nullable=False, comment='当前名次')
    score = Column(Float, nullable=False, default=0.0, comment='当前分数')
    last_rank = Column(Integer, nullable=True, comment='上一次名次，NULL 表示新上榜')
    rank_change = Column(Integer, nullable=True, default=0, comment='名次变动 = last_rank - rank，正数升名次，负数降名次，NULL 表示新上榜')
    update_time = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment='排行榜最后更新时间')
    created_at = Column(DateTime, server_default=func.now(), comment='首次上榜时间')


class UserActivity(Base):
    """用户日活统计表"""
    __tablename__ = "sp_user_activity"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    lang = Column(String(8), nullable=False, default="zh", index=True, comment='业务语种（zh/en/th）')
    stat_date = Column(Date, nullable=False, index=True, comment='统计日期')
    active_users = Column(Integer, default=0, comment='日活跃用户数')
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'lang', 'stat_date', name='_tenant_lang_date_uc'),
    )


class UserSession(Base):
    """用户会话表 - 只读引用"""
    __tablename__ = "sp_user_session"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True, comment='用户ID')
    tenant_id = Column(Integer, nullable=False, index=True, comment='租户ID')
    login_time = Column(DateTime, nullable=False, comment='登录时间')
    last_active_time = Column(DateTime, nullable=False, comment='最后活跃时间')


class Tenant(Base):
    """租户表 - 只读引用"""
    __tablename__ = "sp_tenant"

    tenant_id = Column(Integer, primary_key=True, autoincrement=True, comment='租户ID（主键）')
    status = Column(Integer, nullable=False, default=1, comment='状态：1-启用，0-停用')
    expire_time = Column(DateTime, nullable=True, comment='过期时间')
