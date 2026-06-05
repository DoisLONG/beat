# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from pydantic import SecretStr

from comps.system_common.config import MODEL_CONFIG_ENCRYPTION_KEYS


class SecretEncryptionError(ValueError):
    pass


class SecretDecryptionError(ValueError):
    pass


def _normalize_encryption_keys(encryption_keys: str | Sequence[str] | None) -> list[str]:
    """
    标准化加密密钥输入格式
    
    功能：
    1. 支持字符串（逗号分隔）或列表两种输入格式
    2. 如果未提供，从环境变量 MODEL_CONFIG_ENCRYPTION_KEYS 读取
    3. 过滤空字符串，返回纯净的密钥列表
    
    Args:
        encryption_keys: 密钥字符串、列表或 None
    
    Returns:
        list[str]: 清理后的密钥列表
    
    Raises:
        SecretEncryptionError: 当没有任何可用密钥时抛出
    """
    source = encryption_keys if encryption_keys is not None else MODEL_CONFIG_ENCRYPTION_KEYS
    if isinstance(source, str):
        keys = [item.strip() for item in source.split(",") if item.strip()]
    else:
        keys = [item.strip() for item in source if item.strip()]

    if not keys:
        raise SecretEncryptionError("模型配置加密密钥未配置。")
    return keys


def _build_multifernet(encryption_keys: str | Sequence[str] | None) -> MultiFernet:
    """
    构建多 Fernet 实例（支持密钥轮换）
    
    工作原理：
    1. 将每个密钥字符串转换为 Fernet 对象
    2. 使用 MultiFernet 包装多个实例
    3. 加密时使用第一个密钥，解密时尝试所有密钥
    
    应用场景：
    - 密钥轮换期间，新旧密钥共存
    - 历史数据用旧密钥加密，新数据用新密钥加密
    
    Returns:
        MultiFernet: 支持多密钥的加密器
    
    Raises:
        SecretEncryptionError: 任何密钥格式不正确时抛出
    """
    fernet_instances: list[Fernet] = []
    for key in _normalize_encryption_keys(encryption_keys):
        try:
            fernet_instances.append(Fernet(key.encode("utf-8")))
        except Exception as exc:  # noqa: BLE001 - normalize invalid-key failures
            raise SecretEncryptionError("模型配置加密密钥格式无效。") from exc
    return MultiFernet(fernet_instances)


def derive_secret_key_id(encryption_keys: str | Sequence[str] | None = None) -> str:
    """
    派生密钥标识符（用于审计和追踪）
    
    生成逻辑：
    1. 取第一个活跃密钥（用于加密的主密钥）
    2. 计算 SHA256 哈希值的前 16 个字符
    3. 添加前缀 "fernet:" 标识算法
    
    用途：
    - 记录日志时标识使用了哪个密钥加密
    - 不暴露真实密钥内容
    
    Returns:
        str: 密钥指纹，格式如 "fernet:a1b2c3d4e5f67890"
    """
    primary_key = _normalize_encryption_keys(encryption_keys)[0]
    digest = hashlib.sha256(primary_key.encode("utf-8")).hexdigest()[:16]
    return f"fernet:{digest}"


def encrypt_api_key(plaintext: str | None, encryption_keys: str | Sequence[str] | None = None) -> str | None:
    """
    加密 API Key（入库前处理）
    
    加密流程：
    1. 如果输入为 None，直接返回 None（允许空密钥）
    2. 使用 MultiFernet 加密明文字符串
    3. 返回 Base64 编码的密文字符串
    
    安全特性：
    - 使用当前活跃密钥（密钥列表的第一个）加密
    - 异常信息自动脱敏，不泄露密钥内容
    
    Args:
        plaintext: 明文 API Key
        encryption_keys: 密钥列表（可选，默认从环境变量读取）
    
    Returns:
        str | None: 加密后的字符串或 None
    
    Raises:
        SecretEncryptionError: 密钥未配置或加密失败时抛出
    """
    if plaintext is None:
        return None

    try:
        ciphertext = _build_multifernet(encryption_keys).encrypt(plaintext.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - normalize unexpected failures
        raise SecretEncryptionError("无法加密模型配置密钥。") from exc
    return ciphertext.decode("utf-8")


def decrypt_api_key(
    ciphertext: str | None,
    encryption_keys: str | Sequence[str] | None = None,
) -> SecretStr | None:
    """
    解密 API Key（使用时读取）
    
    解密流程：
    1. 如果输入为 None，直接返回 None
    2. 使用 MultiFernet 尝试所有密钥解密
    3. 返回 SecretStr 对象（Pydantic 安全字符串类型）
    
    安全特性：
    - 支持多密钥解密（兼容历史数据）
    - 使用 SecretStr 封装，防止意外打印明文
    - 异常信息统一脱敏
    
    Args:
        ciphertext: 加密的字符串
        encryption_keys: 密钥列表（可选）
    
    Returns:
        SecretStr | None: 解密后的安全字符串或 None
    
    Raises:
        SecretDecryptionError: 密钥未配置、格式错误或解密失败时抛出
    """
    if ciphertext is None:
        return None

    # Backward compatibility:
    # - try legacy/new fernet ciphertext first
    # - if decrypt fails with InvalidToken, treat as historical plaintext
    try:
        plaintext = _build_multifernet(encryption_keys).decrypt(ciphertext.encode("utf-8"))
        return SecretStr(plaintext.decode("utf-8"))
    except InvalidToken:
        return SecretStr(ciphertext)
    except SecretEncryptionError as exc:
        raise SecretDecryptionError("模型配置加密密钥不可用。") from exc
    except Exception as exc:  # noqa: BLE001 - normalize unexpected failures
        raise SecretDecryptionError("无法读取模型配置密钥。") from exc


def mask_secret(
    secret: SecretStr | str | None,
    *,
    visible_prefix: int = 2,
    visible_suffix: int = 2,
    mask_char: str = "*",
) -> str | None:
    """
    掩码敏感信息（用于日志和前端展示）
    
    掩码规则：
    1. 保留前 2 个字符和后 2 个字符
    2. 中间部分用星号替换
    3. 长度不足时全部用星号填充
    
    示例：
    - "sk-abc123xyz" → "sk***********yz"
    - "key" → "***"
    - "ab" → "**"
    
    安全特性：
    - 支持 SecretStr 和 str 两种输入
    - 自动处理 None 和空字符串
    - 可自定义可见字符数量
    
    Args:
        secret: 要掩码的秘密
        visible_prefix: 保留前缀长度（默认 2）
        visible_suffix: 保留后缀长度（默认 2）
        mask_char: 掩码字符（默认 "*"）
    
    Returns:
        str | None: 掩码后的字符串
    
    Raises:
        ValueError: 参数不合法时抛出
    """
    if secret is None:
        return None

    raw_value = secret.get_secret_value() if isinstance(secret, SecretStr) else secret
    if not raw_value:
        return ""

    if len(mask_char) != 1:
        raise ValueError("mask_char must be a single character.")

    if visible_prefix < 0 or visible_suffix < 0:
        raise ValueError("visible_prefix/visible_suffix must be >= 0.")

    if len(raw_value) <= visible_prefix + visible_suffix:
        return mask_char * len(raw_value)

    middle_length = len(raw_value) - visible_prefix - visible_suffix
    return f"{raw_value[:visible_prefix]}{mask_char * middle_length}{raw_value[-visible_suffix:]}"
