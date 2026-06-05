# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing \
    libgl1-mesa-glx \
    libjemalloc-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash user && \
    mkdir -p /home/user && \
    chown -R user /home/user/

USER user

COPY comps/router/requirements.txt /home/user/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /home/user/requirements.txt

COPY comps /home/user/comps

ENV PYTHONPATH=/home/user

WORKDIR /home/user/comps/router

RUN echo 'ulimit -S -n 999999' >> ~/.bashrc

ENTRYPOINT ["python", "chatqna.py"]
