#!/bin/sh

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -eu

APP_USER="${APP_USER:-user}"
APP_GROUP="${APP_GROUP:-user}"
EXCEL_DATA_DIR="${EXCEL_DATA_DIR:-/home/user/comps/excel/data}"

mkdir -p \
  "${EXCEL_DATA_DIR}" \
  "${EXCEL_DATA_DIR}/jobs" \
  "${EXCEL_DATA_DIR}/output" \
  "${EXCEL_DATA_DIR}/tmp"

chown -R "${APP_USER}:${APP_GROUP}" "${EXCEL_DATA_DIR}"

exec gosu "${APP_USER}:${APP_GROUP}" python main.py
