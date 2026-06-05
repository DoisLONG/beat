# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ExamRecordCreate(BaseModel):
    id: str
    user_id: Optional[str] = None
    position_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    exam_category: Optional[str] = None
    filename: Optional[str] = None
    conversation_id: Optional[str] = None
    summary: Optional[str] = None
    total_score: Optional[float] = None
    accumulated_score: Optional[float] = None
    total_questions: Optional[int] = None
    answered_questions: Optional[int] = None
    sop_id: Optional[int] = None
    tenant_id: Optional[int] = None