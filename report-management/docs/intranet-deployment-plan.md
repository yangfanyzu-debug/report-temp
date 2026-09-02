# 报告中心内网部署执行方案

## 1. 部署拓扑

| 服务器 | IP | 部署内容 |
| --- | --- | --- |
| 批次服务器 | `10.2.64.36` | 生成 DOCX，调用上传登记接口 |
| 报告中心 | `10.8.64.110` | Python API、AI Worker、DOCX 文件目录 |
| RuoYi 前端 | `10.8.64.107` | `ruoyi-ui` 静态资源和 Nginx |

```text
10.2.64.36 --上传DOCX--> 10.8.64.110:8045
浏览器 --> 10.8.64.107 --Nginx代理--> 10.8.64.110:8045
10.8.64.110 --> MySQL / 大模型API
```

服务器之间网络互通，接口不配置 Token。本方案不创建 systemd 服务，使用一个管理脚本统一启停 API 和 Worker。

## 2. 部署前确认

以下占位符执行前必须替换：

- `<ssh-user>`：三台服务器的 SSH 用户。
- `<ruoyi-web-root>`：`10.8.64.107` 当前 RuoYi 静态目录。
- `<MySQL地址/用户/密码>`：内网 `ry-cloud` 数据库连接信息。
- `<大模型API地址/模型/API-Key>`：实际大模型配置。

在 `10.8.64.110` 检查：

```bash
python3 --version
python3 -m pip --version
ss -lntp | grep ':8045 ' || true
df -h /opt /appdata
curl -I --connect-timeout 10 '<大模型API地址>' || true
mysql -h '<MySQL地址>' -P 3306 -u '<MySQL用户>' -p \
  -e 'SELECT VERSION(); SHOW DATABASES LIKE "ry-cloud";'
```

在 `10.8.64.107` 检查真实静态目录和 Nginx 配置：

```bash
nginx -v
sudo nginx -T 2>/dev/null | grep -E 'server_name|root |location /prod-api/'
```

## 3. 制作部署包

### 3.1 后端

在保存源码的部署机执行：

```bash
cd /Users/yangfan/workspace/codex/report-temp/report-management
rm -f /tmp/report-management-backend.tar.gz
tar \
  --exclude='backend/.venv' \
  --exclude='backend/__pycache__' \
  --exclude='backend/.env' \
  -czf /tmp/report-management-backend.tar.gz \
  backend db/migrations

scp /tmp/report-management-backend.tar.gz \
  <ssh-user>@10.8.64.110:/tmp/
scp deploy/scripts/report-management.sh \
  <ssh-user>@10.8.64.110:/tmp/
```

如果 `10.8.64.110` 无法访问 Python 软件源，在相同 Linux 系统和 CPU 架构的联网机器准备离线依赖：

```bash
cd /path/to/report-management
rm -rf /tmp/report-management-wheelhouse
mkdir -p /tmp/report-management-wheelhouse
python3 -m pip download \
  -r backend/requirements.txt \
  -d /tmp/report-management-wheelhouse
tar -czf /tmp/report-management-wheelhouse.tar.gz \
  -C /tmp report-management-wheelhouse
scp /tmp/report-management-wheelhouse.tar.gz \
  <ssh-user>@10.8.64.110:/tmp/
```

### 3.2 前端

在实际 RuoYi-Cloud 的 `ruoyi-ui` 目录执行：

```bash
cd /path/to/ruoyi-cloud/ruoyi-ui
npm ci
npm run build:prod

rm -f /tmp/ruoyi-ui-dist.tar.gz
tar -czf /tmp/ruoyi-ui-dist.tar.gz -C dist .
scp /tmp/ruoyi-ui-dist.tar.gz \
  <ssh-user>@10.8.64.107:/tmp/
```

前端在本地构建通过后上传 `dist`，不在内网服务器执行完整构建。

## 4. 数据库迁移

数据库迁移前必须备份。以下命令在能够访问 MySQL 且包含迁移 SQL 的机器执行。

```bash
export MYSQL_HOST='<MySQL地址>'
export MYSQL_PORT='3306'
export MYSQL_USER='<MySQL用户>'
export MYSQL_DATABASE='ry-cloud'
cd /path/to/report-management

mysql \
  -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p \
  --default-character-set=utf8mb4 "$MYSQL_DATABASE" \
  < db/migrations/001_precheck_report_management.sql

BACKUP_FILE="/tmp/ry-cloud-before-report-management.sql"
mysqldump \
  -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p \
  --single-transaction --routines --triggers \
  "$MYSQL_DATABASE" > "$BACKUP_FILE"
ls -lh "$BACKUP_FILE"
```

确认预检查没有重复数据或对象冲突后，按顺序执行：

```bash
for sql in \
  db/migrations/001_apply_report_management.sql \
  db/migrations/002_audit_model_config.sql \
  db/migrations/003_audit_progress_events.sql \
  db/migrations/004_audit_conversation_checkpoints.sql \
  db/migrations/005_report_agent_messages.sql
do
  echo "执行 $sql"
  mysql \
    -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p \
    --default-character-set=utf8mb4 "$MYSQL_DATABASE" \
    < "$sql" || exit 1
done
```

目标数据库已经执行过迁移时不要重复执行，应先核对现有表结构。

## 5. 部署报告中心到 10.8.64.110

### 5.1 解压及备份

```bash
ssh <ssh-user>@10.8.64.110
set -e

sudo mkdir -p \
  /opt/report-management/backups \
  /appdata/report-management/initial_reports \
  /appdata/report-management/uploaded_reports

if [ -d /opt/report-management/backend ]; then
  sudo cp -a /opt/report-management/backend \
    /opt/report-management/backups/backend-before-deploy
fi

sudo rm -rf /opt/report-management/backend.new
sudo mkdir -p /opt/report-management/backend.new
sudo tar -xzf /tmp/report-management-backend.tar.gz \
  -C /opt/report-management/backend.new \
  --strip-components=1 backend

if [ -f /opt/report-management/backend/.env ]; then
  sudo cp /opt/report-management/backend/.env \
    /opt/report-management/backend.new/.env
fi
```

### 5.2 安装 Python 依赖

可以访问 Python 软件源时：

```bash
sudo python3 -m venv /opt/report-management/backend.new/.venv
sudo /opt/report-management/backend.new/.venv/bin/pip install --upgrade pip
sudo /opt/report-management/backend.new/.venv/bin/pip install \
  -r /opt/report-management/backend.new/requirements.txt
```

完全离线时：

```bash
sudo rm -rf /tmp/report-management-wheelhouse
sudo tar -xzf /tmp/report-management-wheelhouse.tar.gz -C /tmp
sudo python3 -m venv /opt/report-management/backend.new/.venv
sudo /opt/report-management/backend.new/.venv/bin/pip install \
  --no-index \
  --find-links=/tmp/report-management-wheelhouse \
  -r /opt/report-management/backend.new/requirements.txt
```

### 5.3 配置环境变量

首次部署执行：

```bash
sudo cp /opt/report-management/backend.new/.env.example \
  /opt/report-management/backend.new/.env
sudo vi /opt/report-management/backend.new/.env
```

配置内容：

```dotenv
REPORT_UPLOAD_DIR=/appdata/report-management/uploaded_reports
REPORT_INITIAL_REPORT_DIR=/appdata/report-management/initial_reports
REPORT_PUBLIC_API_PREFIX=/report-management-api
REPORT_PORT=8045
REPORT_LOG_LEVEL=INFO

REPORT_MYSQL_HOST=<MySQL地址>
REPORT_MYSQL_PORT=3306
REPORT_MYSQL_USER=<MySQL用户>
REPORT_MYSQL_PASSWORD=<MySQL密码>
REPORT_MYSQL_DATABASE=ry-cloud

ARK_API_URL=<大模型API地址>
ARK_MODEL=<模型名称>
ARK_API_KEY=<API-Key>

REPORT_WORKER_INTERVAL_SECONDS=15
```

### 5.4 创建单一管理脚本

安装部署包中已经提供的统一管理脚本：

```bash
sudo install -m 750 \
  /tmp/report-management.sh \
  /opt/report-management/report-management.sh
bash -n /opt/report-management/report-management.sh
```

### 5.5 切换版本并启动

```bash
if [ -d /opt/report-management/backend ]; then
  sudo /opt/report-management/report-management.sh stop || true
fi

sudo rm -rf /opt/report-management/backend.old
if [ -d /opt/report-management/backend ]; then
  sudo mv /opt/report-management/backend \
    /opt/report-management/backend.old
fi
sudo mv /opt/report-management/backend.new \
  /opt/report-management/backend

sudo /opt/report-management/report-management.sh start
sudo /opt/report-management/report-management.sh status
curl -fsS http://127.0.0.1:8045/health
```

日常只操作一个脚本：

```bash
sudo /opt/report-management/report-management.sh start
sudo /opt/report-management/report-management.sh stop
sudo /opt/report-management/report-management.sh restart
sudo /opt/report-management/report-management.sh status
sudo /opt/report-management/report-management.sh logs
```

需要机器重启后自动拉起且仍不使用 systemd 时，可由运维在 root crontab 增加：

```cron
@reboot /opt/report-management/report-management.sh start >> /opt/report-management/boot.log 2>&1
```

## 6. 部署前端到 10.8.64.107

### 6.1 更新静态文件

```bash
ssh <ssh-user>@10.8.64.107
export RUOYI_WEB_ROOT='<ruoyi-web-root>'

test "$RUOYI_WEB_ROOT" != '<ruoyi-web-root>'
test -d "$RUOYI_WEB_ROOT"

BACKUP_DIR="$RUOYI_WEB_ROOT.backup"
sudo rm -rf "$BACKUP_DIR"
sudo cp -a "$RUOYI_WEB_ROOT" "$BACKUP_DIR"
sudo find "$RUOYI_WEB_ROOT" -mindepth 1 -maxdepth 1 \
  -exec rm -rf {} +
sudo tar -xzf /tmp/ruoyi-ui-dist.tar.gz \
  -C "$RUOYI_WEB_ROOT"
```

### 6.2 配置 Nginx

在当前 RuoYi 的 `server` 块中加入：

```nginx
location /prod-api/report-management-api/ {
    client_max_body_size 50m;
    proxy_connect_timeout 10s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    proxy_pass http://10.8.64.110:8045/api/report-management/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

检查并重载：

```bash
sudo nginx -t
sudo nginx -s reload
curl -fsS \
  http://127.0.0.1/prod-api/report-management-api/reports
```

如果 Nginx 在 Docker 中运行，修改宿主机挂载配置后执行：

```bash
docker exec <nginx-container> nginx -t
docker exec <nginx-container> nginx -s reload
```

## 7. 批次服务器接入

在 `10.2.64.36` 联调：

```bash
curl -fsS http://10.8.64.110:8045/health

curl --fail --show-error \
  --connect-timeout 10 \
  --max-time 300 \
  -X POST \
  'http://10.8.64.110:8045/api/report-management/reports/register-upload' \
  -F 'file=@/appdata/batch/output/性能容量报告.docx' \
  -F 'systemId=credit-card-center' \
  -F 'title=中信银行信用卡中心授权交易资源分析报告' \
  -F 'reportMonth=2026年08月' \
  -F 'generationId=batch-202608-credit-card-center-001' \
  -F 'source=batch'
```

成功响应：

```json
{
  "reportId": 1,
  "versionId": 1,
  "auditId": 1,
  "auditStatus": "pending"
}
```

批量调用规则：

- 每份报告单独请求，`3～5 MB` 文件并发数控制在 `2～4`。
- 网络超时和 `5xx` 最多重试 3 次，间隔建议 `5s/15s/30s`。
- `4xx` 不自动重试，记录响应内容后处理。
- 日志记录文件名、系统编码、月份、HTTP 状态码和 `auditId`。

## 8. 验收步骤

在 `10.8.64.110`：

```bash
sudo /opt/report-management/report-management.sh status
curl -fsS http://127.0.0.1:8045/health
curl -fsS http://127.0.0.1:8045/api/report-management/reports
tail -n 100 /opt/report-management/backend/logs/api.log
tail -n 100 /opt/report-management/backend/logs/worker.log
```

在 `10.8.64.107`：

```bash
curl -fsS http://10.8.64.110:8045/health
curl -fsS http://127.0.0.1/prod-api/report-management-api/reports
```

业务验收：

1. 从 `10.2.64.36` 上传一份测试 DOCX。
2. 确认接口返回 `pending` 及有效的三个 ID。
3. 在 `10.8.64.107` 页面确认报告已经出现。
4. 等待审核状态由“审核中”更新为最终结果。
5. 验证 DOCX 在线预览和下载。
6. 上传修改版，确认生成 `v2` 且 `v1` 仍可查看。
7. 验证 AI 审核工作台的文档和审核记录。

## 9. 回退命令

后端回退：

```bash
sudo /opt/report-management/report-management.sh stop
sudo rm -rf /opt/report-management/backend.failed
sudo mv /opt/report-management/backend \
  /opt/report-management/backend.failed
sudo mv /opt/report-management/backend.old \
  /opt/report-management/backend
sudo /opt/report-management/report-management.sh start
curl -fsS http://127.0.0.1:8045/health
```

前端回退：

```bash
export RUOYI_WEB_ROOT='<ruoyi-web-root>'
sudo find "$RUOYI_WEB_ROOT" -mindepth 1 -maxdepth 1 \
  -exec rm -rf {} +
sudo cp -a "$RUOYI_WEB_ROOT.backup/." "$RUOYI_WEB_ROOT/"
sudo nginx -t
sudo nginx -s reload
```

数据库回退必须使用迁移前的 SQL 备份，并由数据库管理员确认后执行，不能直接删除业务表。

## 10. 边界说明

- 本文提供可执行步骤，但尚未在三台内网服务器实际执行。
- API 和 Worker 由一个脚本管理，不使用 systemd；仍保留两个进程以避免异步审核阻塞 Web 请求。
- 第一版审核处理 DOCX 文字、表格和结构，不分析图片及图表语义。
