# system-common 客户端版本管理技术方案

## 1. 背景与目标

当前客户端需要一个“热更新信息获取接口”，用于返回 `edition_version_code`、`edition_url`、`describe` 等字段，驱动 APK / WGT 的更新提示和安装流程。

注意：

- 本方案面向“客户端应用版本管理 / 热更新管理”
- 管理对象是 `apk`、`wgt` 等客户端安装包或热更新包
- 文档中提到 `sop_version_routes`，仅用于参考 `system_common` 现有代码组织方式

短期目标：

- 提供一个稳定的“当前可用版本”查询接口，返回前端约定格式。
- 支持后台手动发布版本，不需要先做复杂的发布后台页面。
- 支持版本撤销，避免误发版本后只能改库回滚。
- 文件存储复用现有 [`oss_manager.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/oss_manager/oss_manager.py)。

### 1.1 需求对齐结论

为满足你当前需求，第一期必须保证以下几点：

1. 必须有“获取热更新信息接口”，并且返回体里的 `data` 结构要兼容你给的字段定义。
2. 必须支持后台手工发布版本，发布时能维护：
   `edition_version_code`、`edition_url`、`describe`、`package_type`、`edition_force`、`edition_issue`、`edition_silence`、`edition_name`。
3. 必须支持撤销已发布版本，避免误发后只能改库。
4. `edition_url` 指向包文件下载地址，文件存储可复用 OSS。
5. 第一阶段默认 `package_type = 1`，即先支持 WGT 热更新。

因此，第一期收敛后的接口边界建议为：

- 客户端接口：`获取当前热更新信息`
- 管理端接口：`发布版本`
- 管理端接口：`撤销版本`
- 管理端辅助接口：`版本列表`

第一期设计原则：

- 先满足“单应用客户端热更新”场景
- 先不引入多应用、多平台、多渠道、多租户复杂度
- 先保证“可查、可发、可撤销”
- 文件上传复用 `oss_manager` 的小文件上传能力

中期目标：

- 支持版本发布历史留痕。
- 支持多端、多渠道、多包类型管理。
- 为后续“版本发布列表页 / 审批流 / 自动上架”保留扩展空间。


## 2. 现状分析

### 2.1 system-common 模块现状

`system_common` 当前已经具备较清晰的服务组织方式：

- 路由入口集中在 [`main.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common/main.py)
- 业务逻辑以 `xxx_routes.py` 形式拆分，如 [`sop_version_routes.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common/sop_version_routes.py)
- 数据访问主要通过 [`mysql_client.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common/mysql_client.py)
- 管理接口大多走 `@require_auth_dict()`，从用户信息中取 `tenant_id`

这意味着“客户端版本管理”也适合沿用同样模式：

- `version_routes.py` 负责业务逻辑
- `main.py` 挂接口
- `mysql_client.py` 增加版本表相关 CRUD
- 如需更强请求校验，可在 [`schema.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common/schema.py) 新增请求/响应模型

### 2.2 OSS 能力现状

[`OSSManager`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/oss_manager/oss_manager.py) 已具备：

- 小文件上传 `oss_upload`
- 大文件上传 `upload_large_file`
- 预签名 URL 生成
- 对象大小获取
- 文件下载

因此版本包文件存储不需要新造轮子，可以直接复用：

- 发布时上传 `.wgt` / `.apk`
- 第一阶段优先生成并保存可直接下载的 `edition_url`
- 如后续需要加强追踪，再补充保存 `oss_uri`


## 3. 总体设计思路

建议不要只做一个“写死返回值接口”，而是抽象成“客户端版本发布管理”能力。

从需求满足角度看，接口分两类：

- 客户端消费接口：只负责“取当前生效版本”
- 管理端维护接口：负责“发布 / 撤销 / 查询历史”

至少包含 3 个核心接口：

1. `获取当前生效版本`
2. `发布版本`
3. `撤销版本`

这样做的原因：

- 只做查询接口，后续每次发版都要手动改代码或直接改库，不可控。
- 增加发布接口后，可以先手工调用接口发版，不必等管理页面。
- 增加撤销接口后，误发版本能快速恢复，不需要后端人肉修数据。

建议采用“两层模型”：

- `版本记录表`：保存每一次发布的完整元数据
- `当前生效版本`：通过表中状态字段识别，不单独硬编码在配置文件中


## 4. 数据模型设计

第一期建议新增最小表：`sp_app_version`

### 4.1 第一阶段最小字段

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint PK | 主键 |
| `edition_name` | varchar(64) | 展示版本号，如 `1.0.1` |
| `edition_version_code` | int | 版本比较号，范围 `2 ~ 2147483647` |
| `describe` | text | 更新说明，允许 `<br>` |
| `edition_force` | tinyint | 是否强制更新：0/1 |
| `package_type` | tinyint | 0=整包，1=wgt |
| `edition_issue` | tinyint | 是否发行：0/1 |
| `edition_silence` | tinyint | 是否静默更新：0/1 |
| `edition_url` | varchar(1024) | 对外下载地址 |
| `status` | tinyint | 1=已发布，2=已撤销 |
| `published_at` | datetime | 发布时间 |
| `published_by` | varchar(64) | 发布人 |
| `revoked_at` | datetime | 撤销时间 |
| `revoked_by` | varchar(64) | 撤销人 |
| `revoke_reason` | varchar(255) | 撤销原因 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### 4.2 第一阶段索引建议

- 唯一索引：`uk_edition_version_code (edition_version_code)`
- 查询索引：`idx_current_release (status, edition_issue, edition_version_code)`

### 4.3 状态定义

- `1`：已发布
- `2`：已撤销

第一期不建议引入“草稿”状态，减少复杂度。

这里保留“发布”和“发行”区分：

- `status=1` 表示这条记录已被后台发布
- `edition_issue=1` 表示客户端允许感知它

这样审核期可以保留已发布记录，但通过 `edition_issue=0` 控制客户端不弹更新。

### 4.4 后续扩展字段

以下字段第一期可以不做，等明确有多端/多应用场景后再扩展：

- `app_code`
- `platform`
- `channel`
- `tenant_id`
- `oss_uri`
- `package_name`
- `package_size`
- `package_md5`
- `min_support_version_code`
- `extra_meta`


## 5. 接口设计

## 5.1 获取当前热更新信息

### 接口建议

- `POST /v1/app_version/current`

说明：

- 为了兼容当前 `system_common` 大部分接口风格，建议仍使用 `POST + Body`
- 该接口默认给客户端调用，建议可不鉴权，或只做轻鉴权
- 该接口的返回结构应优先满足前端热更新需求，而不是完全套用 `system_common` 现有 `results` 风格

### 请求参数

```json
{
  "current_version_code": 1
}
```

### 返回格式

这里建议**严格按前端当前需要的 `data` 结构返回**，避免再做字段转换。

```json
{
  "status": 200,
  "message": "查询成功",
  "need_update": 1,
  "data": {
    "describe": "1. 修复已知问题<br>2. 优化用户体验",
    "edition_url": "https://wisdom-island.com/copybook/__UNI__858E0D5.wgt",
    "edition_force": 1,
    "package_type": 1,
    "edition_issue": 1,
    "edition_version_code": 2,
    "edition_name": "1.0.1",
    "edition_silence": 1
  }
}
```

当无需更新时建议返回：

```json
{
  "status": 200,
  "message": "当前已是最新版本",
  "need_update": 0,
  "data": {
    "describe": "",
    "edition_url": "",
    "edition_force": 0,
    "package_type": 1,
    "edition_issue": 0,
    "edition_version_code": 0,
    "edition_name": "",
    "edition_silence": 0
  }
}
```

### 查询规则

返回满足以下条件的最新一条记录：

- `status = 1`
- `edition_issue = 1`
- 按 `edition_version_code DESC` 取最新

然后与客户端 `current_version_code` 比较：

- 如果服务端版本号更大，`need_update=1`
- 否则 `need_update=0`

### 必须满足的字段契约

接口返回的 `data` 必须至少包含以下字段，字段名不建议改动：

- `describe`
- `edition_url`
- `edition_force`
- `package_type`
- `edition_issue`
- `edition_version_code`
- `edition_name`
- `edition_silence`


## 5.2 发布版本接口

### 接口建议

- `POST /v1/app_version/publish`

说明：

- 管理端调用，必须鉴权
- 前期可以不做页面，先通过 Postman / 内部脚本调用

### 请求参数建议

```json
{
  "edition_name": "1.0.1",
  "edition_version_code": 2,
  "describe": "1. 修复已知问题<br>2. 优化用户体验",
  "edition_force": 1,
  "package_type": 1,
  "edition_issue": 1,
  "edition_silence": 1,
  "edition_url": "https://wisdom-island.com/copybook/__UNI__858E0D5.wgt"
}
```

### 发布规则

1. `edition_version_code` 必须大于当前已发布版本
2. `edition_version_code` 必须全局唯一
3. 如果 `package_type=1`，应校验 `edition_url` 指向 `.wgt`
4. 如果 `package_type=0`，应校验后缀为 `.apk` 或市场地址
5. 发布成功后记录 `published_at/published_by`

### 发布接口返回建议

```json
{
  "status": 200,
  "message": "版本发布成功",
  "results": {
    "id": 1001,
    "edition_version_code": 2,
    "edition_name": "1.0.1",
    "edition_url": "https://wisdom-island.com/copybook/__UNI__858E0D5.wgt",
    "package_type": 1,
    "status": 1
  }
}
```

### 建议增强

支持两种发布方式：

- 只传 `edition_url`，适合后端已知文件位置
- 先通过上传接口拿到 `edition_url`，再调用发布接口落库

第二种更推荐，因为文件来源更可控。


## 5.3 撤销版本接口

### 接口建议

- `POST /v1/app_version/revoke`

### 请求参数

```json
{
  "id": 1001,
  "revoke_reason": "发现热更新包存在启动异常"
}
```

### 撤销规则

1. 只能撤销 `status=1` 的版本
2. 撤销后更新为 `status=2`
3. 补充 `revoked_at/revoked_by/revoke_reason`
4. 不删除历史记录

这样客户端“当前版本查询接口”会自动回落到上一条仍满足 `status=1 and edition_issue=1` 的版本。

### 撤销接口返回建议

```json
{
  "status": 200,
  "message": "版本撤销成功",
  "results": {
    "id": 1001,
    "status": 2
  }
}
```


## 5.4 可选接口

从“满足当前需求”看，下面接口不是强制的，但建议第一期一起补上至少 `list`：

### 5.4.1 版本列表

- `POST /v1/app_version/list`

用途：

- 后续发布管理页面直接复用
- 查询历史发布、撤销记录

### 5.4.2 版本包上传

- `POST /v1/app_version/upload`

用途：

- 直接复用 `oss_manager`
- 第一阶段使用小文件上传能力 `oss_upload`
- 返回 `edition_url`，供发布接口写入数据库

这样发布接口只负责“元数据落库”，职责更清晰。


## 6. 推荐的最小实现范围

为了控制第一期复杂度，同时确保满足需求，建议第一阶段做以下 4 个接口：

1. `POST /v1/app_version/current`
2. `POST /v1/app_version/publish`
3. `POST /v1/app_version/revoke`
4. `POST /v1/app_version/list`

其中：

- `current`、`publish`、`revoke` 是需求必需
- `list` 是运维必需，强烈建议第一期一并做
- `upload` 接口可以第一期不开放成页面能力，但后端实现时建议预留
- 第一阶段如果包文件已经由别的方式上传，只需要传 `edition_url` 即可


## 7. 文件存储方案

## 7.1 复用 oss_manager

建议在 `system_common` 中新增一个轻量封装，比如：

- `version_package_routes.py`
- 或直接在 `version_routes.py` 中调用 `OSSManager`

建议存储路径规范：

```text
{dest_prefix}/app-version/{edition_version_code}/{filename}
```

示例：

```text
app-version/2/__UNI__858E0D5.wgt
```

优点：

- 目录清晰
- 按应用/平台/渠道/版本快速定位
- 后续可直接做生命周期管理

## 7.2 数据库存什么

第一期数据库最少只需要保存：

- `edition_url`

原因：

- `edition_url` 直接给客户端返回，避免每次动态拼接逻辑不一致

如果后端觉得追踪上传来源有必要，可以额外保存 `oss_uri`，但不是第一期必需。

若你们 OSS 对外是固定公网域名，发布时可将 `edition_url` 直接落为公网地址。
若是私有桶，则查询接口临时生成短期签名 URL，但这会带来“URL 失效”的问题，不太适合 App 热更新。

因此更推荐：

- 版本包放在可长期下载的静态域名或公网对象存储路径


## 8. 模块落点建议

### 8.1 文件建议

- 新增 [`version_routes.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common)
- 在 [`main.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common/main.py) 注册路由
- 在 [`mysql_client.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common/mysql_client.py) 增加版本管理表 CRUD
- 可选：在 [`schema.py`](/Users/codedan/local/project/intel/dfxh/stage2/dataprep/eap/src/comps/system_common/schema.py) 增加：
  - `AppVersionPublishRequest`
  - `AppVersionCurrentQueryRequest`
  - `AppVersionRevokeRequest`
  - `AppVersionPublicResponse`

### 8.2 路由风格建议

沿用当前 `system_common` 风格：

- `Body(..., embed=True)` 逐字段接收
- 管理类接口使用 `@require_auth_dict()`
- 查询结果统一返回：

```json
{
  "status": 200,
  "message": "xxx",
  "results": {}
}
```

注意：

这里建议区分两类接口的返回风格：

- `current`：优先满足客户端热更新字段契约，直接返回顶层 `data`
- `publish/revoke/list`：沿用 `system_common` 的 `results` 风格

推荐格式如下。

客户端查询接口：

```json
{
  "status": 200,
  "message": "查询成功",
  "need_update": 1,
  "data": {
    "...": "..."
  }
}
```

管理端接口：

```json
{
  "status": 200,
  "message": "操作成功",
  "results": {
    "...": "..."
  }
}
```


## 9. 关键业务规则

### 9.1 版本号规则

- `edition_version_code` 取值范围：`2 ~ 2147483647`
- 每次发布必须递增
- `edition_name` 仅展示用，不参与比较

### 9.2 更新策略规则

- `edition_force=1`：客户端必须升级后才能继续
- `edition_silence=1`：客户端可静默下载，下载完成后提示重启
- `package_type=1`：默认 WGT 热更新
- `package_type=0`：整包升级 APK / 市场

### 9.3 审核期开关

- `edition_issue=0` 时，接口可返回“无需更新”
- 避免审核阶段弹出热更新提示

### 9.4 撤销策略

撤销不是删除记录，而是：

- 更新状态
- 保留审计字段
- 当前版本接口自动回退到上一有效版本


## 10. 第一阶段实现建议

## 10.1 Phase 1

目标：

- 先把接口能力做通
- 先支持手动发布
- 不做管理页面

范围：

- 建表 `sp_app_version`
- 增加 `current/publish/revoke/list`
- `current` 返回结构严格满足前端 `data` 字段要求
- 先支持 `edition_url` 手工填入
- 包类型默认先用 `package_type=1`
- 文件存储复用 OSS 小文件上传能力 `oss_upload`

## 10.2 Phase 2

目标：

- 补齐上传与发布联动

范围：

- 增加 `upload` 接口
- 自动计算 `package_md5/package_size`
- 自动生成标准 OSS 路径

## 10.3 Phase 3

目标：

- 发布可视化与流程化

范围：

- 发布列表页
- 草稿 -> 发布 -> 撤销 流程
- 审计日志
- 支持灰度渠道


## 11. 我对你当前想法的建议

你的思路“获取接口 + 发布接口 + 发布撤销接口”是对的，而且已经覆盖了核心需求。

我建议在这个基础上再补一个“版本列表接口”，原因很简单：

- 没有列表接口，撤销时只能靠 `id` 或手工查库
- 后续做页面时一定还得补
- 成本很低，但能明显提升可运维性

在这个基础上，我建议再补一个“版本列表接口”，这样才是可运维的最小闭环：

1. `current`
2. `publish`
3. `revoke`
4. `list`


## 12. 推荐结论

推荐在 `system_common` 中新增“客户端版本发布管理”能力，而不是只做一个静态返回接口。

技术上建议：

- 用 MySQL 表维护版本记录
- 用 `status + edition_issue` 控制当前是否对客户端生效
- 用 `edition_version_code` 做唯一比较标准
- 用 `oss_manager` 管版本包存储和下载地址管理
- 前期先手工发版，不做页面
- `current` 接口返回结构严格按你给的 `data` 字段协议输出

这样第一期可以非常快落地，同时后续无论你要做发布页、渠道管理、灰度发布还是审计，都不用推倒重来。
