# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

def normalize_email(email: str) -> str:
    """
    Normalize the email address by converting it to lowercase and stripping whitespace.
    """
    if not email:
        return email
    return email.strip().lower()

def normalize_username(username: str) -> str:
    """
    Normalize the username by stripping leading and trailing whitespace.
    """
    if not username:
        return username
    return username.strip()

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
