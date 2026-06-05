# Excel Service

`src/comps/excel` 是项目内标准化后的 Excel 微服务。

主要职责：

- 拉取 ASR 服务结果
- 使用 LLM 将转写文本结构化
- 生成 Excel 文件
- 调用 `dataprep` 上传生成结果

主要接口：

- `GET /api/v2/universal/jobs`
- `GET /api/v2/universal/jobs/{task_id}/status`
- `GET /api/v2/universal/jobs/{task_id}/result`

本地测试：

```bash
cd src/comps/excel
pytest tests -q
```
