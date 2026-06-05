# ASR Service

`src/comps/asr` 是项目内标准化后的 ASR 微服务。

主要职责：

- 上传 MP4 视频
- 使用远端或本地 ASR 引擎转写音频
- 使用术语表和文本矫正链路修正 ASR 内容
- 基于 LLM 生成章节跳转结果

主要配置：

- `ASR_ENGINE=qwen|faster_whisper`
- `ASR_ENDPOINT`
- `ASR_MODEL`
- `ASR_LLM_MODEL`（用于 ASR 后处理链路，默认继承 `DATAPREP_LLM_MODEL`）
- `ASR_WHISPER_MODEL_SIZE`
- `ASR_WHISPER_DEVICE`
- `ASR_WHISPER_COMPUTE_TYPE`
- `ASR_WHISPER_MODEL_PATH`

主要接口：

- `POST /api/v1/asr/jobs`
- `GET /api/v1/asr/jobs/{job_id}/status`
- `GET /api/v1/asr/jobs/{job_id}/result`
- `GET /api/v1/glossary/terms`
- `POST /api/v1/glossary/terms`

本地测试：

```bash
cd src/comps/asr
pytest tests -q
```
