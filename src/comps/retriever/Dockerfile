# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim

ENV LANG=C.UTF-8

ARG ARCH="cpu"

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing \
    build-essential \
    libgl1-mesa-glx \
    libjemalloc-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash user && \
    mkdir -p /home/user && \
    chown -R user /home/user/

USER user

COPY comps/retriever/requirements.txt /home/user/

RUN pip install --no-cache-dir --upgrade pip && \
    if [ ${ARCH} = "cpu" ]; then pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu; fi && \
    pip install --no-cache-dir -r /home/user/requirements.txt

COPY comps /home/user/comps
# Add patch file for langchain_milvus
COPY comps/retriever/patch/milvus.py /home/user/.local/lib/python3.11/site-packages/langchain_milvus/vectorstores/milvus.py
ADD comps/embedding/hf_cache.tgz /home/user

ENV PYTHONPATH=/home/user

WORKDIR /home/user/comps/retriever

ENTRYPOINT ["python", "retriever.py"]
