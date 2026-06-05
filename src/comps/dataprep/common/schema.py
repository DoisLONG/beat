# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import uuid
from datetime import datetime
from enum import Enum

def make_response(data=None, msg="操作成功", is_success=True, http_status_code=200):
    return {
        "http_status_code": http_status_code,
        "is_success": is_success,
        "msg": msg,
        "data": data,
        "trace_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

class FileType(str, Enum):
    SOP = "sop"
    RISK = "risk"
    OPERATION = "operation"
    EMERGENCY_DRILL = "emergency_drill"