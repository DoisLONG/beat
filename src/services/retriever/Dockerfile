# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Build stage
FROM python:3.12.9-slim AS builder

WORKDIR /build

# need to config additional context "libs" in docker-compose.yml or docker buildx cli
COPY --from=libs . /build

# Build the wheel
RUN pip install build && \
    python -m build --wheel

# Final stage ---------------------------------------------
FROM python:3.12.9-slim
ENV LANG=C.UTF-8
ARG ARCH="cpu"

# Copy only the wheel file from builder
COPY --from=builder /build/dist/*.whl /libs/

# Install the wheel and all **dependencies**
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /libs/*.whl

# Create a non-root user for security
RUN useradd -ms /bin/bash app

RUN pip install --no-cache-dir --upgrade pip
RUN if [ ${ARCH} = "cpu" ]; then pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu; fi

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

WORKDIR /app

# embedding huggingface cache for air gapped mode
ADD artifacts/hf_cache.tgz /home/app
COPY ./src /app/src

RUN chown -R app:app /home/app/.cache /app
RUN mkdir -p /tmp/kbs-info

ENTRYPOINT ["bash", "-c", "chown -R app:app /tmp/kbs-info && su -c 'python -m src.main' app"]
