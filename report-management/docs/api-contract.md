# 报告管理接口契约草案

Base path:

```text
/api/report-management
```

## 状态枚举

审核状态：

| 值 | 中文展示 | 说明 |
| --- | --- | --- |
| `pending` | 待审核 | 审核记录已创建，尚未开始 |
| `running` | 审核中 | 后台正在解析 DOCX 或调用模型 |
| `passed` | 审核通过 | 模型输出通过 |
| `failed` | 审核不通过 | 模型输出不通过 |
| `error` | 审核失败 | 系统异常或模型调用失败 |

版本类型：

| 值 | 中文展示 |
| --- | --- |
| `initial` | 初始版本 |
| `uploaded` | 上传版本 |

## 报告列表

```text
GET /api/report-management/reports
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `systemId` | string | 否 | 系统编码模糊查询 |
| `title` | string | 否 | 标题模糊查询 |
| `reportMonth` | string | 否 | 报表月份，格式 `YYYY年MM月` |
| `auditStatus` | string | 否 | 最新版本最新审核状态 |
| `pageNum` | integer | 否 | 默认 1 |
| `pageSize` | integer | 否 | 默认 10 |

响应示例：

```json
{
  "rows": [
    {
      "id": 1,
      "systemId": "credit-card-center",
      "title": "中信银行信用卡中心授权交易资源分析报告",
      "reportMonth": "2025年08月",
      "latestVersionId": 10,
      "latestVersionNo": 2,
      "latestVersionType": "uploaded",
      "latestAuditId": 99,
      "latestAuditStatus": "failed",
      "latestAuditConclusion": "不通过",
      "latestAuditSuggestion": "请修正系统概述与性能分析小结中的ES服务器数量",
      "createTime": "2026-08-11 10:30:00"
    }
  ],
  "total": 1
}
```

## 报告详情

```text
GET /api/report-management/reports/{reportId}
```

响应示例：

```json
{
  "id": 1,
  "systemId": "credit-card-center",
  "title": "中信银行信用卡中心授权交易资源分析报告",
  "reportMonth": "2025年08月",
  "versions": [
    {
      "id": 9,
      "versionNo": 1,
      "versionType": "initial",
      "fileName": "中信银行信用卡中心授权交易资源分析报告(2025年08月).docx",
      "fileSize": 72314,
      "auditStatus": "failed",
      "uploader": "批次任务",
      "source": "batch",
      "createTime": "2026-08-11 10:30:00",
      "latestAuditId": 88,
      "latestAuditConclusion": "不通过"
    },
    {
      "id": 10,
      "versionNo": 2,
      "versionType": "uploaded",
      "fileName": "中信银行信用卡中心授权交易资源分析报告-修订版.docx",
      "fileSize": 74200,
      "auditStatus": "running",
      "uploader": "未知用户",
      "source": "upload",
      "createTime": "2026-08-11 11:20:00",
      "latestAuditId": 99,
      "latestAuditConclusion": "审核中"
    }
  ]
}
```

## 注册初始报告并发起审核

给跑批任务调用。接口必须幂等：同一个 `systemId + title + reportMonth` 的初始版本已存在时，不重复创建版本，可按需重新发起审核。

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

响应示例：

```json
{
  "reportId": 1,
  "versionId": 9,
  "auditId": 88,
  "auditStatus": "pending"
}
```

## 上传并登记初始报告

供跑批任务与报告中心不在同一台服务器时调用。每份报告单独请求；接口将 DOCX 保存到报告中心的初始报告目录，再登记初始版本并创建异步审核任务。

同一个 `systemId + title + reportMonth` 已存在时，不新增报告或初始版本，但会将初始版本更新为本次上传的文件并重新创建审核任务。服务端使用唯一存储文件名，不会覆盖之前上传的同名文件。

```text
POST /api/report-management/reports/register-upload
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | DOCX 文件，当前服务统一限制不超过 50 MB |
| `systemId` | string | 是 | 系统编码 |
| `title` | string | 是 | 中文报告标题 |
| `reportMonth` | string | 是 | 报表月份，格式 `YYYY年MM月` |
| `jiraId` | string | 否 | JIRA 任务号 |
| `source` | string | 否 | 默认 `batch` |

调用示例：

```bash
curl -X POST http://localhost:5010/api/report-management/reports/register-upload \
  -F 'file=@/path/to/性能容量报告.docx' \
  -F 'systemId=credit-card-center' \
  -F 'title=中信银行信用卡中心授权交易资源分析报告' \
  -F 'reportMonth=2025年08月' \
  -F 'jiraId=容量审核-202508-001'
```

响应与 `POST /reports/register` 一致：

```json
{
  "reportId": 1,
  "versionId": 9,
  "auditId": 88,
  "auditStatus": "pending"
}
```

## 上传新版本并发起审核

同名文件不得覆盖旧文件。后端必须生成新的服务端文件名和新的版本号。

```text
POST /api/report-management/reports/{reportId}/versions
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | DOCX 文件 |
| `uploader` | string | 否 | 上传人，默认 `未知用户` |

响应示例：

```json
{
  "reportId": 1,
  "versionId": 10,
  "versionNo": 2,
  "auditId": 99,
  "auditStatus": "pending"
}
```

## 预览版本

```text
GET /api/report-management/versions/{versionId}/preview
```

返回 DOCX 二进制流：

```text
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

## 下载版本

```text
GET /api/report-management/versions/{versionId}/download
```

返回 DOCX 附件。

## 审核详情

```text
GET /api/report-management/audits/{auditId}
```

响应示例：

```json
{
  "id": 99,
  "status": "failed",
  "summary": {
    "结论": "不通过",
    "问题数量": 1,
    "建议": "请修正系统概述与性能分析小结中的ES服务器数量"
  },
  "resultData": {
    "data": [
      {
        "检查点": "检测章节应用指标统计与分析是否空缺",
        "分析结果": "应用指标统计与分析章节包含交易量趋势分析和交易平均响应时间与交易成功率，内容完整，无空缺"
      }
    ]
  },
  "promptId": 1,
  "promptVersion": 3,
  "modelName": "deepseek-chat",
  "errorMessage": null,
  "startedAt": "2026-08-11 11:20:01",
  "finishedAt": "2026-08-11 11:20:35"
}
```

## 审核过程事件

前端在审核过程弹窗打开期间按 `afterId` 增量轮询。事件已持久化，刷新页面后可恢复查看。

```text
GET /api/report-management/audits/{auditId}/events?afterId=0
```

响应示例：

```json
{
  "auditId": 99,
  "status": "running",
  "events": [
    {
      "id": 101,
      "type": "system",
      "phase": "extracting",
      "content": "正在解析DOCX中的章节、正文和表格",
      "createTime": "2026-08-12 10:15:01"
    },
    {
      "id": 102,
      "type": "model",
      "phase": "streaming",
      "content": "模型当前生成的审核内容片段",
      "createTime": "2026-08-12 10:15:03"
    }
  ],
  "lastEventId": 102,
  "finishedAt": null,
  "errorMessage": null
}
```

事件类型：

| 值 | 说明 |
| --- | --- |
| `system` | 排队、文档解析、模型调用和结果校验等系统阶段 |
| `model` | 大模型流式输出片段 |
| `result` | 审核完成结论 |
| `error` | 审核执行异常 |

## 查看当前启用提示词

```text
GET /api/report-management/audit-prompts/active
```

## 修改提示词

修改提示词必须生成新版本，并启用新版本。

```text
POST /api/report-management/audit-prompts
```

请求示例：

```json
{
  "name": "默认审核提示词",
  "promptContent": "请根据以下检查点审核性能容量报告，并输出JSON...",
  "modelName": "deepseek-chat"
}
```
