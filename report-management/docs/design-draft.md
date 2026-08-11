# 报告管理设计草案

## 目标

在 RuoYi-Cloud 的 `ruoyi-ui` 中新增报告管理菜单，展示跑批生成的 DOCX 报告。用户可以查询、搜索、在线预览、下载初始报告，也可以下载后修改并上传新版本；每个版本上传后都会异步触发 DeepSeek AI 审核，列表默认展示最新版本的最新审核结果。

## 已确认规则

- 报告主记录唯一键为 `systemId + title + report_month`。
- 页面以报告列表为主，不独立展示批次。
- 初始报告路径继续从 `capability_report_log.report_data.data` 获取，并同步建立初始报告版本。
- 用户上传的修改报告统一保存到后端文件服务目录，例如 `/appdata/.../uploaded_reports/`。
- 上传报告不覆盖旧文件，每次上传生成新的报告版本。
- 审核异步执行：上传或批次注册先成功返回，版本状态显示为“审核中”，后台完成后更新结果。
- 第一版 AI 审核只处理 DOCX 文字、表格和章节结构，不处理图片或图表语义。
- 每个版本可以有多条审核记录，页面默认展示最新审核记录。
- 报告列表默认展示最新版本的最新审核结果。
- 审核不通过后，用户可以持续上传新版本，直到审核通过。
- 审核通过后仍允许上传新版本；新版本会重新进入审核流程。
- 页面无鉴权公开访问。
- DOCX 在线预览使用 `@vue-office/docx`，点击预览时打开新浏览器 tab。
- 前端放在 RuoYi-Cloud 的 `ruoyi-ui` 下，后端使用 Python。
- 当前已有 Python 文件服务后续会下线；新报告管理 Python 后端必须自包含上传、预览、下载和文件存储能力，不能把旧文件服务作为运行时依赖。
- 旧文件服务的上传语义是同名替换；新报告管理后端不能沿用该语义，所有上传必须创建新的报告版本并保留历史文件。
- 审核提示词每次修改都生成新版本，审核记录保存当时使用的提示词版本。
- 审核通过/不通过由模型直接输出，后端只做 JSON 格式校验和状态落库。
- 报告月份保存为 `YYYY年MM月` 字符串格式，前端使用月份选择器录入或筛选。
- Python 后端作为新服务单独部署；允许参考当前文件服务代码片段，但不能复用旧服务运行时。

## 推荐数据模型

### `capability_report_log`

作为报告主记录表，保留当前跑批写入入口，并调整唯一键。

建议保留字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 报告主记录 ID |
| `systemId` | 系统编码 |
| `title` | 报告标题 |
| `report_month` | 报表月份 |
| `report_data` | 初始报告文件引用，例如 `{"data": "/appdata/...docx", "type": "file"}` |
| `meta_data` | 元数据，第一版可为 `NULL` |
| `llm_audit_code` | 兼容旧字段，后续可同步最新审核状态 |
| `llm_audit_rs` | 兼容旧字段，后续可同步最新审核结果摘要 |
| `jira_id` | 兼容现有字段 |
| `create_time` | 创建时间 |

建议索引：

```sql
UNIQUE KEY `uk_report_identity` (`systemId`, `title`, `report_month`)
```

### `capability_report_version`

保存初始报告和每次上传报告。

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | bigint | 版本 ID |
| `report_id` | int | 关联 `capability_report_log.id` |
| `version_no` | int | 版本号，初始报告为 1 |
| `version_type` | varchar(16) | `initial` 或 `uploaded` |
| `file_name` | varchar(255) | 展示文件名 |
| `file_path` | varchar(1024) | 服务端真实文件路径 |
| `file_size` | bigint | 文件大小 |
| `audit_status` | varchar(32) | 最新审核状态 |
| `uploader` | varchar(64) | 上传人，初始报告可为 `批次任务` |
| `source` | varchar(32) | `batch` 或 `upload` |
| `create_time` | datetime(3) | 创建时间 |

建议索引：

```sql
UNIQUE KEY `uk_report_version` (`report_id`, `version_no`)
KEY `idx_report_latest` (`report_id`, `create_time`)
```

### `capability_report_audit`

保存每次 AI 审核记录。

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | bigint | 审核记录 ID |
| `report_id` | int | 报告主记录 ID |
| `version_id` | bigint | 报告版本 ID |
| `status` | varchar(32) | `pending`、`running`、`passed`、`failed`、`error` |
| `summary` | json | 总结论，供列表展示 |
| `result_data` | json | 检查点数组，结构兼容现有 `llm_audit_rs.data` |
| `prompt_id` | bigint | 使用的提示词 ID |
| `prompt_version` | int | 使用的提示词版本 |
| `model_name` | varchar(64) | DeepSeek 模型名 |
| `error_message` | text | 调用失败原因 |
| `started_at` | datetime(3) | 开始审核时间 |
| `finished_at` | datetime(3) | 完成审核时间 |
| `create_time` | datetime(3) | 创建时间 |

### `capability_report_audit_prompt`

保存可配置审核提示词。

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | bigint | 提示词 ID |
| `name` | varchar(128) | 提示词名称 |
| `prompt_content` | text | 提示词正文 |
| `version` | int | 提示词版本 |
| `enabled` | tinyint | 是否启用 |
| `model_name` | varchar(64) | 默认模型名 |
| `create_time` | datetime(3) | 创建时间 |
| `update_time` | datetime(3) | 更新时间 |

## 后端接口草案

### 报告列表

```text
GET /api/report-management/reports
```

查询参数：

| 参数 | 说明 |
| --- | --- |
| `systemId` | 系统编码，模糊查询 |
| `title` | 标题，模糊查询 |
| `reportMonth` | 报表月份 |
| `auditStatus` | 最新版本审核状态 |
| `pageNum` | 页码 |
| `pageSize` | 每页数量 |

返回每份报告的主信息、最新版本、最新审核总结。

### 报告详情

```text
GET /api/report-management/reports/{reportId}
```

返回报告主信息、所有版本、每个版本的最新审核结果。

### 批次注册初始报告并发起审核

```text
POST /api/report-management/reports/register
```

请求示例：

```json
{
  "systemId": "credit-card-center",
  "title": "中信银行信用卡中心授权交易资源分析报告",
  "reportMonth": "2025年08月",
  "filePath": "/appdata/aiops_inspect/B-plan/data/docfile_output/中信银行信用卡中心授权交易资源分析报告(2025年08月).docx",
  "source": "batch"
}
```

行为：

- 按 `systemId + title + reportMonth` 创建或更新报告主记录。
- 如果初始版本不存在，则创建 `version_no = 1` 的初始版本。
- 创建审核记录并异步执行 DeepSeek 审核。

### 上传新版本

```text
POST /api/report-management/reports/{reportId}/versions
```

请求：`multipart/form-data`

| 字段 | 说明 |
| --- | --- |
| `file` | DOCX 文件 |
| `uploader` | 上传人，第一版可默认 `未知用户` |

行为：

- 校验 DOCX 基本格式。
- 生成新版本号。
- 保存到上传目录，不覆盖旧文件；即使用户上传同名文件，也必须生成新的服务端文件名和新的版本记录。
- 创建审核记录并异步执行。

### 预览指定版本

```text
GET /api/report-management/versions/{versionId}/preview
```

返回 DOCX 二进制流，前端新 tab 页面使用 `@vue-office/docx` 渲染。

### 下载指定版本

```text
GET /api/report-management/versions/{versionId}/download
```

返回 DOCX 附件下载。

### 审核详情

```text
GET /api/report-management/audits/{auditId}
```

返回审核总结、检查点明细、提示词版本、模型名和错误信息。

### 提示词配置

```text
GET /api/report-management/audit-prompts/active
PUT /api/report-management/audit-prompts/{promptId}
```

第一版可以只支持查看和修改当前启用提示词。

## 前端页面草案

### 菜单

建议菜单名称：`报告管理`

### 报告列表页

能力：

- 按系统编码、标题、月份、审核状态查询。
- 展示系统编码、标题、月份、最新版本号、最新审核状态、最新审核结论、创建时间、更新时间。
- 操作：详情、预览最新版本、下载最新版本、上传新版本。

### 报告详情页

能力：

- 展示报告主信息。
- 展示版本列表。
- 每个版本支持预览、下载、查看审核详情。
- 最新版本支持继续上传新版本。

### DOCX 预览页

能力：

- 路由携带 `versionId`。
- 页面加载后调用 preview 接口。
- 使用 `@vue-office/docx` 渲染。
- 从列表和详情点击预览时新开 tab。

### 审核提示词页面

第一版可作为简单配置页：

- 展示当前启用提示词。
- 修改后生成新的提示词版本，并把新版本设置为启用。

## AI 审核流程

1. 创建报告版本。
2. 创建审核记录，状态为 `pending`。
3. 后台任务将状态改为 `running`。
4. 解析 DOCX 文字、表格和章节结构。
5. 读取当前启用提示词。
6. 调用 DeepSeek API。
7. 要求模型输出结构化 JSON。
8. 写入 `summary` 和 `result_data`。
9. 更新审核记录状态，并同步版本的 `audit_status`。
10. 可选同步 `capability_report_log.llm_audit_code` 和 `llm_audit_rs`，兼容旧查询。

## 已定稿实现决策

1. 提示词修改每次生成新版本，不覆盖旧提示词版本。
2. 审核通过/不通过由模型直接输出，后端只做 JSON 格式校验。
3. 报告月份固定保存为 `YYYY年MM月`。
4. Python 后端作为新服务单独部署；允许参考当前文件服务的实现思路，但不能依赖旧服务继续存在。
