# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM registry.cn-hangzhou.aliyuncs.com/docker_workspace_hub/python:3.10.12-slim

ENV LANG=C.UTF-8

RUN rm -rf /var/lib/apt/lists/* && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends --fix-missing \
        build-essential \
        default-jre \
        libgl1-mesa-glx \
        libjemalloc-dev \
        tesseract-ocr \
        ghostscript \
        python3-tk \
        wget

RUN useradd -m -s /bin/bash user && \
    mkdir -p /home/user && \
    chown -R user /home/user/

USER user

RUN mkdir -p ~/.pip && \
    echo "[global]" > ~/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> ~/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> ~/.pip/pip.conf

COPY comps/smart_practice/requirements.txt /home/user/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /home/user/requirements.txt

ENV PYTHONPATH=/home/user

WORKDIR /home/user/comps/smart_practice

COPY comps /home/user/comps

ENTRYPOINT ["python", "main.py"]
