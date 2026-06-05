# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
language_resolver.py
从 FastAPI Request 或原始请求头字符串中解析并标准化业务语种。
"""

from __future__ import annotations

from comps.dataprep.multilingual.context import LanguageContext

# 支持的业务语种白名单
SUPPORTED_LANGS: frozenset[str] = frozenset({"zh", "en", "th"})

# 不支持时的降级语种
DEFAULT_LANG: str = "zh"


class LanguageResolver:
    """从请求头解析并标准化语种。

    解析规则：
    1. 读取 Accept-Language 请求头
    2. 取优先级最高的第一个语种标签（逗号前）
    3. 去掉 q-value（分号后），只保留语种标签
    4. 取主语种码（连字符前部分），转小写
    5. 非 zh / en / th 时默认降级为 zh

    示例：
        "zh-CN,zh;q=0.9,en;q=0.8" -> "zh"
        "en-US,en;q=0.9"          -> "en"
        "th-TH,th;q=0.9"          -> "th"
        "ja-JP,ja;q=0.9"          -> "zh"  （降级）
    """

    @classmethod
    def from_request(cls, request) -> LanguageContext:
        """从 FastAPI Request 对象解析语种上下文。"""
        header: str = request.headers.get("accept-language", "") or ""
        return cls.from_header(header)

    @classmethod
    def from_header(cls, value: str | None) -> LanguageContext:
        """从原始 Accept-Language 字符串解析语种上下文。"""
        raw: str = value or ""
        lang = cls._normalize(raw)
        return LanguageContext(raw_accept_language=raw, lang=lang)

    @classmethod
    def _normalize(cls, value: str) -> str:
        """标准化语种码，返回 zh / en / th 之一。"""
        if not value:
            return DEFAULT_LANG
        # 取第一个语种标签（逗号分割）
        first_tag = value.split(",")[0].strip()
        # 去掉 q-value（分号分割取第一段）
        primary = first_tag.split(";")[0].strip()
        # 去掉区域码（连字符分割取第一段），转小写
        lang_code = primary.split("-")[0].lower()
        return lang_code if lang_code in SUPPORTED_LANGS else DEFAULT_LANG
