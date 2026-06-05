# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, EmailStr
from typing import Optional, Union
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role_id: Optional[int] = None
    is_active: bool = True
    telephone: Optional[str] = None
    company_id: Optional[int] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    tenant_id: Optional[int] = None
    lang: Optional[str] = None

class GetUserParams(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company_id: Optional[int] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    page: int = 1
    size: int = 20
    id: Optional[int] = None

class CreateUserPayload(UserBase):
    password: str

class UpdateUserPayload(BaseModel):
    id: Union[int, str]
    full_name: Optional[str] = None
    telephone: Optional[str] = None
    company_id: Optional[int] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    avatar_url: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UpdatePasswordPayload(BaseModel):
    old_password: str
    new_password: str


class OnboardingStatusPayload(BaseModel):
    welcome_guide_pending: Optional[int] = None
    dashboard_welcome_guide_pending: Optional[int] = None

class ExamRecordPayload(BaseModel):
    position_id: int | None = None
    company_id: int | None = None
    department_id: int | None = None
    user_id: str | None = None
    username: str | None = None  # 用户名称，用于模糊搜索
    page: int = 1
    page_size: int = 20

_ROLE_NAMES: dict[str, dict[int, str]] = {
    "zh": {1: "超级管理员", 2: "管理员", 3: "普通用户"},
    "en": {1: "Super Admin",  2: "Admin",  3: "User"},
    "th": {1: "ผู้ดูแลระบบสูงสุด", 2: "ผู้ดูแลระบบ", 3: "ผู้ใช้งาน"},
}

class Role(BaseModel):
    id: int
    name: str

    @staticmethod
    def from_role_id(role_id: int, lang: str = "zh") -> "Role":
        lang = lang if lang in _ROLE_NAMES else "zh"
        names = _ROLE_NAMES[lang]
        name = names.get(role_id, names[3])
        return Role(id=role_id, name=name)

class Company(BaseModel):
    company_id: int
    company_name: str

class Department(BaseModel):
    department_id: int
    department_name: str

class Position(BaseModel):
    position_id: int
    position_name: str

class UserData(UserBase):
    id: int
    welcome_guide_pending: int = 0
    dashboard_welcome_guide_pending: int = 0
    role: Optional[Role] = None
    company: Optional[Company] = None
    department: Optional[Department] = None
    position: Optional[Position] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class LoginPayload(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str

class Token(BaseModel):
    token: str

class TokenData(BaseModel):
    id: Optional[int] = None
    tenant_id: Optional[int] = None
    position_id: Optional[int] = None
    name: Optional[str] = None
    role: Optional[int] = None
    lang: str = "zh"

class LoginData(Token):
    data: UserData

class ListUsersResponse(BaseModel):
    data: list[UserData]
    total: int
    page: int = 0
    page_size: int = 20
    tenant_id: int | None = None
