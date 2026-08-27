# 双类型 AI 审核实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将批次初始报告和用户上传报告分别路由到初始审核与修订审核，共用模型连接配置并独立维护两套版本化提示词。

**Architecture:** 审核记录在创建时固定 `audit_type`，Worker 按类型读取对应提示词，并从独立的单例模型配置表读取 URL、Model Name 和 API Key。旧检查点数据保留但退出新审核流程；真实 RuoYi 前端提供共享模型配置和两个提示词页签。

**Tech Stack:** Python 3.11、Flask、PyMySQL、python-docx、MySQL 5.7、Vue 2、Element UI、Node.js 内置测试、RuoYi-Cloud `ruoyi-ui`

**Spec:** `report-management/docs/superpowers/specs/2026-08-27-dual-audit-types-design.md`

## Global Constraints

- 审核类型只允许 `initial` 和 `revision`。
- 批次登记只创建 `initial` 审核；用户上传只创建 `revision` 审核。
- 修订审核不重复初始审核中的错别字和目录一致性检查。
- 模型 URL、Model Name 和 API Key 共用，API Key 不返回明文且不得提交到 Git。
- 两套提示词分别版本化，每种类型只能有一个启用版本。
- 输出协议保持“首行审核结论 + 中文 Markdown”，不输出 JSON。
- 不处理图片、截图和图表图片语义。
- 不删除旧检查点表、历史快照、旧 JSON 字段或旧提示词连接字段。
- 不修改报告登记和上传接口的现有请求格式。
- 数据库迁移和生产部署必须分别获得用户确认。
- 后端仓库根目录为 `/Users/yangfan/workspace/codex/report-temp`；真实前端仓库为 `/Users/yangfan/workspace/codex/ruoyi-cloud-ops`，当前隔离工作区为 `/Users/yangfan/workspace/codex/report-temp/ruoyi-report-table-layout`。

---

### Task 1: 双审核类型数据库迁移

**Files:**
- Create: `report-management/db/migrations/006_precheck_dual_audit_types.sql`
- Create: `report-management/db/migrations/006_dual_audit_types.sql`
- Create: `report-management/backend/tests/test_dual_audit_migration_contract.py`

**Interfaces:**
- Produces: `capability_report_ai_config` 单例配置表。
- Produces: `capability_report_audit_prompt.audit_type`。
- Produces: `capability_report_audit.audit_type`。
- Produces: 每种审核类型各一个启用提示词。

- [ ] **Step 1: 写迁移契约失败测试**

```python
class DualAuditMigrationContractTest(unittest.TestCase):
    def test_migration_is_additive_and_seeds_both_prompt_types(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("capability_report_ai_config", sql)
        self.assertIn("audit_type", sql)
        self.assertIn("'initial'", sql)
        self.assertIn("'revision'", sql)
        self.assertNotRegex(sql.upper(), r"DROP\s+TABLE")
        self.assertNotRegex(sql.upper(), r"DROP\s+COLUMN")

    def test_precheck_reports_unlinked_audits_and_active_prompts(self):
        sql = PRECHECK.read_text(encoding="utf-8")
        self.assertIn("unlinked_audit_rows", sql)
        self.assertIn("active_prompt_rows", sql)
        self.assertIn("running_audit_rows", sql)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_dual_audit_migration_contract -v`

Expected: FAIL，因为 `006` 迁移文件不存在。

- [ ] **Step 3: 编写预检查脚本**

预检查必须输出以下列，并且只执行 SELECT：

```sql
SELECT
  (SELECT COUNT(*) FROM capability_report_audit WHERE status = 'running') AS running_audit_rows,
  (SELECT COUNT(*) FROM capability_report_audit_prompt WHERE enabled = 1) AS active_prompt_rows,
  (SELECT COUNT(*)
     FROM capability_report_audit audit
     LEFT JOIN capability_report_version version ON version.id = audit.version_id
    WHERE version.id IS NULL) AS unlinked_audit_rows;
```

- [ ] **Step 4: 编写幂等迁移脚本**

迁移使用 MySQL 5.7 存储过程检查表和列是否存在，执行以下确定性操作：

```sql
CREATE TABLE IF NOT EXISTS capability_report_ai_config (
  id bigint(20) NOT NULL AUTO_INCREMENT,
  api_url varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT '',
  model_name varchar(64) COLLATE utf8mb4_bin NOT NULL DEFAULT 'ark-code-latest',
  api_key varchar(512) COLLATE utf8mb4_bin NOT NULL DEFAULT '',
  create_time datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_time datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
```

增加 `audit_type` 后按版本类型回填：

```sql
UPDATE capability_report_audit audit
JOIN capability_report_version version ON version.id = audit.version_id
SET audit.audit_type = CASE
  WHEN version.version_type = 'initial' THEN 'initial'
  ELSE 'revision'
END
WHERE audit.audit_type IS NULL OR audit.audit_type = '';
```

从当前启用提示词复制模型连接到单例配置，停用旧提示词，再把设计文档中的两套提示词原文分别插入 `initial` 和 `revision` 类型。旧连接字段填写共用配置值以满足原 NOT NULL 约束，但新代码不读取这些字段。

- [ ] **Step 5: 运行迁移契约测试**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_dual_audit_migration_contract -v`

Expected: PASS。

- [ ] **Step 6: 检查 SQL 不包含破坏性操作**

Run: `rg -n "DROP TABLE|DROP COLUMN|TRUNCATE|DELETE FROM capability_report" report-management/db/migrations/006_*.sql`

Expected: 无匹配结果；仅允许删除临时存储过程的 `DROP PROCEDURE`。

- [ ] **Step 7: 提交迁移**

```bash
git add report-management/db/migrations/006_precheck_dual_audit_types.sql \
  report-management/db/migrations/006_dual_audit_types.sql \
  report-management/backend/tests/test_dual_audit_migration_contract.py
git commit -m "新增双类型审核数据库迁移"
```

### Task 2: 共用模型配置与双提示词 API

**Files:**
- Create: `report-management/backend/app/routes/ai_config.py`
- Modify: `report-management/backend/app/factory.py`
- Modify: `report-management/backend/app/routes/audit_prompts.py`
- Modify: `report-management/backend/app/repositories/audits.py`
- Modify: `report-management/backend/tests/test_report_routes.py`

**Interfaces:**
- Produces: `get_ai_config() -> dict[str, Any] | None`。
- Produces: `update_ai_config(payload: dict[str, str]) -> dict[str, Any]`。
- Produces: `get_active_prompt(audit_type: str) -> dict[str, Any] | None`。
- Produces: `get_prompt_by_id(prompt_id: int) -> dict[str, Any] | None`。
- Produces: `create_prompt_version(audit_type: str, payload: dict[str, Any]) -> dict[str, Any]`。

- [ ] **Step 1: 写路由失败测试**

覆盖以下请求：

```python
def test_shared_ai_config_masks_key(self):
    response = self.client.get("/api/report-management/ai-config")
    self.assertEqual(response.status_code, 200)
    self.assertNotIn("apiKey", response.json)
    self.assertTrue(response.json["apiKeyConfigured"])

def test_prompt_types_are_independent(self):
    initial = self.client.get("/api/report-management/audit-prompts/initial/active")
    revision = self.client.get("/api/report-management/audit-prompts/revision/active")
    self.assertEqual(initial.json["auditType"], "initial")
    self.assertEqual(revision.json["auditType"], "revision")

def test_unknown_prompt_type_is_rejected(self):
    response = self.client.get("/api/report-management/audit-prompts/other/active")
    self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: 运行路由测试并确认失败**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_report_routes.ReportRoutesTest.test_shared_ai_config_masks_key tests.test_report_routes.ReportRoutesTest.test_prompt_types_are_independent -v`

Expected: FAIL，路由和仓储方法尚不存在。

- [ ] **Step 3: 实现模型配置仓储**

`update_ai_config` 在 Key 留空时沿用当前 Key：

```python
api_key = payload.get("apiKey") or (current["apiKey"] if current else "")
```

对外响应只返回：

```python
{
    "id": row["id"],
    "apiUrl": row["api_url"],
    "modelName": row["model_name"],
    "apiKeyMasked": _mask_secret(row["api_key"]),
    "apiKeyConfigured": bool(row["api_key"]),
}
```

- [ ] **Step 4: 实现双提示词仓储**

查询必须带类型：

```sql
SELECT id, name, audit_type, prompt_content, version, enabled, create_time, update_time
FROM capability_report_audit_prompt
WHERE audit_type = %s AND enabled = 1
ORDER BY version DESC, id DESC
LIMIT 1
```

创建新版本时只停用同类型记录：

```sql
UPDATE capability_report_audit_prompt SET enabled = 0 WHERE audit_type = %s
```

- [ ] **Step 5: 实现并注册 API**

新增：

```text
GET  /api/report-management/ai-config
PUT  /api/report-management/ai-config
GET  /api/report-management/audit-prompts/<audit_type>/active
POST /api/report-management/audit-prompts/<audit_type>
```

旧 `/audit-prompts/active` 和 `/audit-prompts` 映射到 `revision`，响应增加 `Deprecation: true`。

- [ ] **Step 6: 运行路由测试**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_report_routes -v`

Expected: PASS。

- [ ] **Step 7: 提交配置 API**

```bash
git add report-management/backend/app/routes/ai_config.py \
  report-management/backend/app/factory.py \
  report-management/backend/app/routes/audit_prompts.py \
  report-management/backend/app/repositories/audits.py \
  report-management/backend/tests/test_report_routes.py
git commit -m "新增共享模型配置与双提示词接口"
```

### Task 3: 审核任务类型路由

**Files:**
- Modify: `report-management/backend/app/repositories/reports.py`
- Modify: `report-management/backend/app/repositories/audits.py`
- Modify: `report-management/backend/app/services/audit_worker.py`
- Modify: `report-management/backend/app/services/deepseek_client.py`
- Modify: `report-management/backend/tests/test_report_routes.py`
- Modify: `report-management/backend/tests/test_audit_worker.py`

**Interfaces:**
- Consumes: Task 2 的 `get_ai_config()` 和 `get_active_prompt(audit_type)`。
- Produces: `_create_pending_audit(cursor, report_id, version_id, audit_type)`。
- Produces: Worker 作业字段 `auditType`。
- Produces: `DeepSeekClient.audit_report(model_config, prompt, audit_input, on_delta=None)`。

- [ ] **Step 1: 写任务类型失败测试**

```python
def test_register_initial_report_creates_initial_audit(self):
    response = self.client.post("/api/report-management/reports/register", json=INITIAL_PAYLOAD)
    self.assertEqual(response.json["auditType"], "initial")

def test_register_uploaded_initial_report_creates_initial_audit(self):
    response = self.client.post(
        "/api/report-management/reports/register-upload",
        data={**INITIAL_FORM, "file": (io.BytesIO(DOCX_BYTES), "report.docx")},
        content_type="multipart/form-data",
    )
    self.assertEqual(response.json["auditType"], "initial")

def test_upload_version_creates_revision_audit(self):
    response = self.client.post("/api/report-management/reports/1/versions", data=UPLOAD_PAYLOAD)
    self.assertEqual(response.json["auditType"], "revision")

def test_retry_preserves_latest_audit_type(self):
    response = self.client.post("/api/report-management/audits/reports/1/versions/2/retry")
    self.assertEqual(response.json["auditType"], "revision")
```

- [ ] **Step 2: 写 Worker 提示词选择失败测试**

Fake repository 记录调用参数：

```python
def get_active_prompt(self, audit_type):
    self.requested_prompt_types.append(audit_type)
    return self.prompts.get(audit_type)
```

断言 `initial` 作业只请求初始提示词，`revision` 作业只请求修订提示词，且 `audit_input` 不含 `checkpoints`。

- [ ] **Step 3: 运行测试并确认失败**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_report_routes tests.test_audit_worker -v`

Expected: FAIL，现有方法没有审核类型参数。

- [ ] **Step 4: 创建审核记录时固定类型**

```python
def _create_pending_audit(self, cursor, report_id, version_id, audit_type):
    if audit_type not in {"initial", "revision"}:
        raise ValueError("不支持的审核类型")
    cursor.execute(
        "INSERT INTO capability_report_audit "
        "(report_id, version_id, audit_type, status, summary, result_data) "
        "VALUES (%s, %s, %s, 'pending', NULL, NULL)",
        [report_id, version_id, audit_type],
    )
```

初始登记传 `initial`，上传版本传 `revision`。响应增加 `auditType`。

- [ ] **Step 5: 重试沿用原类型**

重试查询最近审核的 `audit_type`；旧记录为空时联查 `version_type` 并映射。新记录和 queued 事件都写入明确类型。

- [ ] **Step 6: Worker 使用共用模型配置和类型提示词**

```python
model_config = self.repository.get_ai_config()
prompt = self.repository.get_active_prompt(job["auditType"])
result = self.model_client.audit_report(model_config, prompt, audit_input, on_delta=handle_delta)
```

删除新任务中的 `get_active_checkpoints()` 和 `save_checkpoint_snapshot()` 调用。错误信息区分“未配置共用模型连接”和“未配置启用的初始/修订审核提示词”。

- [ ] **Step 7: 调整模型客户端签名**

连接参数只来自 `model_config`，系统消息只使用 `prompt["promptContent"]`，输出协议继续由客户端追加。

- [ ] **Step 8: 运行相关测试**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_report_routes tests.test_audit_worker -v`

Expected: PASS。

- [ ] **Step 9: 提交任务路由**

```bash
git add report-management/backend/app/repositories/reports.py \
  report-management/backend/app/repositories/audits.py \
  report-management/backend/app/services/audit_worker.py \
  report-management/backend/app/services/deepseek_client.py \
  report-management/backend/tests/test_report_routes.py \
  report-management/backend/tests/test_audit_worker.py
git commit -m "按报告来源路由AI审核类型"
```

### Task 4: DOCX 标题和目录结构提取

**Files:**
- Modify: `report-management/backend/app/services/docx_tools.py`
- Modify: `report-management/backend/app/services/audit_input.py`
- Modify: `report-management/backend/tests/test_audit_worker.py`

**Interfaces:**
- Produces: `document.headings: list[dict[str, Any]]`。
- Produces: `document.tocEntries: list[str]`。
- Produces: `document.tocAvailable: bool`。

- [ ] **Step 1: 写标题结构失败测试**

```python
def test_extracts_heading_levels_for_initial_audit(self):
    document = Document()
    document.add_heading("一、系统概述", level=1)
    document.add_heading("1.1 应用信息", level=2)
    document.save(path)
    result = extract_text_and_tables(path)
    self.assertEqual(result["headings"][0]["level"], 1)
    self.assertEqual(result["headings"][1]["text"], "1.1 应用信息")
```

- [ ] **Step 2: 写目录不可用失败测试**

普通 DOCX 没有可读取目录域时断言：

```python
self.assertFalse(result["tocAvailable"])
self.assertEqual(result["tocEntries"], [])
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_audit_worker.AuditWorkerTest.test_extracts_heading_levels_for_initial_audit -v`

Expected: FAIL，返回结构中没有 `headings`。

- [ ] **Step 4: 实现标题提取**

读取 `paragraph.style.name`，识别 `Heading N` 和 `标题 N`，输出：

```python
{"text": paragraph.text.strip(), "level": level, "style": paragraph.style.name}
```

目录提取采用 best-effort：检测 `w:instrText` 中的 `TOC` 字段，并收集对应目录段落文本；无法读取时明确 `tocAvailable = False`。

- [ ] **Step 5: 更新审核输入范围**

`build_audit_input` 不再接受 checkpoints 参数，保持 `paragraphs` 和 `tables` 兼容，并把标题和目录字段放入 `document`。

- [ ] **Step 6: 运行测试**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_audit_worker -v`

Expected: PASS。

- [ ] **Step 7: 提交 DOCX 结构提取**

```bash
git add report-management/backend/app/services/docx_tools.py \
  report-management/backend/app/services/audit_input.py \
  report-management/backend/tests/test_audit_worker.py
git commit -m "补充DOCX标题与目录结构提取"
```

### Task 5: AI 对话沿用审核提示词

**Files:**
- Modify: `report-management/backend/app/repositories/audits.py`
- Modify: `report-management/backend/app/services/agent_worker.py`
- Modify: `report-management/backend/app/services/deepseek_client.py`
- Modify: `report-management/backend/tests/test_audit_worker.py`

**Interfaces:**
- Consumes: `get_ai_config()`。
- Consumes: `get_prompt_by_id(prompt_id)`，缺失时使用 `get_active_prompt(audit_type)`。
- Produces: Agent 作业字段 `auditType` 和 `promptId`。
- Produces: `DeepSeekClient.chat_report_agent(model_config, prompt, report_context, history, question, on_delta=None)`。

- [ ] **Step 1: 写 Agent 选择提示词失败测试**

```python
def test_agent_uses_prompt_saved_on_audit_record(self):
    worker.run_once()
    self.assertEqual(repository.requested_prompt_id, 42)
    self.assertEqual(model_client.calls[0][0]["modelName"], "ark-code-latest")
    self.assertEqual(model_client.calls[0][1]["auditType"], "revision")
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_audit_worker.AuditWorkerTest.test_agent_uses_prompt_saved_on_audit_record -v`

Expected: FAIL，Agent 当前读取全局提示词。

- [ ] **Step 3: 扩展 Agent 作业查询**

`next_pending_agent_message` 联查关联审核的 `audit_type` 和 `prompt_id`。历史审核没有 prompt_id 时保留空值。

- [ ] **Step 4: 实现回退顺序**

```python
prompt = self.repository.get_prompt_by_id(job.get("promptId")) if job.get("promptId") else None
if prompt is None:
    prompt = self.repository.get_active_prompt(job["auditType"])
```

Agent 使用共用模型连接配置；构造报告上下文时不再注入旧 checkpoints。

模型调用固定为：

```python
self.model_client.chat_report_agent(
    model_config,
    prompt,
    context,
    job.get("history", []),
    job["question"],
    on_delta=handle_delta,
)
```

- [ ] **Step 5: 运行 Agent 测试**

Run: `cd report-management/backend && .venv/bin/python -m unittest tests.test_audit_worker -v`

Expected: PASS。

- [ ] **Step 6: 提交 AI 对话调整**

```bash
git add report-management/backend/app/repositories/audits.py \
  report-management/backend/app/services/agent_worker.py \
  report-management/backend/app/services/deepseek_client.py \
  report-management/backend/tests/test_audit_worker.py
git commit -m "让AI对话沿用审核类型提示词"
```

### Task 6: 双提示词配置页面

**Files:**
- Modify: `ruoyi-ui/src/api/report-management/auditPrompt.js`
- Modify: `ruoyi-ui/src/views/report-management/audit-prompt/index.vue`
- Create: `ruoyi-ui/tests/report-audit-config-page.test.mjs`

**Interfaces:**
- Consumes: Task 2 的共用模型配置和双提示词 API。
- Produces: 一份模型连接表单和 `initial`、`revision` 两个提示词编辑页签。

- [ ] **Step 1: 写前端失败测试**

```javascript
assert.match(page, /模型连接配置/)
assert.match(page, /初始审核提示词/)
assert.match(page, /修订审核提示词/)
assert.doesNotMatch(page, /业务检查点/)
assert.doesNotMatch(page, /listAuditCheckpoints/)
assert.match(api, /audit-prompts\/\$\{auditType\}\/active/)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd ruoyi-ui && node --test tests/report-audit-config-page.test.mjs`

Expected: FAIL，当前页面仍展示业务检查点。

- [ ] **Step 3: 更新 API 模块**

导出：

```javascript
export const getAiConfig = () => request({ url: '/report-management-api/ai-config', method: 'get' })
export const updateAiConfig = data => request({ url: '/report-management-api/ai-config', method: 'put', data })
export const getActivePrompt = auditType => request({ url: `/report-management-api/audit-prompts/${auditType}/active`, method: 'get' })
export const createPromptVersion = (auditType, data) => request({ url: `/report-management-api/audit-prompts/${auditType}`, method: 'post', data })
```

删除页面使用的检查点 API 导入；旧导出可以暂时保留，避免影响未迁移代码。

- [ ] **Step 4: 重构配置页面状态**

使用独立对象：

```javascript
modelConfig: { apiUrl: '', modelName: '', apiKey: '', apiKeyMasked: '', apiKeyConfigured: false },
prompts: {
  initial: { name: '初始审核提示词', promptContent: '', version: null },
  revision: { name: '修订审核提示词', promptContent: '', version: null }
}
```

模型配置单独保存；两个提示词页签分别保存新版本。页面移除检查点表格、弹窗、徽标、统计和组合说明。

- [ ] **Step 5: 完善页面说明**

初始审核说明“批次初始版本，检查文字与文档结构”；修订审核说明“用户上传版本，检查性能容量分析，不重复初始检查”。Key 留空说明保持“沿用当前密钥”。

- [ ] **Step 6: 运行前端测试和构建**

Run: `cd ruoyi-ui && node --test tests/report-audit-config-page.test.mjs tests/report-management-page.test.mjs`

Expected: PASS。

Run: `cd ruoyi-ui && npm run build:prod`

Expected: build complete；允许项目已有资源体积 warning，不允许编译错误。

- [ ] **Step 7: 提交真实前端配置页**

```bash
git add ruoyi-ui/src/api/report-management/auditPrompt.js \
  ruoyi-ui/src/views/report-management/audit-prompt/index.vue \
  ruoyi-ui/tests/report-audit-config-page.test.mjs
git commit -m "改造AI审核双提示词配置"
```

### Task 7: 审核类型展示

**Files:**
- Modify: `report-management/backend/app/repositories/audits.py`
- Modify: `report-management/backend/app/repositories/reports.py`
- Modify: `report-management/backend/tests/test_report_routes.py`
- Modify: `ruoyi-ui/src/views/report-management/report/index.vue`
- Modify: `ruoyi-ui/src/views/report-management/audit-workbench/index.vue`
- Modify: `ruoyi-ui/tests/report-management-page.test.mjs`

**Interfaces:**
- Produces: API 字段 `auditType` 和 `auditTypeLabel`。
- Consumes: `initial -> 初始审核`、`revision -> 修订审核` 的固定展示映射。

- [ ] **Step 1: 写后端响应失败测试**

审核详情、报告详情版本和会话版本均断言：

```python
self.assertEqual(response.json["auditType"], "initial")
self.assertEqual(response.json["auditTypeLabel"], "初始审核")
```

- [ ] **Step 2: 实现统一映射**

在仓储模块使用同一函数：

```python
def _audit_type_label(audit_type: str | None) -> str:
    return {"initial": "初始审核", "revision": "修订审核"}.get(audit_type or "", "未知审核")
```

所有审核详情和会话查询选择 `audit.audit_type`。

- [ ] **Step 3: 写前端展示失败测试**

```javascript
assert.match(page, /auditTypeLabel/)
assert.match(workbench, /audit-type-tag/)
```

- [ ] **Step 4: 实现轻量标签**

报告列表不新增列。详情弹窗的审核状态旁显示类型标签；工作台右侧审核记录标题区域显示类型标签。未知历史值显示“未知审核”，不阻断页面。

- [ ] **Step 5: 运行后端和前端测试**

Run: `cd report-management/backend && .venv/bin/python -m unittest discover -s tests -v`

Expected: PASS。

Run: `cd ruoyi-ui && node --test tests/report-management-page.test.mjs tests/report-audit-config-page.test.mjs`

Expected: PASS。

- [ ] **Step 6: 分别提交后端和前端**

后端仓库：

```bash
git add report-management/backend/app/repositories/audits.py \
  report-management/backend/app/repositories/reports.py \
  report-management/backend/tests/test_report_routes.py
git commit -m "返回AI审核类型信息"
```

真实前端仓库：

```bash
git add ruoyi-ui/src/views/report-management/report/index.vue \
  ruoyi-ui/src/views/report-management/audit-workbench/index.vue \
  ruoyi-ui/tests/report-management-page.test.mjs
git commit -m "展示报告AI审核类型"
```

### Task 8: 全量验证与发布准备

**Files:**
- Modify: `report-management/README.md`
- Modify: `report-management/docs/api-contract.md`
- Create: `report-management/docs/dual-audit-release-checklist.md`

**Interfaces:**
- Consumes: Tasks 1-7 的数据库、后端和前端结果。
- Produces: 可复现的本地验证结果和生产发布检查表。

- [ ] **Step 1: 更新接口和运行文档**

记录共用模型配置 API、双提示词 API、`auditType` 响应字段、两类触发规则和 Worker 配置错误语义。删除“新审核会动态组合业务检查点”的当前行为描述，明确旧检查点仅为历史兼容数据。

- [ ] **Step 2: 编写发布检查表**

检查表必须包含：

```text
[ ] 查询 running 审核数量为 0
[ ] 停止 report-management-worker.service
[ ] 备份远端数据库和当前后端 release
[ ] 执行 006_precheck_dual_audit_types.sql
[ ] 用户确认迁移输出
[ ] 执行 006_dual_audit_types.sql
[ ] 部署并重启 API 与 Worker
[ ] 验证 initial 和 revision 启用提示词各 1 条
[ ] 模拟批次登记并确认 auditType=initial
[ ] 上传用户版本并确认 auditType=revision
[ ] 部署 ruoyi-ui 静态资源并验证配置页
[ ] 保留回滚目录和数据库备份路径
```

- [ ] **Step 3: 运行后端全量测试**

Run: `cd report-management/backend && .venv/bin/python -m unittest discover -s tests -v`

Expected: 所有测试 PASS。

- [ ] **Step 4: 运行前端测试**

Run: `cd ruoyi-ui && node --test tests/*.test.mjs`

Expected: 所有测试 PASS。

- [ ] **Step 5: 运行生产构建**

Run: `cd ruoyi-ui && npm run build:prod`

Expected: build complete；不允许编译错误。

- [ ] **Step 6: 检查密钥和改动范围**

Run: `git diff --check`

Run: `rg -n "ark-[A-Za-z0-9_-]{16,}|Authorization: Bearer" report-management ruoyi-ui -g '!*.md' -g '!dist/**'`

Expected: 不出现真实 API Key；测试中的固定假值必须明确以 `test-` 开头。

- [ ] **Step 7: 提交文档**

```bash
git add report-management/README.md \
  report-management/docs/api-contract.md \
  report-management/docs/dual-audit-release-checklist.md
git commit -m "补充双类型审核发布说明"
```

- [ ] **Step 8: 停在生产变更确认门槛**

向用户汇报本地测试、构建、迁移预检查脚本和待部署提交，不执行远端数据库迁移、服务重启或静态资源替换。生产操作必须由用户再次明确确认。
