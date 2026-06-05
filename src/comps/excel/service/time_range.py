# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import date


def resolve_time_range(start_time: str, end_time: str) -> tuple[str, str]:
    resolved_start = start_time or date.today().isoformat()
    resolved_end = end_time or "2099-12-31"

    date.fromisoformat(resolved_start)
    date.fromisoformat(resolved_end)
    return resolved_start, resolved_end
