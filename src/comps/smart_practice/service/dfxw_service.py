# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import os
import time
import threading
from typing import Optional, Dict, Any

import requests
from requests import Response
import http.client
from urllib.parse import urlparse

from comps import CustomLogger

logger = CustomLogger("dfxw_service", os.getenv("LOG_LEVEL", "INFO"))

# ============== 环境配置 ==============
DFXW_BASE_URL = os.getenv("DFXW_BASE_URL", "https://ehcloud-gw-ehtest.dxchi.com")
DFXW_TOKEN_URL = os.getenv("DFXW_TOKEN_URL", "https://ehcloud-oauth-ehtest.dxchi.com")
DFXW_CLIENT_ID = os.getenv("DFXW_CLIENT_ID", "docCloud")
DFXW_CLIENT_SECRET = os.getenv("DFXW_CLIENT_SECRET", "yQQrBsEtAlaMMYqHajxC")
TOKEN_ENDPOINT = f"{DFXW_TOKEN_URL}/oauth/token"
PUSH_RESULT_ENDPOINT = f"{DFXW_BASE_URL}/safe-business/lawRecheckFile/pushExamResult"

# ============== 简单内存缓存 ==============
_token_cache_lock = threading.Lock()
_token_cache: Dict[str, Any] = {  # {"access_token": str, "expires_at": int}
}

def _request_token() -> Dict[str, Any]:
    """直接向认证服务器申请新的 token"""
    params = {
        "grant_type": "client_credentials",
        "client_id": DFXW_CLIENT_ID,
        "client_secret": DFXW_CLIENT_SECRET,
    }
    try:
        resp: Response = requests.post(
            TOKEN_ENDPOINT,
            data=params,
            timeout=10,
            headers={
                "User-Agent": "PostmanRuntime/7.36.0",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        resp.raise_for_status()
        data = resp.json()
        # 通常返回: access_token, token_type, expires_in, scope, jti
        access_token = data.get("access_token") or data.get("value")
        if not access_token:
            raise ValueError(f"Token 响应缺少 access_token 字段: {data}")
        expires_in = int(data.get("expires_in", 3600))
        return {
            "access_token": access_token,
            "expires_at": int(time.time()) + expires_in - 30  # 预留 30 秒缓冲
        }
    except Exception as e:
        logger.error(f"获取 token 失败: {e}")
        raise

def get_access_token(force_refresh: bool = False) -> str:
    """获取可用 token，自动缓存与刷新。
    :param force_refresh: 强制刷新
    :return: access_token 字符串
    """
    with _token_cache_lock:
        if (not force_refresh) and _token_cache:
            if _token_cache.get("expires_at", 0) > time.time():
                return _token_cache["access_token"]
        # 重新获取
        token_info = _request_token()
        _token_cache.update(token_info)
        logger.info("成功刷新第三方 access_token")
        return token_info["access_token"]

def push_exam_result(payload: Dict[str, Any], access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    推送考试结果到第三方接口（使用 http.client）

    :param payload: 满足第三方接口字段要求的字典
    :param access_token: 若未提供则自动获取
    :return: 响应 JSON 对象
    :raises ValueError: 缺少必填字段
    :raises RuntimeError: 请求失败或返回非200
    """

    # --- 字段校验 ---
    required_fields = [
        "conversationId", "detail", "score", "totalScore", "completeRate",
        "userId", "userName", "category", "fileName"
    ]
    missing = [f for f in required_fields if f not in payload]
    if missing:
        raise ValueError(f"缺少必填字段: {', '.join(missing)}")

    # --- AccessToken ---
    access_token = access_token or get_access_token()

    # --- URL 解析 ---
    parsed = urlparse(DFXW_BASE_URL)
    scheme = parsed.scheme.lower()
    host = parsed.netloc
    if not host:
        raise ValueError(f"无效的 DFXW_BASE_URL: {DFXW_BASE_URL}")
    path = "/safe-business/lawRecheckFile/pushExamResult"

    # --- 请求体与头 ---
    body = json.dumps(payload, ensure_ascii=False)
    logger.info(f"推送考试结果 | payload={body}")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    # --- 建立连接 ---
    conn_class = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    conn = conn_class(host, timeout=10)

    try:
        conn.request("POST", path, body=body.encode("utf-8"), headers=headers)
        res = conn.getresponse()
        response_text = res.read().decode("utf-8", errors="replace")
        status = res.status

        # 尝试解析 JSON 响应
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            response_data = {"raw": response_text}

        if status == 200:
            logger.info(f"推送考试结果成功 | status={status} | response={response_data}")
            return response_data
        else:
            logger.error(f"推送考试结果失败 | status={status} | response={response_data}")
            raise RuntimeError(f"HTTP {status}: {response_text}")

    except (http.client.HTTPException, ConnectionError, TimeoutError) as e:
        logger.exception(f"网络或HTTP错误: {e}")
        raise RuntimeError(f"HTTP连接错误: {e}") from e
    except Exception as e:
        logger.exception(f"推送考试结果异常: {e}")
        raise
    finally:
        conn.close()




# ============== 封装：统一入口 ==============

async def submit_exam_result(conversation_id: str, detail: str, score: int, total_score: int,
                       complete_rate: str, user_id: str, user_name: str, category: str,
                       file_name: str) -> Dict[str, Any]:
    """业务友好封装，传入原始字段实现推送。
    :return: 第三方响应 JSON
    """
    payload = {
        "conversationId": conversation_id,
        "detail": detail,
        "score": score,
        "totalScore": total_score,
        "completeRate": complete_rate,
        "userId": user_id,
        "userName": user_name,
        "category": category,
        "fileName": file_name,
    }
    return push_exam_result(payload)

__all__ = [
    "get_access_token",
    "push_exam_result",
    "submit_exam_result",
]
