#!/bin/sh
# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# setting nginx.conf
envsubst '${APP_BACKEND_ENDPOINT} ${APP_MCP_LIST} ${APP_KBS_ENDPOINT} ${APP_CHATHISTORY_ENDPOINT} ${APP_LLM_ENDPOINT} ${APP_DOWNLOAD_SERVER} ${APP_TRAIN_CHAT} ${APP_DATAPREP_SOPS}' < /tmp/default.conf.template > /etc/nginx/conf.d/default.conf
