# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12.9-slim

ENV LANG=C.UTF-8

RUN useradd -ms /bin/bash app
RUN mkdir /app
WORKDIR /app

RUN pip install uv
COPY pyproject.toml uv.lock /app/
RUN uv sync --no-cache --no-dev

ENV PLAYWRIGHT_BROWSERS_PATH="/home/app/.cache/ms-playwright"
RUN uvx playwright install --with-deps
RUN chown -R app:app /home/app/.cache/ms-playwright

RUN mkdir -p /app/uploaded_files && mkdir -p /app/storage && chown -R app /app
ENV PYTHONPATH=/app
COPY ./src/ /app

USER app
ENTRYPOINT ["/app/.venv/bin/python", "crawlee_to_file.py"]