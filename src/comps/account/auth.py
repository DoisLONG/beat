# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

from jose import jwt, ExpiredSignatureError
import datetime
from passlib.context import CryptContext
from fastapi import HTTPException, Request
from typing import Callable
from functools import wraps

from comps import CustomLogger
from comps.account.model import User, UserRole
from comps.account.schema import Token, TokenData
from comps.account.config import SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_DELTA

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = CustomLogger("account_auth", os.getenv("LOG_LEVEL", "INFO"))

def ensure_bytes(password: str, min_bytes: int = 8, max_bytes: int = 32) -> None:
    if len(password.encode("utf-8")) < min_bytes:
        raise HTTPException(status_code=400, detail=f"密码长度不足，最少需要{min_bytes}。")
    if len(password.encode("utf-8")) > max_bytes:
        raise HTTPException(status_code=400, detail=f"密码长度超过最大限制，最多{max_bytes}。")

def hash_password(password: str) -> str:
    ensure_bytes(password)
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def sign_token(user: User) -> Token:
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=JWT_EXPIRATION_DELTA)
    lang = getattr(user, "lang", None) or "zh"
    if lang not in ("zh", "en", "th"):
        lang = "zh"
    payload = {
        "sub": f"{user.id}",
        "name": user.name,
        "tenant_id": user.tenant_id,
        "position_id": user.position_id,
        "exp": expires,
        "role": f"{user.role_id}",
        "lang": lang,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return Token(token=token)

def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        name = payload.get("name")
        role_value = payload.get("role")
        tenant_id = payload.get("tenant_id")
        position_id = payload.get("position_id")
        lang = payload.get("lang") or "zh"
        if lang not in ("zh", "en", "th"):
            lang = "zh"
        if not UserRole.is_owner(int(role_value)):
            if sub is None or name is None or role_value is None or tenant_id is None:
                raise HTTPException(status_code=401, detail="无效的认证令牌。")
        return TokenData(
            id=int(sub),
            tenant_id=int(tenant_id),
            name=str(name),
            role=int(role_value),
            position_id=int(position_id) if position_id else 0,
            lang=lang,
        )
    except ExpiredSignatureError:
        logger.exception("认证令牌已过期")
        raise HTTPException(status_code=401, detail="认证令牌已过期。")
    except Exception as e:
        logger.exception("认证令牌验证失败")
        raise HTTPException(status_code=401, detail="认证令牌验证失败。")

def require_auth(admin_only: bool = False, owner_only: bool = False, field_name: str = "user"):
    """
    鉴权装饰器：
      - 验证 JWT 并注入 user 信息
      - 如果 admin_only=True，则校验 user["role"] 是否为管理员
      - 如果 owner_only=True，则校验 user["role"] 是否为所有者
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request | None = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request and "request" in kwargs:
                val = kwargs["request"]
                if isinstance(val, Request):
                    request = val
            
            if not request:
                for k, val in kwargs.items():
                    if isinstance(val, Request):
                        request = val
                        break
            
            if not request:
                raise RuntimeError("无法获取 Request 对象进行鉴权。")

            # 提取 Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid token")

            token = auth_header.split(" ", 1)[1]
            user = verify_token(token)

            # 管理员权限校验
            if owner_only and not UserRole.is_owner(user.role):
                raise HTTPException(status_code=403, detail="权限不足")
            if admin_only and not UserRole.is_admin(user.role):
                raise HTTPException(status_code=403, detail="权限不足")

            if field_name in kwargs:
                kwargs[field_name] = user
            return await func(*args, **kwargs)

        return wrapper

    return decorator

def require_auth_dict(admin_only: bool = False, owner_only: bool = False, field_name: str = "user"):
    """
    鉴权装饰器（简化版）：
      - 验证 JWT 并注入包含tenant_id的用户信息
      - 直接从JWT中获取tenant_id，无需查询数据库
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request | None = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request and "request" in kwargs:
                val = kwargs["request"]
                if isinstance(val, Request):
                    request = val
            
            if not request:
                for k, val in kwargs.items():
                    if isinstance(val, Request):
                        request = val
                        break
            
            if not request:
                raise RuntimeError("无法获取 Request 对象进行鉴权。")

            # 提取 Header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid token")

            token = auth_header.split(" ", 1)[1]
            user = verify_token(token)  # 这里返回的TokenData包含tenant_id

            # 管理员权限校验
            if owner_only and not UserRole.is_owner(user.role):
                raise HTTPException(status_code=403, detail="权限不足")
            if admin_only and not UserRole.is_admin(user.role):
                raise HTTPException(status_code=403, detail="权限不足")

            # 将用户信息转换为字典格式，方便后续使用
            user_dict = {
                "id": user.id,
                "name": user.name,
                "role": user.role,
                "tenant_id": user.tenant_id,  # 从JWT中获取的tenant_id
                "position_id": user.position_id,  # 从JWT中获取的position_id
                "lang": user.lang,  # 从JWT中获取的业务语种
            }

            if field_name in kwargs:
                kwargs[field_name] = user_dict
            return await func(*args, **kwargs)

        return wrapper

    return decorator
