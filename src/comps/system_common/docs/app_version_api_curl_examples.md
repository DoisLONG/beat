# 客户端版本管理接口 curl 示例

```bash
# 1. 上传版本包
# 从响应中取出 results.file_url，下一步 publish 的 edition_url 直接传这个值
curl -X POST 'http://{host}/v1/app_version/upload' \
  -H 'Authorization: Bearer {token}' \
  -F 'file=@/path/to/app_release.wgt'

# 2. 发布版本
# edition_url = 上一步 upload.results.file_url
# 发布成功后从响应中取出 results.id，后续 revoke 直接传这个值
curl -X POST 'http://{host}/v1/app_version/publish' \
  -H 'Authorization: Bearer {token}' \
  -H 'Content-Type: application/json' \
  -d '{
    "edition_name": "1.0.1",
    "edition_version_code": 2,
    "describe_zh": "1. 修复已知问题<br>2. 优化用户体验",
    "describe_en": "1. Fixed known issues<br>2. Improved user experience",
    "describe_th": "1. แก้ไขปัญหาที่ทราบ<br>2. ปรับปรุงประสบการณ์ผู้ใช้",
    "edition_url": "{upload.results.file_url}",
    "edition_force": 1,
    "package_type": 1,
    "edition_issue": 1,
    "edition_silence": 0
  }'

# 3. 查询当前最新版本
# 客户端传自己的 current_version_code
# 如果 need_update=1，则使用响应里的 data.edition_url 下载（格式：/v1/app_version/download?id={id}）
curl -X POST 'http://{host}/v1/app_version/current' \
  -H 'Content-Type: application/json' \
  -d '{
    "current_version_code": 1
  }'

# 3.1 下载版本包
# id = 第 2 步 publish.results.id（也可用第 3 步 current.data.id）
curl -L 'http://{host}/v1/app_version/download?id={publish.results.id}' -o app_release.wgt

# 4. 查询已发布版本列表
# 可以用 publish 时传入的 edition_name / edition_version_code 做过滤
curl -X POST 'http://{host}/v1/app_version/list' \
  -H 'Authorization: Bearer {token}' \
  -H 'Content-Type: application/json' \
  -d '{
    "page": 1,
    "page_size": 10,
    "status": 1,
    "edition_name": "1.0.1",
    "edition_version_code": 2
  }'

# 5. 撤销发布
# id = 第 2 步 publish.results.id
curl -X POST 'http://{host}/v1/app_version/revoke' \
  -H 'Authorization: Bearer {token}' \
  -H 'Content-Type: application/json' \
  -d '{
    "id": {publish.results.id},
    "revoke_reason": "发现版本包问题，先撤回"
  }'

# 6. 查询已撤销版本列表，确认撤销结果
curl -X POST 'http://{host}/v1/app_version/list' \
  -H 'Authorization: Bearer {token}' \
  -H 'Content-Type: application/json' \
  -d '{
    "page": 1,
    "page_size": 10,
    "status": 2,
    "edition_version_code": 2
  }'
```
