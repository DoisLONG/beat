# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import mimetypes
import os
from urllib.parse import quote

FILE_ACCESS_ENDPOINT = "/api/v1/files/access"


def build_file_proxy_url(file_uri: str | None) -> str | None:
    if not file_uri or not isinstance(file_uri, str):
        return file_uri
    if not file_uri.startswith(("minio://", "oss://")):
        return file_uri
    return f"{FILE_ACCESS_ENDPOINT}?uri={quote(file_uri, safe='')}"


def apply_proxy_urls_to_course(course_info: dict) -> dict:
    if course_info.get("cover_url"):
        course_info["cover_url"] = build_file_proxy_url(course_info["cover_url"])

    videos = course_info.get("videos")
    if isinstance(videos, list):
        for video in videos:
            if isinstance(video, dict) and video.get("video_url"):
                video["video_url"] = build_file_proxy_url(video["video_url"])
    return course_info


def apply_proxy_urls_to_course_list(items: list[dict]) -> list[dict]:
    for item in items:
        if item.get("cover_url"):
            item["cover_url"] = build_file_proxy_url(item["cover_url"])
    return items


def apply_proxy_urls_to_materials(items: list[dict]) -> list[dict]:
    for item in items:
        if item.get("file_url"):
            item["file_url"] = build_file_proxy_url(item["file_url"])
    return items


def guess_filename(file_uri: str, fallback: str = "download") -> str:
    if not file_uri or not isinstance(file_uri, str):
        return fallback
    cleaned = file_uri.rstrip("/")
    tail = cleaned.rsplit("/", 1)[-1]
    return os.path.basename(tail) or fallback


def guess_content_type(filename: str, default: str = "application/octet-stream") -> str:
    guessed, _encoding = mimetypes.guess_type(filename)
    return guessed or default


def build_content_disposition(filename: str, download: bool) -> str:
    disposition_type = "attachment" if download else "inline"
    ascii_filename = "".join(
        ch if ord(ch) < 128 and ch not in {'"', "\\"} else "_"
        for ch in filename
    ) or "download"
    encoded_filename = quote(filename, safe="")
    return f"{disposition_type}; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
