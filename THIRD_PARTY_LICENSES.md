# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Third-Party Licenses

This document records the primary third-party code bases and dependency
manifests used by this repository. It is intended as an inventory and
compliance aid for source and image distribution.

This file does not replace the original license texts published by upstream
projects. Exact dependency versions and transitive dependency trees should be
verified from the referenced manifest and lock files during release or image
packaging.

## Included Or Derived Upstream Projects

| Component | Upstream | License |
| --- | --- | --- |
| Intel OPEA (Open Platform for Enterprise AI) | https://github.com/opea-project/opea | Apache-2.0 |

## Frontend Dependency Source

Frontend direct dependencies are declared in:

- `src/ui/package.json`

Representative frontend packages include:

- `react`
- `react-dom`
- `@mantine/core`
- `@mantine/hooks`
- `@mantine/notifications`
- `@reduxjs/toolkit`
- `react-redux`
- `axios`
- `react-markdown`
- `react-pdf`
- `pdfjs-dist`
- `vite`
- `typescript`
- `vitest`

License information for these packages must be verified from npm package
metadata and lockfiles used during release.

## Python Dependency Sources

Python direct dependencies are declared in these repository manifests.

### Core Components Under `src/comps`

- `src/comps/account/requirements.txt`
- `src/comps/asr/requirements.txt`
- `src/comps/chathistory/requirements.txt`
- `src/comps/dashboard/requirements.txt`
- `src/comps/dataprep/requirements.txt`
- `src/comps/embedding/requirements.txt`
- `src/comps/excel/requirements.txt`
- `src/comps/knowledge-base/requirements.txt`
- `src/comps/learn/requirements.txt`
- `src/comps/llm/requirements.txt`
- `src/comps/mcp/requirements.txt`
- `src/comps/retriever/requirements.txt`
- `src/comps/rerank/requirements.txt`
- `src/comps/router/requirements.txt`
- `src/comps/smart_practice/requirements.txt`
- `src/comps/system_common/requirements.txt`
- `src/comps/web_search/requirements.txt`

Representative Python packages used across components include:

- `fastapi`
- `uvicorn`
- `aiohttp`
- `SQLAlchemy`
- `PyMySQL`
- `redis`
- `celery`
- `docarray`
- `openai`
- `langchain`
- `langchain-community`
- `langchain-milvus`
- `pymilvus`
- `pandas`
- `numpy`
- `scikit-learn`
- `openpyxl`
- `PyMuPDF`
- `pdfplumber`
- `camelot-py`
- `minio`
- `oss2`
- `python-jose`
- `passlib`
- `opentelemetry-api`
- `opentelemetry-sdk`

### Services Under `src/services`

- `src/services/llm/pyproject.toml`
- `src/services/llm/requirements.txt`
- `src/services/llm/uv.lock`
- `src/services/retriever/pyproject.toml`
- `src/services/retriever/requirements.txt`
- `src/services/retriever/uv.lock`
- `src/services/router/pyproject.toml`
- `src/services/router/requirements.txt`
- `src/services/router/uv.lock`
- `src/services/webcrawler/pyproject.toml`
- `src/services/webcrawler/uv.lock`

### Shared Libraries Under `src/libs`

- `src/libs/pyproject.toml`
- `src/libs/uv.lock`

## Utility And Plugin Dependency Sources

### History Reporter And Tester

- `scripts/history-reporter/pyproject.toml`
- `scripts/history-reporter/requirements.txt`
- `scripts/tester/src/pyproject.toml`
- `scripts/tester/src/requirements.txt`

### Dify Plugins

- `scripts/dify-plugins/eap-llm-service/requirements.txt`
- `scripts/dify-plugins/eap-llm-service/manifest.yaml`
- `scripts/dify-plugins/huggingface-tei/requirements.txt`
- `scripts/dify-plugins/huggingface-tei/manifest.yaml`
- `scripts/dify-plugins/ovms_models/requirements.txt`
- `scripts/dify-plugins/ovms_models/manifest.yaml`

## Deployment Artifacts

Deployment assets in `deployment/` may reference third-party container images,
Helm charts, or infrastructure projects, including but not limited to:

- MongoDB
- MySQL
- Redis
- MinIO
- Milvus
- etcd
- vLLM
- OVMS
- Text Embeddings Inference

The licenses for these components are governed by their respective upstream
projects and container image publishers.

## Release Guidance

When distributing source, images, or deployment bundles for this repository,
include at least the following files:

- `LICENSE`
- `NOTICE`
- `THIRD_PARTY_LICENSES.md`

For production release or external redistribution, additionally verify:

1. Exact dependency versions from lockfiles and image tags.
2. Third-party package licenses from upstream package metadata.
3. Any required attribution or notice obligations imposed by upstream
   projects included in the final distribution.
