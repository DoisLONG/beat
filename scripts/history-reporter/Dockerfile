# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim 

RUN mkdir -p /working
WORKDIR /working

COPY requirements.txt /working
RUN pip install --no-cache-dir -r /working/requirements.txt

COPY history-reporter.py /working

ENTRYPOINT ["python", "history-reporter.py"]