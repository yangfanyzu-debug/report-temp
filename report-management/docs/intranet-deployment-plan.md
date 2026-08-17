# 报告中心内网部署方案

## 1. 文档目的

本文档用于指导报告中心在内网环境中的部署和联调。当前采用批次服务器、报告中心服务和 RuoYi 前端分机部署的方式，服务器之间网络已经互通，接口暂不配置 Token。

## 2. 部署范围

| 服务器 | IP | 部署内容 | 主要职责 |
| --- | --- | --- | --- |
| 批次服务器 | `10.2.64.36` | 现有跑批任务 | 生成 DOCX，并调用上传登记接口 |
| 报告中心服务器 | `10.8.64.110` | Python API、AI 审核 Worker、报告文件目录 | 文件存储、报告管理、异步 AI 审核、数据库访问 |
| 前端服务器 | `10.8.64.107` | `ruoyi-ui`、Nginx | 提供报告管理页面并反向代理报告中心 API |

MySQL 地址沿用实际内网数据库配置，只要求 `10.8.64.110` 可以访问。批次服务器和前端服务器不直接连接报告数据库。

## 3. 总体架构

```text
                    multipart/form-data
批次服务器                                   报告中心服务器
10.2.64.36  --------------------------------> 10.8.64.110:5010
生成 DOCX                                    Python API
                                             AI 审核 Worker
                                             DOCX 文件目录
                                             MySQL / 大模型接口
                                                     ^
                                                     |
                                           HTTP 反向代理
                                                     |
用户浏览器  ------------------------------> 10.8.64.107
                                           ruoyi-ui + Nginx
```

核心原则：

- 批次上传流量直接进入 `10.8.64.110`，不经过前端服务器。
- 浏览器统一访问 `10.8.64.107`，报告接口由 Nginx 转发至 `10.8.64.110`。
- 初始报告和人工上传版本均保存在报告中心服务器。
- 报告登记成功后立即返回，AI 审核由 Worker 异步完成。
- 报告唯一标识为 `systemId + title + report_month`。
- 同名文件使用唯一服务端文件名保存，不覆盖历史版本。

## 4. 业务调用流程

### 4.1 批次生成初始报告

1. `10.2.64.36` 完成跑批并生成 DOCX。
2. 批次程序调用 `10.8.64.110` 的文件上传登记接口。
3. Python API 将文件写入初始报告目录，并写入报告、版本及审核任务记录。
4. 接口返回 `reportId`、`versionId`、`auditId` 和 `pending` 状态。
5. Worker 获取待处理任务，提取 DOCX 的文字、表格和结构后调用大模型。
6. 审核结果写入数据库，用户刷新页面或由页面轮询获取最新状态。

### 4.2 用户查看和修改报告

1. 用户通过 `10.8.64.107` 进入报告管理页面。
2. 查询、详情、预览和下载请求经 Nginx 转发至 `10.8.64.110:5010`。
3. 用户上传修改后的 DOCX 时，后端创建 `v2`、`v3` 等新版本，不覆盖原始文件。
4. 每个新版本自动创建独立的异步审核任务。
5. AI 审核工作台展示左侧 DOCX 和右侧各版本审核记录及对话。

## 5. 报告中心服务器部署

### 5.1 目录规划

```text
/opt/report-management/backend
/appdata/report-management/initial_reports
/appdata/report-management/uploaded_reports
```

目录用途：

- `initial_reports`：保存批次上传的初始报告。
- `uploaded_reports`：保存用户在页面上传的后续版本。
- `backend`：保存 Python API、Worker、虚拟环境及 `.env`。

运行服务的系统用户必须拥有两个文件目录的读写权限。

### 5.2 Python 服务

API 默认监听：

```text
0.0.0.0:5010
```

部署两个 systemd 服务：

```text
report-management-api.service
report-management-worker.service
```

API 使用 Gunicorn 启动，Worker 独立轮询待审核任务。两者使用同一份 `/opt/report-management/backend/.env`。

### 5.3 环境变量

```dotenv
REPORT_UPLOAD_DIR=/appdata/report-management/uploaded_reports
REPORT_INITIAL_REPORT_DIR=/appdata/report-management/initial_reports
REPORT_PUBLIC_API_PREFIX=/report-management-api

REPORT_MYSQL_HOST=<内网MySQL地址>
REPORT_MYSQL_PORT=3306
REPORT_MYSQL_USER=<数据库用户>
REPORT_MYSQL_PASSWORD=<数据库密码>
REPORT_MYSQL_DATABASE=ry-cloud

ARK_API_URL=<大模型接口地址>
ARK_MODEL=<模型名称>
ARK_API_KEY=<API Key>

REPORT_WORKER_INTERVAL_SECONDS=15
```

数据库密码和大模型 API Key 只配置在服务器 `.env`，不得写入源码或部署文档。

### 5.4 必要网络条件

`10.8.64.110` 需要能够访问：

- MySQL 服务地址及端口。
- 配置的大模型 API 地址；如果内网不能访问公网，应替换为内网大模型网关地址。
- `10.8.64.107` 发起的 API 请求。
- `10.2.64.36` 发起的 DOCX 上传请求。

## 6. 前端服务器配置

在 `10.8.64.107` 构建并部署实际 `ruoyi-ui` 静态文件。报告中心接口使用以下 Nginx 代理：

```nginx
location /prod-api/report-management-api/ {
    client_max_body_size 50m;
    proxy_connect_timeout 10s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    proxy_pass http://10.8.64.110:5010/api/report-management/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

浏览器始终访问 `10.8.64.107`，无需直接访问 `10.8.64.110`，也不需要额外配置 CORS。

## 7. 批次上传接口

批次服务器调用：

```text
POST http://10.8.64.110:5010/api/report-management/reports/register-upload
Content-Type: multipart/form-data
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `file` | 是 | DOCX 文件，最大 50 MB |
| `systemId` | 是 | 系统编码 |
| `title` | 是 | 中文报告标题 |
| `reportMonth` | 是 | 报表月份，格式 `YYYY年MM月` |
| `jiraId` | 否 | 对应 JIRA 任务号 |
| `source` | 否 | 建议固定为 `batch` |

调用示例：

```bash
curl --fail --show-error \
  --connect-timeout 10 \
  --max-time 300 \
  -X POST 'http://10.8.64.110:5010/api/report-management/reports/register-upload' \
  -F 'file=@/appdata/batch/output/性能容量报告.docx' \
  -F 'systemId=credit-card-center' \
  -F 'title=中信银行信用卡中心授权交易资源分析报告' \
  -F 'reportMonth=2026年08月' \
  -F 'jiraId=CAPACITY-001' \
  -F 'source=batch'
```

成功响应示例：

```json
{
  "reportId": 1,
  "versionId": 1,
  "auditId": 1,
  "auditStatus": "pending"
}
```

批量上传建议：

- 每份报告单独请求，平均 `3～5 MB` 的文件建议并发数控制在 `2～4`。
- 仅对网络异常、连接超时和 `5xx` 响应进行有限次数重试。
- 对 `4xx` 响应记录错误信息并停止重试，避免错误参数反复提交。
- 批次日志保存报告路径、系统编码、月份、HTTP 状态码及响应中的 `auditId`。

## 8. 数据库部署

部署前先执行预检查脚本，确认唯一键冲突、现有索引和目标表状态；确认无误后执行迁移脚本。

迁移内容包括：

- 将报告唯一键调整为 `systemId + title + report_month`。
- 创建报告版本、审核记录、提示词、检查点、审核事件和 Agent 消息等表。
- 保留 `capability_report_log` 作为报告主记录。

数据库迁移属于写操作，必须先备份并在维护窗口执行。

## 9. 部署顺序

1. 确认 `10.8.64.110` 到 MySQL 和大模型 API 的连通性。
2. 备份数据库并完成数据库预检查和迁移。
3. 在 `10.8.64.110` 创建目录、安装 Python 环境并配置 `.env`。
4. 启动 API 和 Worker，完成本机健康检查。
5. 在 `10.8.64.107` 部署前端静态资源并更新 Nginx 代理。
6. 从 `10.2.64.36` 上传一份测试 DOCX，验证初始报告登记和异步审核。
7. 在浏览器验证查询、预览、下载、上传新版本和 AI 审核工作台。
8. 测试通过后再切换正式批次调用。

## 10. 验收检查

### 10.1 报告中心服务器

```bash
curl -fsS http://127.0.0.1:5010/health
curl -fsS http://127.0.0.1:5010/api/report-management/reports
systemctl status report-management-api
systemctl status report-management-worker
```

### 10.2 批次服务器

```bash
curl -fsS http://10.8.64.110:5010/health
```

完成一份测试报告上传后，确认：

- 接口返回 `pending` 和有效的 `reportId/versionId/auditId`。
- 初始报告目录出现唯一命名的 DOCX 文件。
- 页面能查询到对应报告。
- 审核状态能够从“审核中”更新为最终结果。
- DOCX 可以在线预览和下载。
- 上传新版本后版本号递增，旧版本仍可查看。

### 10.3 前端服务器

```bash
curl -fsS http://127.0.0.1/prod-api/report-management-api/reports
nginx -t
```

## 11. 故障处理与回退

- 前端异常：恢复 `10.8.64.107` 上一次静态文件备份和 Nginx 配置。
- API 异常：恢复 `/opt/report-management/backend` 上一次发布目录并重启 API。
- Worker 异常：可单独停止 Worker；已登记报告仍可查询和下载，待审核任务保留在数据库中。
- 大模型不可达：报告登记和文件上传不受影响，审核任务记录失败原因，恢复后可重新触发审核。
- 数据库迁移异常：停止服务并依据迁移前备份回退，禁止通过删除业务表进行临时处理。

## 12. 当前边界

- 当前不配置接口 Token，依赖三台服务器所在内网的访问边界。
- 第一版 AI 审核处理 DOCX 的文字、表格和文档结构，不分析图片及图表语义。
- 报告文件当前保存在 `10.8.64.110` 本地磁盘；后续文件量明显增长时，可再评估共享存储或对象存储。
- 本文档提供部署方案，不代表已经在上述三台内网服务器执行部署。
