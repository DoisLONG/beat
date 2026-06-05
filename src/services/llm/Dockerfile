# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

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

# Copy only the wheel file from builder
COPY --from=builder /build/dist/*.whl /libs/

# Install the wheel and all **dependencies**
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir /libs/*.whl

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing \
    libgl1-mesa-glx \
    libjemalloc-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash app

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

WORKDIR /app

COPY ./src /app/src

RUN chown -R app:app /home/app/.cache /app
USER app

ENTRYPOINT ["python", "-m", "src.main"]
