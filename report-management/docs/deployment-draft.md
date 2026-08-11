# 部署草案

本文档是草案，不直接执行。涉及远端部署、重启、Nginx 修改或数据库迁移前，需要先确认影响范围并获得明确批准。

## 目标目录

建议新服务独立部署：

```text
/opt/report-management/backend
/appdata/report-management/uploaded_reports
```

## 后端环境变量

参考：

```text
report-management/backend/.env.example
```

API Key 只写入远端 `.env`，不进入 Git。

## Python API 服务

建议 systemd：

```text
report-management/deploy/systemd/report-management-api.service
```

默认监听：

```text
0.0.0.0:5010
```

## AI 审核 Worker

建议 systemd：

```text
report-management/deploy/systemd/report-management-worker.service
```

worker 默认每 15 秒处理一条 `pending` 审核记录。单次调试命令：

```bash
python run_worker.py --once
```

## Nginx

建议路径：

```text
/prod-api/report-management-api/
```

草案配置：

```text
report-management/deploy/nginx/report-management.conf
```

## 数据库

草案 SQL：

```text
report-management/db/schema-draft.sql
```

建议实际使用迁移脚本：

```text
report-management/db/migrations/001_precheck_report_management.sql
report-management/db/migrations/001_apply_report_management.sql
report-management/db/run-remote-migration.sh
```

预检查只读：

```bash
report-management/db/run-remote-migration.sh precheck
```

执行迁移会修改远端 `ry-cloud` 数据库：

```bash
report-management/db/run-remote-migration.sh apply
```

`apply` 的影响：

- 检查 `systemId + title + report_month` 是否有重复；有重复时中止。
- 创建 `capability_report_version`。
- 创建 `capability_report_audit`。
- 创建 `capability_report_audit_prompt`。
- 将 `capability_report_log` 的唯一键调整为 `systemId + title + report_month`。
- 插入默认启用审核提示词。
- 根据 `capability_report_log.report_data.data` 回填初始版本。
- 为初始版本创建 `pending` 审核记录。

执行前必须先检查：

- `capability_report_log` 是否已有重复的 `systemId + title + report_month`。
- 远端现有索引名是否为 `idx_systemId`。
- 是否已有同名新表。
- JSON 字段在 MySQL 5.7 上的兼容性。

## 验证命令

```bash
curl -fsS http://127.0.0.1:5010/health
curl -fsS http://127.0.0.1:5010/api/report-management/reports
python run_worker.py --once
```

## RuoYi UI

当前前端源码在隔离目录：

```text
report-management/frontend/ruoyi-ui
```

迁移到真实 `ruoyi-ui` 后需要：

- 安装 `@vue-office/docx`。
- 合并 API 文件、页面、路由。
- 审核菜单 SQL 中的 `parent_id`。
- 运行前端构建验证。
