# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.10.12-slim

ENV LANG=C.UTF-8

ARG ARCH="cpu"

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing \
    build-essential \
    default-jre \
    libgl1-mesa-glx \
    libjemalloc-dev \
    tesseract-ocr \
    ghostscript \
    python3-tk \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash user
# embed paddleocr and embedding models
ADD comps/dataprep/paddleocr_cache.tgz /home/user/
ADD comps/dataprep/hf_cache.tgz /home/user
RUN chown -R user:user /home/user/

USER user

RUN pip install --no-cache-dir requests huggingface_hub
COPY comps/dataprep/download_models_hf.py /home/user
RUN python /home/user/download_models_hf.py

RUN pip install --no-cache-dir -U magic-pdf[full] --extra-index-url https://download.pytorch.org/whl/cpu --extra-index-url https://wheels.myhloli.com

COPY comps/dataprep/requirements.txt  /home/user/
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r /home/user/requirements.txt

ENV PYTHONPATH=/home/user
COPY --chown=user:user comps /home/user/comps
RUN mkdir -p /home/user/comps/dataprep/uploaded_files

WORKDIR /home/user/comps/dataprep

ENTRYPOINT ["python", "prepare_doc_milvus.py"]
