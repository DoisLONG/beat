# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

#   智能考试陪练系统

本项目是面向企业内部 SOP、操作规程、应急演练和岗位培训场景的智能考试陪练平台。系统基于大模型、RAG、多微服务架构，覆盖数据预处理、智能陪练、学习服务、系统管理、视频多模态处理、历史会话管理和仪表服务等完整链路。

## 背景

- 题目、答案和评分缺少可溯源能力
- 大模型长上下文带来的幻觉和不稳定问题
- 多轮陪练中题号、分数、状态不稳定
- 用户答错后缺少追问、解释和学习闭环

系统目标是让陪练过程更准确、可控、可解释，并形成从语料入库到学习分析的完整业务闭环。

## 微服务组成

- `dataprep`：数据预处理
- `smart-practice`：智能陪练
- `learn`：学习服务
- `system-common`：系统管理服务
- `asr`：视频语音转写服务
- `excel`：视频多模态结构化处理服务
- `dashboard`：仪表服务
- `account`：用户管理服务
- `chathistory`：历史会话管理微服务

## 整体技术架构

- 接入层：前端 UI
- 业务层：`dataprep`、`smart-practice`、`learn`、`system-common`、`asr`、`excel`、`dashboard`、`account`、`chathistory`
- 数据层：MySQL、MongoDB、Redis、Milvus、MinIO / OSS
- 模型层：外部 LLM、ASR、PDF 解析能力

核心链路：

1. 文档、SOP、视频等资料进入系统
2. `dataprep`、`asr`、`excel` 完成解析、转写、结构化和知识入库
3. `smart-practice` 基于知识检索、状态机和模型能力执行出题、评分、追问
4. `learn`、`dashboard`、`chathistory`、`account`、`system-common` 负责学习、统计、会话、用户与系统管理能力

## 部署流程

当前推荐流程是不在本地构建镜像，由启动脚本先拉取外部镜像并重标记为项目默认镜像名，再执行部署。

### 1. 准备环境

- 安装 Docker 和 Docker Compose
- ubuntu22.04
- 200G磁盘
- 8～16G内存
- 4核及以上cpu

### 2. 执行一键启动脚本

```bash
cd deployment/docker-compose
bash quickstart-dfxw.sh
```

脚本会自动：

- 自动检查并生成 `deployment/docker-compose/dfxw/nginx-ssl/tls.crt` 和 `tls.key`
- 询问是否先从远程拉取镜像并重标记为默认镜像名
- 询问是否直接复用 `deployment/docker-compose/dfxw/.env`
- 分别启动基础依赖服务和陪练业务服务


### 3. 停止服务

```bash
cd deployment/docker-compose
bash quickstart-dfxw.sh stop
```

## 说明
- 如果 `dfxw/.env` 已存在，脚本会询问是否直接复用
- 默认业务镜像目标名保持为 `localhost:5000/ekba/...:latest`
- 基础依赖服务默认使用官方原始镜像名，如 `mongo:7.0.11`、`mysql:8.0.39`、`redis:8.0.2`
- UI 默认通过 HTTPS 暴露，首次启动会自动生成自签名证书

## License
- `LICENSE`
- `NOTICE`
- `THIRD_PARTY_LICENSES.md`
