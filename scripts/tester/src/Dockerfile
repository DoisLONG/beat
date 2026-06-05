# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim 

RUN mkdir -p /working/cases
WORKDIR /working

COPY requirements.txt /working 
RUN pip install --no-cache-dir -r /working/requirements.txt

COPY runner.py /working

CMD [ "/working/runner.py", "--parallel", "--casebase", "/working/cases"]
