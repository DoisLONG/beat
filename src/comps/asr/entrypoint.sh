#!/bin/sh

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -eu

APP_USER="${APP_USER:-user}"
APP_GROUP="${APP_GROUP:-user}"
ASR_DATA_DIR="${ASR_DATA_DIR:-/home/user/comps/asr/data}"

mkdir -p \
  "${ASR_DATA_DIR}" \
  "${ASR_DATA_DIR}/uploads" \
  "${ASR_DATA_DIR}/jobs" \
  "${ASR_DATA_DIR}/asr" \
  "${ASR_DATA_DIR}/results" \
  "${ASR_DATA_DIR}/tmp"

chown -R "${APP_USER}:${APP_GROUP}" "${ASR_DATA_DIR}"

exec gosu "${APP_USER}:${APP_GROUP}" python main.py
