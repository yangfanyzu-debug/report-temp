from __future__ import annotations

import math
import random
import shutil
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "performance-capacity-test-docx"
TMP = OUT / ".assets"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

BLUE = "24557A"
BLUE2 = "2E74B5"
INK = "24323D"
MUTED = "667681"
LIGHT = "E8EEF5"
PALE = "F4F7FA"
GREEN = "2D7D46"
GOLD = "B47B16"
RED = "B33A3A"
WHITE = "FFFFFF"


REPORTS = [
    {
        "filename": "01_性能基线测试报告.docx",
        "title": "性能基线测试报告",
        "subtitle": "核心业务接口吞吐、时延与资源利用率基准",
        "scope": "Web API 与订单查询服务",
        "summary": "在 400 并发用户下，系统达到 1,180 TPS，P95 响应时间为 286 ms，错误率为 0.18%。主要约束来自应用节点 CPU，而数据库仍保留约 35% 余量。",
        "metrics": [("峰值吞吐", "1,180 TPS", "↑ 18%"), ("P95 时延", "286 ms", "达标"), ("错误率", "0.18%", "达标"), ("CPU 峰值", "76%", "可控")],
        "chart_title": "并发用户数与吞吐/时延趋势",
        "x": [50, 100, 200, 300, 400, 500],
        "series": [("吞吐量 TPS", [210, 405, 735, 980, 1180, 1215], BLUE2), ("P95 时延 ms", [82, 105, 148, 205, 286, 495], GOLD)],
        "table": [
            ["场景", "并发用户", "平均时延", "P95", "TPS", "错误率", "结果"],
            ["轻载", "50", "48 ms", "82 ms", "210", "0.00%", "通过"],
            ["常规", "200", "91 ms", "148 ms", "735", "0.03%", "通过"],
            ["峰值", "400", "168 ms", "286 ms", "1,180", "0.18%", "通过"],
            ["超载", "500", "276 ms", "495 ms", "1,215", "1.36%", "关注"],
        ],
        "findings": ["400 并发是当前版本的稳定工作点。", "超过 450 并发后吞吐增益明显收敛，时延快速上升。", "应用节点 CPU 是首要瓶颈，建议优先优化序列化与日志链路。"],
    },
    {
        "filename": "02_系统容量评估报告.docx",
        "title": "系统容量评估报告",
        "subtitle": "未来 12 个月业务增长与基础设施容量测算",
        "scope": "生产集群容量模型（模拟）",
        "summary": "按月活跃用户增长 8%、峰值系数 2.4 测算，现有 6 节点集群可支撑至第 8 个月。若保持 30% 安全余量，应在第 6 个月前扩容 2 个应用节点，并同步提升缓存容量。",
        "metrics": [("当前容量", "5.6M req/day", "基线"), ("安全容量", "7.4M req/day", "余量 32%"), ("耗尽月份", "第 8 月", "预测"), ("建议扩容", "+2 节点", "第 6 月")],
        "chart_title": "需求预测与安全容量边界",
        "x": list(range(1, 13)),
        "series": [("预测峰值负载", [54, 58, 63, 68, 73, 79, 85, 92, 99, 107, 116, 125], BLUE2), ("安全容量", [100] * 12, RED)],
        "table": [
            ["资源层", "当前配置", "当前利用率", "安全上限", "剩余余量", "建议"],
            ["应用节点", "6 × 8C16G", "62%", "70%", "11%", "第 6 月扩容"],
            ["数据库", "16C64G", "55%", "75%", "27%", "观察慢查询"],
            ["Redis", "3 × 16G", "68%", "75%", "9%", "优先扩容"],
            ["消息队列", "3 节点", "43%", "70%", "39%", "暂不调整"],
        ],
        "findings": ["容量模型采用 30% 安全余量，避免只按平均负载规划。", "Redis 内存余量最小，是最早需要处理的资源层。", "扩容后应重复峰值压测，校准线性扩展假设。"],
    },
    {
        "filename": "03_压力与稳定性测试报告.docx",
        "title": "压力与稳定性测试报告",
        "subtitle": "8 小时稳态负载、突发流量与故障恢复验证",
        "scope": "核心交易链路与依赖服务",
        "summary": "8 小时稳定性测试期间累计处理 27.4M 请求，无服务中断。内存由 58% 缓慢上升至 67%，Full GC 次数可控；突发流量阶段出现短时限流，但系统在 96 秒内恢复。",
        "metrics": [("测试时长", "8 h", "连续"), ("累计请求", "27.4M", "模拟"), ("可用性", "99.97%", "达标"), ("恢复时间", "96 s", "达标")],
        "chart_title": "长稳测试资源利用率趋势",
        "x": list(range(0, 9)),
        "series": [("CPU %", [58, 62, 64, 63, 67, 65, 68, 66, 64], BLUE2), ("内存 %", [58, 59, 60, 61, 63, 64, 65, 66, 67], GOLD)],
        "table": [
            ["验证项", "注入条件", "业务影响", "恢复时间", "判定"],
            ["持续负载", "900 TPS / 8h", "无中断", "不适用", "通过"],
            ["流量突增", "30 秒内 +80%", "0.6% 限流", "96 秒", "通过"],
            ["单节点下线", "摘除 1 个应用节点", "P95 +42 ms", "54 秒", "通过"],
            ["缓存抖动", "命中率降至 72%", "DB CPU +18%", "128 秒", "关注"],
        ],
        "findings": ["稳态测试未发现明显吞吐衰减或线程池耗尽。", "内存存在缓慢爬升，应继续执行 24 小时测试排除泄漏。", "缓存命中率下降时数据库压力传导明显，需完善降级策略。"],
    },
    {
        "filename": "04_扩容方案与容量规划报告.docx",
        "title": "扩容方案与容量规划报告",
        "subtitle": "分阶段扩容策略、预算估算与验收指标",
        "scope": "应用、缓存、数据库与可观测性平台",
        "summary": "建议采用“两阶段扩容 + 自动伸缩”方案：近期增加 2 个应用节点并扩展 Redis，季度内完成数据库读写分离。方案预计将安全吞吐提升至 2,100 TPS，并维持不少于 35% 的峰值余量。",
        "metrics": [("目标吞吐", "2,100 TPS", "↑ 78%"), ("安全余量", "≥35%", "目标"), ("实施周期", "6 周", "两阶段"), ("预算估算", "¥286k/年", "模拟")],
        "chart_title": "各阶段安全吞吐能力预测",
        "x": [0, 1, 2, 3],
        "xlabels": ["当前", "阶段一", "阶段二", "自动伸缩"],
        "series": [("安全吞吐 TPS", [1180, 1560, 1880, 2100], BLUE2), ("峰值需求 TPS", [920, 1050, 1210, 1360], GOLD)],
        "table": [
            ["阶段", "时间窗", "关键动作", "能力目标", "验收条件", "风险"],
            ["阶段一", "第 1–2 周", "应用 +2；Redis 扩容", "1,560 TPS", "P95 < 300 ms", "低"],
            ["阶段二", "第 3–6 周", "读写分离；连接池优化", "1,880 TPS", "错误率 < 0.2%", "中"],
            ["持续优化", "第 7 周起", "自动伸缩；容量告警", "2,100 TPS", "余量 ≥ 35%", "中"],
        ],
        "findings": ["先扩展无状态应用和缓存，可快速释放近期容量风险。", "数据库架构调整需灰度实施，并准备完整回滚方案。", "每阶段必须以相同脚本复测，验收通过后再进入下一阶段。"],
    },
]


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd")) or OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    if shd.getparent() is None:
        tc_pr.append(shd)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for key, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{key}")) or OxmlElement(f"w:{key}")
        node.set(qn("w:w"), str(value)); node.set(qn("w:type"), "dxa")
        if node.getparent() is None: tc_mar.append(node)


def set_table_widths(table, widths: list[int]) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.first_child_found_in("w:tblW")
    tbl_w.set(qn("w:w"), str(sum(widths))); tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.first_child_found_in("w:tblInd")
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd"); tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120"); tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid): grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol"); col.set(qn("w:w"), str(width)); grid.append(col)
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            tc_w = cell._tc.get_or_add_tcPr().first_child_found_in("w:tcW")
            tc_w.set(qn("w:w"), str(width)); tc_w.set(qn("w:type"), "dxa")


def set_font(run, size=10.5, color=INK, bold=False, name="Hiragino Sans GB") -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Hiragino Sans GB")
    run._element.rPr.rFonts.set(qn("w:ascii"), name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), name)
    run.font.size = Pt(size); run.font.color.rgb = RGBColor.from_string(color); run.bold = bold


def add_field(paragraph, instruction: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    text = OxmlElement("w:instrText"); text.set(qn("xml:space"), "preserve"); text.text = instruction
    separate = OxmlElement("w:fldChar"); separate.set(qn("w:fldCharType"), "separate")
    display = OxmlElement("w:t"); display.text = "1"
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    for node in (begin, text, separate, display, end): run._r.append(node)


def chart(path: Path, title: str, xs: list, series: list, xlabels=None) -> None:
    width, height = 1400, 700
    img = Image.new("RGB", (width, height), "white"); d = ImageDraw.Draw(img)
    f_title = ImageFont.truetype(FONT, 38); f_axis = ImageFont.truetype(FONT, 25); f_small = ImageFont.truetype(FONT, 22)
    d.text((70, 35), title, font=f_title, fill="#24323D")
    left, top, right, bottom = 110, 120, 1320, 590
    d.line((left, top, left, bottom), fill="#71818C", width=3); d.line((left, bottom, right, bottom), fill="#71818C", width=3)
    values = [v for _, vals, _ in series for v in vals]; ymax = max(values) * 1.12
    for i in range(5):
        y = bottom - (bottom-top) * i / 4; val = ymax*i/4
        d.line((left, y, right, y), fill="#DCE3E8", width=2)
        d.text((15, y-14), f"{val:.0f}", font=f_small, fill="#667681")
    n = len(xs)
    for j, (name, vals, color) in enumerate(series):
        pts = []
        for i, val in enumerate(vals):
            x = left + (right-left) * i / max(n-1, 1); y = bottom-(bottom-top)*val/ymax
            pts.append((x,y))
        d.line(pts, fill="#"+color, width=7)
        for p in pts: d.ellipse((p[0]-6,p[1]-6,p[0]+6,p[1]+6), fill="#"+color)
        lx = 835 + j*240; d.line((lx, 82, lx+50, 82), fill="#"+color, width=7); d.text((lx+62, 66), name, font=f_small, fill="#24323D")
    labels = xlabels or [str(x) for x in xs]
    for i, label in enumerate(labels):
        x = left + (right-left)*i/max(n-1,1); box=d.textbbox((0,0), str(label), font=f_small)
        d.text((x-(box[2]-box[0])/2, bottom+18), str(label), font=f_small, fill="#667681")
    img.save(path, quality=92)


def style_document(doc: Document) -> None:
    sec = doc.sections[0]
    sec.page_width = Inches(8.5); sec.page_height = Inches(11)
    sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Inches(1)
    sec.header_distance = sec.footer_distance = Inches(0.492)
    normal = doc.styles["Normal"]
    normal.font.name = "Hiragino Sans GB"; normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Hiragino Sans GB")
    normal.font.size = Pt(10.5); normal.font.color.rgb = RGBColor.from_string(INK)
    normal.paragraph_format.space_after = Pt(6); normal.paragraph_format.line_spacing = 1.10
    for name, size, before, after, color in (("Title",24,0,8,INK),("Subtitle",12,0,12,MUTED),("Heading 1",16,16,8,BLUE2),("Heading 2",13,12,6,BLUE2),("Heading 3",12,8,4,BLUE)):
        st=doc.styles[name]; st.font.name="Hiragino Sans GB"; st._element.rPr.rFonts.set(qn("w:eastAsia"),"Hiragino Sans GB")
        st.font.size=Pt(size); st.font.color.rgb=RGBColor.from_string(color); st.font.bold=name!="Subtitle"
        st.paragraph_format.space_before=Pt(before); st.paragraph_format.space_after=Pt(after); st.paragraph_format.keep_with_next=True


def add_header_footer(doc: Document, title: str) -> None:
    sec = doc.sections[0]
    hp=sec.header.paragraphs[0]; hp.text=f"性能与容量测试中心  |  {title}"; hp.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    for r in hp.runs: set_font(r, 8.5, MUTED)
    fp=sec.footer.paragraphs[0]; fp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=fp.add_run("内部测试样例  ·  "); set_font(r,8.5,MUTED); add_field(fp,"PAGE")


def add_metrics(doc: Document, metrics) -> None:
    table=doc.add_table(rows=2, cols=4); set_table_widths(table,[2340]*4)
    for i,(label,value,delta) in enumerate(metrics):
        c=table.cell(0,i); set_cell_shading(c, BLUE); set_cell_margins(c,100,100,70,100)
        p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run(label); set_font(r,9,WHITE,True)
        c=table.cell(1,i); set_cell_shading(c, PALE); set_cell_margins(c,120,100,120,100)
        p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run(value+"\n"); set_font(r,15,BLUE,True); r=p.add_run(delta); set_font(r,8.5,GREEN if "达标" in delta or "↑" in delta or "余量" in delta else MUTED,False)


def add_data_table(doc: Document, data: list[list[str]]) -> None:
    cols=len(data[0]); table=doc.add_table(rows=len(data), cols=cols)
    widths = [9360//cols]*cols; widths[-1] += 9360-sum(widths); set_table_widths(table,widths)
    for ri,row in enumerate(data):
        for ci,value in enumerate(row):
            cell=table.cell(ri,ci); set_cell_margins(cell,90,90,90,90); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if ri==0: set_cell_shading(cell, BLUE)
            elif ri%2==0: set_cell_shading(cell, PALE)
            p=cell.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.LEFT if (ci in (0,2) and cols<=6) else WD_ALIGN_PARAGRAPH.CENTER
            r=p.add_run(value); set_font(r,8.5,WHITE if ri==0 else INK,ri==0)
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))


def add_bullet(doc: Document, text: str) -> None:
    p=doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after=Pt(4); p.paragraph_format.left_indent=Inches(.5); p.paragraph_format.first_line_indent=Inches(-.25)
    r=p.add_run(text); set_font(r,10.5)


def build(report: dict) -> Path:
    doc=Document(); style_document(doc); add_header_footer(doc, report["title"])
    p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(26); r=p.add_run("PERFORMANCE & CAPACITY"); set_font(r,10,BLUE2,True)
    p=doc.add_paragraph(style="Title"); p.add_run(report["title"])
    p=doc.add_paragraph(style="Subtitle"); p.add_run(report["subtitle"])
    p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(16)
    for label,value in (("报告范围",report["scope"]),("报告版本","V1.0 · 测试样例"),("生成日期",str(date.today())),("数据说明","模拟数据，仅用于功能、性能与容量测试")):
        r=p.add_run(label+"："); set_font(r,9.5,MUTED,True); r=p.add_run(value+"    "); set_font(r,9.5,INK)
    add_metrics(doc, report["metrics"])
    doc.add_paragraph("执行摘要", style="Heading 1")
    p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(10); r=p.add_run(report["summary"]); set_font(r,11,INK)
    doc.add_paragraph("结论：当前结果可作为系统测试基线；正式决策前需使用生产等价环境复测。", style="Intense Quote")

    doc.add_paragraph("1. 测试目标与方法", style="Heading 1")
    doc.add_paragraph("本报告用于验证系统在不同业务负载下的吞吐能力、响应时延、资源消耗和恢复能力，并形成可重复的容量判断依据。")
    for item in ("测试环境：3 个应用节点、1 个主数据库、3 节点缓存集群。", "流量模型：读写比 7:3，包含登录、查询、提交与批量任务。", "判定口径：P95 < 300 ms、错误率 < 0.5%、CPU 稳态 < 70%。"):
        add_bullet(doc,item)
    doc.add_paragraph("测试限制", style="Heading 2")
    doc.add_paragraph("样例报告中的业务量、资源配置与预算均为合成数据，主要用于验证 DOCX 上传、预览、检索、分页、图表渲染和容量处理能力。")

    doc.add_page_break()
    doc.add_paragraph("2. 核心测试结果", style="Heading 1")
    asset=TMP/(Path(report["filename"]).stem+".png"); chart(asset,report["chart_title"],report["x"],report["series"],report.get("xlabels"))
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next=True
    p.add_run().add_picture(str(asset), width=Inches(6.35))
    p=doc.add_paragraph("图 1  " + report["chart_title"]); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for r in p.runs: set_font(r,9,MUTED)
    doc.add_paragraph("测试数据明细", style="Heading 2"); add_data_table(doc, report["table"])
    p=doc.add_paragraph("表 1  关键场景与容量指标（模拟数据）"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for r in p.runs: set_font(r,9,MUTED)

    doc.add_paragraph("3. 主要发现", style="Heading 1")
    for item in report["findings"]: add_bullet(doc,item)
    doc.add_paragraph("风险分级", style="Heading 2")
    risk=[["等级","触发条件","处理时限","当前状态"],["高","错误率 ≥ 1% 或服务不可用","立即","未触发"],["中","P95 超标或余量 < 20%","5 个工作日","需跟踪"],["低","指标轻微漂移","下个迭代","观察"]]
    add_data_table(doc,risk)

    doc.add_paragraph("4. 建议与行动计划", style="Heading 1")
    actions=[["优先级","行动项","负责人","目标日期","验收指标"],["P0","复核关键压测脚本与流量模型","性能负责人","T+3 天","脚本覆盖率 100%"],["P1","优化应用热点与缓存策略","研发团队","T+14 天","P95 降低 15%"],["P1","补充长稳与故障注入测试","SRE 团队","T+21 天","连续运行 24h"],["P2","建立月度容量复盘机制","架构组","每月","余量 ≥ 30%"]]
    add_data_table(doc,actions)
    doc.add_paragraph("验收清单", style="Heading 2")
    for item in ("使用相同数据集和压测脚本完成复测。", "导出监控快照、错误样本与资源利用率明细。", "确认容量阈值、告警策略和回滚路径。", "由研发、测试、SRE 三方共同签署结论。"):
        add_bullet(doc,"☐ "+item)
    doc.add_paragraph("附录：指标定义", style="Heading 1")
    defs=[["指标","定义"],["TPS","每秒成功完成的业务事务数。"],["P95","95% 请求的响应时间不超过该值。"],["错误率","失败请求数占总请求数的比例。"],["安全余量","安全容量与预测峰值需求之间的可用空间。"]]
    add_data_table(doc,defs)
    p=doc.add_paragraph("文档结束 · 本文档为自动生成的测试样例"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for r in p.runs: set_font(r,8.5,MUTED)
    path=OUT/report["filename"]; doc.save(path); return path


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    TMP.mkdir(parents=True)
    files=[build(r) for r in REPORTS]
    shutil.rmtree(TMP)
    for f in files: print(f)


if __name__ == "__main__":
    main()
