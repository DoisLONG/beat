# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.10.12-slim

ENV LANG=C.UTF-8

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash user

RUN chown -R user:user /home/user/

USER user

COPY comps/mcp/requirements.txt  /home/user/
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r /home/user/requirements.txt

ENV PYTHONPATH=/home/user
COPY comps /home/user/comps

USER root

USER user
WORKDIR /home/user/comps/mcp

ENTRYPOINT ["python", "client.py"]