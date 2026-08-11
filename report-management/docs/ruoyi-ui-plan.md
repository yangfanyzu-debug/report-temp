# RuoYi UI 接入草案

## 菜单

建议新增菜单：

```text
系统工具 / 报告管理
```

或者如果后续有专门业务分组：

```text
AI能力 / 报告管理
```

## 路由

建议路由：

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `/report-management/reports` | `views/report-management/report/index.vue` | 报告列表 |
| `/report-management/reports/:id` | `views/report-management/report/detail.vue` | 报告详情 |
| `/report-management/preview/:versionId` | `views/report-management/preview/index.vue` | DOCX 新 tab 预览 |
| `/report-management/audit-prompts` | `views/report-management/audit-prompt/index.vue` | 审核提示词配置 |

## API 文件

建议新增：

```text
src/api/report-management/report.js
src/api/report-management/auditPrompt.js
```

当前隔离目录已提供可迁移源码：

```text
report-management/frontend/ruoyi-ui/src/api/report-management/report.js
report-management/frontend/ruoyi-ui/src/api/report-management/auditPrompt.js
report-management/frontend/ruoyi-ui/src/views/report-management/report/index.vue
report-management/frontend/ruoyi-ui/src/views/report-management/report/detail.vue
report-management/frontend/ruoyi-ui/src/views/report-management/preview/index.vue
report-management/frontend/ruoyi-ui/src/views/report-management/audit-prompt/index.vue
report-management/frontend/ruoyi-ui/src/router/report-management.js
report-management/frontend/ruoyi-ui/menu-draft.sql
```

## 列表页

搜索项：

- 系统编码
- 报告标题
- 报表月份
- 审核状态

表格列：

- 系统编码
- 报告标题
- 报表月份
- 最新版本
- 最新审核状态
- 最新审核结论
- 最新审核建议
- 创建时间
- 操作

操作：

- 详情
- 预览最新版本
- 下载最新版本
- 上传新版本

## 详情页

区域：

- 报告主信息
- 版本列表
- 最新审核概要

版本列表操作：

- 预览
- 下载
- 查看审核详情

## 上传新版本

上传入口可以放在列表页和详情页。

行为：

- 只允许 `.docx`。
- 前端不做同名覆盖提示，因为后端永远创建新版本。
- 上传成功后提示“已上传新版本，AI审核中”。
- 刷新列表或详情后展示最新状态。

## DOCX 预览页

使用 `@vue-office/docx`。

打开方式：

```js
window.open(`/report-management/preview/${versionId}`, '_blank')
```

预览页内部请求：

```text
GET /prod-api/report-management-api/versions/{versionId}/preview
```

注意：

- 预览页不需要展示业务说明文字。
- 预览失败时展示简短错误状态，并提供下载按钮。

## 审核提示词配置页

第一版能力：

- 查看当前启用提示词。
- 编辑提示词内容。
- 保存后创建新版本并启用。

保存提示：

```text
保存后仅影响后续审核，历史审核记录仍保留原提示词版本。
```
