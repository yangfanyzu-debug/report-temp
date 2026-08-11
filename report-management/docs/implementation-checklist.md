# 实施清单

## 阶段 1：数据库准备

- 检查远端 `ry-cloud.capability_report_log` 是否存在 `systemId + title + report_month` 重复数据。
- 检查现有索引名，避免直接执行草案里的 `DROP KEY idx_systemId` 失败。
- 调整 `capability_report_log` 唯一键为 `systemId + title + report_month`。
- 创建 `capability_report_version`。
- 创建 `capability_report_audit`。
- 创建 `capability_report_audit_prompt`。
- 插入默认启用提示词版本。
- 基于现有 `capability_report_log.report_data.data` 回填初始版本记录。

## 阶段 2：Python 后端骨架

- 在 `report-management/backend/` 下新建独立 Python 服务。
- 配置 MySQL 连接、上传目录、DeepSeek URL、DeepSeek Key、模型名。
- 提供健康检查接口。
- 提供统一错误响应。
- 实现 DOCX 基本校验。
- 实现版本化文件名生成，禁止同名替换。

## 阶段 3：报告与版本接口

- 实现报告列表查询。
- 实现报告详情查询。
- 实现批次注册初始报告接口。
- 实现上传新版本接口。
- 实现指定版本预览接口。
- 实现指定版本下载接口。

## 阶段 4：AI 审核

- 实现 DOCX 文本、表格、章节结构提取。
- 实现当前启用提示词读取。
- 实现审核记录创建和状态流转。
- 实现后台异步审核任务。
- 接入 Ark/OpenAI-compatible 模型 API，并使用环境变量配置 URL、Key 和模型名。
- 要求模型输出结构化 JSON。
- 校验模型输出 JSON 格式。
- 更新审核记录、版本审核状态和报告最新审核摘要。
- 暂不处理图片或图表语义。

## 阶段 5：审核提示词

- 实现查看当前启用提示词接口。
- 实现新增提示词版本接口。
- 保存后启用新版本并停用旧版本。
- 确保历史审核记录仍指向旧提示词版本。

## 阶段 6：RuoYi UI

- 在 `ruoyi-ui` 新增报告管理 API 文件。
- 新增报告列表页。
- 新增报告详情页。
- 新增 DOCX 预览页，使用 `@vue-office/docx`。
- 新增审核提示词配置页。
- 新增菜单。
- 预览操作使用新 tab 打开。
- 上传成功后展示“已上传新版本，AI审核中”。

## 阶段 7：部署与验证

- 新 Python 服务单独部署，不依赖旧 Python 文件服务。
- 配置上传目录，例如 `/appdata/.../uploaded_reports/`。
- 配置 Nginx 反向代理路径。
- 配置 API 和 worker 的 systemd 服务。
- 配置 RuoYi UI 后端 API 地址。
- 验证批次注册初始报告。
- 验证用户上传同名 DOCX 会创建新版本。
- 验证初始版本和上传版本都可预览、下载。
- 验证审核状态从 `pending` 到 `running` 再到 `passed` 或 `failed`。
- 验证提示词修改只影响后续审核。
