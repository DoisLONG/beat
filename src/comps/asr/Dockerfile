# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM registry.cn-hangzhou.aliyuncs.com/docker_workspace_hub/python:3.10.12-slim

ENV LANG=C.UTF-8

RUN rm -rf /var/lib/apt/lists/* && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends --fix-missing ffmpeg gosu

RUN mkdir -p ~/.pip && \
    echo "[global]" > ~/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> ~/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> ~/.pip/pip.conf

COPY comps/asr/requirements.txt /home/user/
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

RUN pip install --no-cache-dir --upgrade pip setuptools uv && \
    uv pip install --system --no-cache-dir -r /home/user/requirements.txt

RUN useradd -m -s /bin/bash user && \
    mkdir -p /home/user && \
    chown -R user /home/user/

ENV PYTHONPATH=/home/user
COPY --chown=user:user comps /home/user/comps
COPY --chown=root:root comps/asr/entrypoint.sh /usr/local/bin/asr-entrypoint.sh
RUN chmod 755 /usr/local/bin/asr-entrypoint.sh

WORKDIR /home/user/comps/asr

ENTRYPOINT ["/usr/local/bin/asr-entrypoint.sh"]
