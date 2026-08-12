from app.repositories.reports import _audit_result_summary


def test_extracts_description_after_audit_summary_heading():
    result = _audit_result_summary(
        "审核结论：通过\n\n## 审核总结\n报告结构完整，关键指标未发现明显异常。\n\n## 检查点结果"
    )

    assert result == "报告结构完整，关键指标未发现明显异常。"


def test_falls_back_to_first_meaningful_line_without_heading():
    result = _audit_result_summary("审核结论：不通过\n请补充容量风险及整改计划。")

    assert result == "请补充容量风险及整改计划。"


def test_does_not_treat_next_markdown_heading_as_summary():
    result = _audit_result_summary("审核结论：通过\n\n## 审核总结\n\n## 检查点结果")

    assert result == ""
