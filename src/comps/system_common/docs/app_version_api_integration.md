# 客户端版本管理接口对接文档

## 1. 适用范围

本文档用于前后端对接 `system_common` 中的客户端版本管理接口，覆盖以下能力：

- 上传版本包
- 发布版本
- 查询最新版本
- 下载版本包
- 查询版本列表
- 撤销已发布版本

当前版本包支持两种类型：

- `package_type = 1`：`wgt` 热更新包
- `package_type = 0`：`apk` 整包

---

## 2. 调用顺序

### 2.1 管理端发布流程

前端管理端调用顺序如下：

1. 调用 `POST /v1/app_version/upload` 上传版本包
2. 从上传结果中拿到 `file_url`
3. 调用 `POST /v1/app_version/publish` 发布版本
4. 从发布结果中拿到 `id`
5. 客户端调用 `POST /v1/app_version/current` 获取最新版本信息
6. 从 `current.data.edition_url` 获取下载地址（格式为 `/v1/app_version/download?id={id}`）
7. 后续如果需要撤销该版本，调用 `POST /v1/app_version/revoke`，传入这个 `id`

说明：

- `upload` 返回的 `file_url` 是内部存储地址，不是给客户端直接下载的公网链接
- `publish` 时应将 `upload` 返回的 `file_url` 原样传给 `edition_url`
- `current` 接口返回给客户端的 `edition_url` 为业务下载地址，格式为 `/v1/app_version/download?id={id}`

### 2.2 客户端检查更新流程

客户端调用顺序如下：

1. 启动应用或进入设置页时，调用 `POST /v1/app_version/current`
2. 将本地版本号传给 `current_version_code`
3. 根据返回的 `need_update` 判断是否需要更新
4. 如果需要更新，读取返回的 `data.edition_url` 发起下载

---

## 3. 接口鉴权说明

### 3.1 需要鉴权

- `POST /v1/app_version/upload`
- `POST /v1/app_version/publish`
- `POST /v1/app_version/list`
- `POST /v1/app_version/revoke`

### 3.2 不要求鉴权

- `POST /v1/app_version/current`
- `GET /v1/app_version/download`

---

## 4. 接口说明

## 4.1 上传版本包

### 接口

`POST /v1/app_version/upload`

### 请求类型

`multipart/form-data`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | 版本包文件，仅支持 `.wgt` 或 `.apk` |

### 请求示例

```bash
curl -X POST 'http://{host}/v1/app_version/upload' \
  -H 'Authorization: Bearer {token}' \
  -F 'file=@/path/to/app_release.wgt'
```

### 响应示例

```json
{
  "status": 200,
  "message": "上传成功",
  "results": {
    "file_name": "app_release.wgt",
    "file_url": "minio://bucket/path/1745978400000_app_release.wgt"
  }
}
```

### 前端处理建议

- 保存 `results.file_url`
- 发布时将该值传给 `publish.edition_url`
- 不要直接把这个地址给客户端下载

---

## 4.2 发布版本

### 接口

`POST /v1/app_version/publish`

### 请求类型

`application/json`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `edition_name` | string | 是 | 版本名称，展示用，例如 `1.0.1` |
| `edition_version_code` | int | 是 | 版本号，程序比较用，必须递增 |
| `describe_zh` | string | 否 | 中文更新说明 |
| `describe_en` | string | 否 | 英文更新说明 |
| `describe_th` | string | 否 | 泰文更新说明 |
| `edition_url` | string | 是 | 上传接口返回的 `file_url` |
| `edition_force` | int | 否 | 是否强制更新，`0/1` |
| `package_type` | int | 否 | 包类型，`0=apk`，`1=wgt` |
| `edition_issue` | int | 否 | 是否发行，`0/1` |
| `edition_silence` | int | 否 | 是否静默更新，`0/1` |

### 请求示例

```json
{
  "edition_name": "1.0.1",
  "edition_version_code": 2,
  "describe_zh": "1. 修复已知问题<br>2. 优化用户体验",
  "describe_en": "1. Fixed known issues<br>2. Improved user experience",
  "describe_th": "1. แก้ไขปัญหาที่ทราบ<br>2. ปรับปรุงประสบการณ์ผู้ใช้",
  "edition_url": "minio://bucket/path/1745978400000_app_release.wgt",
  "edition_force": 1,
  "package_type": 1,
  "edition_issue": 1,
  "edition_silence": 0
}
```

### 响应示例

```json
{
  "status": 200,
  "message": "版本发布成功",
  "results": {
    "id": 12,
    "edition_version_code": 2,
    "edition_name": "1.0.1",
    "describe_zh": "1. 修复已知问题<br>2. 优化用户体验",
    "describe_en": "1. Fixed known issues<br>2. Improved user experience",
    "describe_th": "1. แก้ไขปัญหาที่ทราบ<br>2. ปรับปรุงประสบการณ์ผู้ใช้",
    "edition_url": "minio://bucket/path/1745978400000_app_release.wgt",
    "package_type": 1,
    "status": 1
  }
}
```

### 注意事项

- `edition_version_code` 必须大于当前已发布版本
- `publish` 返回的 `results.id` 就是后续撤销时要用的版本 ID
- `package_type=1` 时，`edition_url` 必须指向 `.wgt`
- `package_type=0` 时，`edition_url` 必须指向 `.apk`

---

## 4.3 查询最新版本

### 接口

`POST /v1/app_version/current`

### 请求类型

`application/json`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `current_version_code` | int | 否 | 客户端当前版本号 |

### 请求示例

```json
{
  "current_version_code": 1
}
```

### 响应示例

```json
{
  "status": 200,
  "message": "查询成功",
  "need_update": 1,
  "data": {
    "id": 12,
    "describe_zh": "1. 修复已知问题<br>2. 优化用户体验",
    "describe_en": "1. Fixed known issues<br>2. Improved user experience",
    "describe_th": "1. แก้ไขปัญหาที่ทราบ<br>2. ปรับปรุงประสบการณ์ผู้ใช้",
    "edition_url": "/v1/app_version/download?id=12",
    "edition_force": 1,
    "package_type": 1,
    "edition_issue": 1,
    "edition_version_code": 2,
    "edition_name": "1.0.1",
    "edition_silence": 0
  }
}
```

### 字段说明

- `need_update = 1`：说明服务端版本大于客户端版本，需要更新
- `data.id`：版本 ID（即发布接口返回的 `results.id`）
- `data.edition_url`：客户端实际下载地址（代理下载地址），可直接用于下载
- `data.describe_zh/en/th`：前端根据当前语言选择对应说明展示

### 多语言展示建议

- 中文界面优先使用 `describe_zh`
- 英文界面优先使用 `describe_en`
- 泰文界面优先使用 `describe_th`
- 如果对应语言为空，可按产品策略回退到中文

---

## 4.4 下载版本包

### 接口

`GET /v1/app_version/download?id={id}`

### 鉴权

不要求鉴权

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | int | 是 | 版本 ID（`publish.results.id`） |

### 请求示例

```bash
curl -L 'http://{host}/v1/app_version/download?id=12' -o app_release.wgt
```

### 说明

- 只允许下载 `status=1`（已发布）版本
- 支持 `Range` 请求

---

## 4.5 查询版本列表

### 接口

`POST /v1/app_version/list`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 否 | 页码，默认 `1` |
| `page_size` | int | 否 | 每页条数，默认 `10` |
| `status` | int | 否 | `1=已发布`，`2=已撤销` |
| `edition_name` | string | 否 | 版本名称模糊查询 |
| `edition_version_code` | int | 否 | 版本号精确查询 |

### 请求示例

```json
{
  "page": 1,
  "page_size": 10,
  "status": 1
}
```

### 响应示例

```json
{
  "status": 200,
  "message": "查询成功",
  "results": {
    "data": [
      {
        "id": 12,
        "edition_name": "1.0.1",
        "edition_version_code": 2,
        "describe_zh": "1. 修复已知问题<br>2. 优化用户体验",
        "describe_en": "1. Fixed known issues<br>2. Improved user experience",
        "describe_th": "1. แก้ไขปัญหาที่ทราบ<br>2. ปรับปรุงประสบการณ์ผู้ใช้",
        "edition_url": "minio://bucket/path/1745978400000_app_release.wgt",
        "edition_force": 1,
        "package_type": 1,
        "edition_issue": 1,
        "edition_silence": 0,
        "status": 1
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

### 前端使用建议

- 管理台列表中直接保存每条记录的 `id`
- 点击撤销时，把该 `id` 传给撤销接口

---

## 4.6 撤销发布

### 接口

`POST /v1/app_version/revoke`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | int | 是 | 发布接口返回的版本 ID |
| `revoke_reason` | string | 否 | 撤销原因 |

### 请求示例

```json
{
  "id": 12,
  "revoke_reason": "发现版本包问题，先撤回"
}
```

### 响应示例

```json
{
  "status": 200,
  "message": "版本撤销成功",
  "results": {
    "id": 12,
    "status": 2
  }
}
```

### 说明

- 只有 `status=1` 的版本可以撤销
- 撤销后该版本不会再被 `current` 接口返回

---

## 5. 前端联调建议

### 5.1 管理台最小闭环

1. 上传 `.wgt` 或 `.apk`
2. 取回 `file_url`
3. 录入三语更新说明
4. 发布版本
5. 保存发布返回的 `id`
6. 列表页展示版本信息
7. 如需下架，调用撤销接口

### 5.2 客户端最小闭环

1. 启动时调用 `current`
2. 比较 `need_update`
3. 根据当前语言展示 `describe_zh/en/th`
4. 使用 `edition_url` 下载更新包
5. 根据 `edition_force`、`edition_silence` 决定交互方式

---

## 6. 特别注意

- `upload` 返回的是内部存储地址，供管理端继续发布，不是客户端直链
- `current` 返回的是对客户端可用的下载地址
- `publish` 的 `edition_version_code` 必须严格递增
- 撤销接口依赖 `publish.results.id`，前端不要丢掉这个字段
