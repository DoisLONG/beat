# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pydantic import BaseModel, Field


class ASRSegment(BaseModel):
    id: str = Field(..., description="片段ID")
    start: float = Field(..., description="开始时间")
    end: float = Field(..., description="结束时间")
    text: str = Field(..., description="原始ASR文本")


class RefinedSegment(BaseModel):
    id: str = Field(description="原始片段唯一标识")
    start: float = Field(description="开始时间(秒)")
    end: float = Field(description="结束时间(秒)")
    original_text: str = Field(description="ASR原始文本")
    refined_text: str = Field(description="矫正后的文本")


class ASRCorrectionResult(BaseModel):
    original_segments: list[dict] = Field(description="原始输入片段")
    refined_segments: list[RefinedSegment] = Field(description="矫正后的片段")
    new_terms_added: list[str] = Field(default_factory=list, description="新发现的专业术语")
    status: str = Field(default="success", description="处理状态")
    message: str = Field(default="", description="处理说明")


class TextRefineResponse(BaseModel):
    original_segments: list[ASRSegment] = Field(..., description="原始ASR片段列表")
    refined_segments: list[RefinedSegment] = Field(..., description="矫正后的ASR片段列表")
    new_terms_added: list[str] = Field(default_factory=list, description="新增专业词汇")
    status: str = Field(default="success", description="处理状态")
    message: str = Field(default="", description="状态消息")
