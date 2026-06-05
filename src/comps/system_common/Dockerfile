# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM registry.cn-hangzhou.aliyuncs.com/docker_workspace_hub/python:3.10.12-slim

ENV LANG=C.UTF-8

RUN useradd -ms /bin/bash user

COPY comps/system_common/requirements.txt  /home/user/

RUN mkdir -p ~/.pip && \
    echo "[global]" > ~/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> ~/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> ~/.pip/pip.conf

RUN pip install --no-cache-dir --upgrade pip setuptools -i https://pypi.tuna.tsinghua.edu.cn/simple

RUN pip install  -r /home/user/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONPATH=/home/user
COPY comps /home/user/comps

USER user
WORKDIR /home/user/comps/system_common

ENTRYPOINT ["python", "main.py"]