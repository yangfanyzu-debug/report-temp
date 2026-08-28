from __future__ import annotations

import re
import unittest
from pathlib import Path


REPORT_MANAGEMENT_DIR = Path(__file__).resolve().parents[2]
MIGRATION = REPORT_MANAGEMENT_DIR / "db/migrations/006_dual_audit_types.sql"
PRECHECK = REPORT_MANAGEMENT_DIR / "db/migrations/006_precheck_dual_audit_types.sql"


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
        self.assertNotRegex(sql.upper(), r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b")

    def test_migration_seeds_complete_design_prompts_and_markdown_protocol(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        initial_prompt = """你是性能容量报告的初始质量审核助手。你只审核批次生成的初始 DOCX 报告，目标是发现基础文字和文档结构问题。

审核范围仅包括系统提供的报告基本信息、正文文字、标题层级、可读取的目录条目和表格文字。不要判断图片、截图或图表图片的视觉语义，不要声称检查了字体、颜色、分页、对齐等未提供的版式信息。

请检查：
1. 报告标题、系统名称、报告月份等基本信息是否前后一致。
2. 可读取的目录条目与正文标题是否存在缺失、多余、顺序错误或编号不一致。
3. 章节和子章节是否缺失、重复、为空或只有标题没有正文。
4. 正文是否存在明显错别字、病句、标点错误、术语混用或同一名称前后不一致。
5. 表格标题、表头、单位和单元格内容是否存在明显缺失或前后不一致。
6. 文档中是否存在明显占位符、测试文字、未替换模板内容或无法解释的空值。

只根据输入中可读取的内容判断。证据不足时明确说明无法判断，不得编造文档内容。发现问题时指出原文位置或相关章节，并给出可执行的修改建议。"""
        revision_prompt = """你是性能容量报告的修订审核助手。你只审核用户上传的修订版本，目标是判断性能容量分析、数据结论和治理建议是否合理。不要重复执行错别字、目录一致性等初始质量检查。

审核范围仅包括系统提供的报告基本信息、正文文字、表格数据和标题结构。不要判断图片、截图或图表图片的视觉语义。

请检查：
1. 性能指标、容量指标、阈值、统计周期和单位是否明确，最小值、最大值、平均值或关键指标为 0 时是否有合理解释。
2. 系统概述、组件清单、服务器数量、性能分析小结和结论中的数量是否前后一致。
3. 各组件是否都有对应的性能或容量分析，是否存在只有数据没有分析、只有结论没有依据的情况。
4. 报告结论是否能由正文或表格中的数据支撑，是否存在数据与结论矛盾、统计口径不一致或推导跳跃。
5. 是否识别容量瓶颈、资源风险、趋势变化和影响范围，风险等级是否与证据匹配。
6. 扩容、优化或治理建议是否具体可执行，是否包含对象、依据、优先级或验证方式。
只根据输入中可读取的内容判断。证据不足时明确说明无法判断，不得编造指标、服务器数量或图表结论。发现问题时引用相关章节或表格依据，并给出可执行的修改建议。"""

        self.assertIn(initial_prompt, sql)
        self.assertIn(revision_prompt, sql)
        self.assertIn("审核结论：通过", sql)
        self.assertIn("审核结论：不通过", sql)
        self.assertIn("中文 Markdown", sql)
        self.assertIn("不输出 JSON", sql)

    def test_migration_uses_mysql_57_information_schema_guards_and_indexes(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("information_schema.columns", sql)
        self.assertIn("information_schema.statistics", sql)
        self.assertIn("idx_audit_prompt_type_enabled", sql)
        self.assertIn("idx_audit_pending_type", sql)
        self.assertIsNone(re.search(r"\bJSON_TABLE\b", sql, re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
