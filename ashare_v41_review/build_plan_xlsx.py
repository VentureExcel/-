import sys
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as CL
sys.path.insert(0, ".")
from content import *

NAVY, TEAL = "1F3A5F", "2A7F8E"
F = "Microsoft YaHei"
thin = Side(style="thin", color="C9CED6"); BD = Border(left=thin, right=thin, top=thin, bottom=thin)
HF = PatternFill("solid", fgColor=NAVY); IN = PatternFill("solid", fgColor="FFF6D6"); OUT = PatternFill("solid", fgColor="E3F1F4")
wb = Workbook()


def sheet(name, title, heads, widths, rows, first=False, sev_col=None):
    ws = wb.active if first else wb.create_sheet(name)
    ws.title = name
    ws["A1"].value = title; ws["A1"].font = Font(name=F, size=14, bold=True, color=NAVY)
    for j, (h, w) in enumerate(zip(heads, widths), 1):
        c = ws.cell(row=3, column=j, value=h); c.font = Font(name=F, bold=True, color="FFFFFF", size=10); c.fill = HF; c.border = BD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); ws.column_dimensions[CL(j)].width = w
    for i, r in enumerate(rows, 4):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v); c.font = Font(name=F, size=9.5); c.border = BD
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A4"; ws.sheet_view.showGridLines = False
    if sev_col:
        rng = f"{CL(sev_col)}4:{CL(sev_col)}{3 + len(rows)}"
        for k, col in (("致命", "F4B6B6"), ("严重", "FFD9A8"), ("中", "FFF1BF"), ("低", "DDE6EE")):
            ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{k}"'], fill=PatternFill("solid", bgColor=col)))
    return ws


ws = wb.active
ws.title = "说明"
ws.column_dimensions["A"].width = 22; ws.column_dimensions["B"].width = 110
ws["A1"].value = "主力净流入策略 V4.1 评审与回测方案(Excel 配套)"; ws["A1"].font = Font(name=F, size=16, bold=True, color=NAVY)
info = [("对象", "V4.1 每日选股报告 2026-10-09(候选池 387 只、观察 60 只、0 买入)及其 Excel"),
        ("本工作簿", "问题清单(15 项,按严重度)→ V4.1→V4.2 对照 → 实验矩阵 E1~E9 → 数据字典 → 参数网格 → 成本模型(公式)→ 验收门槛(公式判定)→ 结果登记 → 路线图 → 本地 Claude Code 清单"),
        ("使用", "浅黄=可改输入;浅蓝=公式输出。本地回测跑完后,把关键数字填入《结果登记》,《验收门槛》自动给出 PASS/FAIL。"),
        ("代码", "backtest/ 目录:bt 包、selftest.py、run_backtest.py、config.example.yaml、CLAUDE_CODE_TASK.md"),
        ("重要提示", "合成数据自检结果只证明引擎无前视/无技术错误,不是 V4.1 或 V4.2 的收益证据。阈值(G1~G4)是预先登记的建议值,可按你的风险偏好调整,但必须在看到样本外结果之前确定。仅供研究,不构成投资建议。")]
for i, (k, v) in enumerate(info, 3):
    a = ws.cell(row=i, column=1, value=k); a.font = Font(name=F, bold=True); a.fill = PatternFill("solid", fgColor="F2F4F7"); a.border = BD
    b = ws.cell(row=i, column=2, value=v); b.font = Font(name=F); b.alignment = Alignment(wrap_text=True, vertical="top"); b.border = BD
    ws.row_dimensions[i].height = 44

sheet("问题清单", "V4.1 问题清单(按严重度排序)", ["编号", "严重度", "模块", "问题", "证据(来自 10-09 报告/Excel)", "影响", "调整措施", "验证实验"],
      [6, 8, 9, 28, 52, 38, 44, 10], [list(x) for x in ISSUES], sev_col=2)
sheet("V4.1→V4.2", "调整方案对照", ["领域", "V4.1 现状", "V4.2 调整", "理由"], [14, 30, 62, 36], [list(x) for x in CHANGES])
sheet("实验矩阵", "回测实验矩阵 E1~E9", ["编号", "实验", "要回答的问题", "预先登记的假设", "配置", "输出指标", "通过标准", "代码入口"],
      [6, 14, 26, 44, 34, 30, 34, 28], [list(x) for x in EXPERIMENTS])
sheet("数据字典", "数据字典与点时(PIT)规则", ["表", "字段", "单位", "点时规则", "检验"], [10, 20, 8, 52, 44], [list(x) for x in DATA_DICT])
sheet("参数网格", "参数网格", ["参数", "取值", "实验"], [26, 40, 12], [list(x) for x in GRID])

# 成本模型(公式)
ws = wb.create_sheet("成本模型")
ws["A1"].value = "交易成本模型(可改黄色单元格)"; ws["A1"].font = Font(name=F, size=14, bold=True, color=NAVY)
rows = [("佣金(单边)", 0.00025, "0.000%"), ("印花税(仅卖出)", 0.0005, "0.000%"), ("过户费(单边)", 0.00001, "0.0000%"),
        ("滑点(单边,bp)", 10, "0"), ("冲击系数(bp/参与率)", 10, "0"), ("参与率(下单额/20日成交额)", 0.02, "0.0%"),
        ("年换手(单边,倍)", 40, "0.0"), ("毛年化收益(假设)", 0.25, "0.0%")]
for i, (k, v, fmt) in enumerate(rows, 3):
    a = ws.cell(row=i, column=1, value=k); a.font = Font(name=F); a.border = BD
    b = ws.cell(row=i, column=2, value=v); b.fill = IN; b.number_format = fmt; b.border = BD; b.font = Font(name=F, bold=True)
calc = [("往返成本(%)", "=2*B3+B4+2*B5+2*B6/10000+2*B7*B8/10000", "0.000%"),
        ("年化成本拖累(%)", "=B12*B9/2", "0.0%"),
        ("净年化收益(%)", "=B10-B13", "0.0%"),
        ("盈亏平衡毛收益/笔(%)", "=B12", "0.000%")]
for i, (k, f, fmt) in enumerate(calc, 12):
    a = ws.cell(row=i, column=1, value=k); a.font = Font(name=F, bold=True); a.border = BD
    b = ws.cell(row=i, column=2, value=f); b.fill = OUT; b.number_format = fmt; b.border = BD; b.font = Font(name=F, bold=True)
ws["A17"].value = "解读:往返成本≈0.3~0.5%;若平均持有 5 日、年换手 40 倍,成本拖累可达 6~10%/年——这是资金流类短线策略最常被忽略的利润侵蚀。"
ws.column_dimensions["A"].width = 32; ws.column_dimensions["B"].width = 16; ws.sheet_view.showGridLines = False

# 结果登记 + 验收门槛(公式)
ws = wb.create_sheet("结果登记")
ws["A1"].value = "结果登记(本地回测完成后填写黄色单元格)"; ws["A1"].font = Font(name=F, size=14, bold=True, color=NAVY)
reg = [("V4.1 修正综合分:5日RankIC(中性)", None, "E1"), ("V4.1 修正综合分:NW-t", None, "E1"), ("V4.2 核心因子:5日RankIC(中性)", None, "E1"),
       ("V4.2 核心因子:NW-t", None, "E1"), ("V4.2 五分层单调性", None, "E1"), ("V4.1 样本内夏普", None, "E8"), ("V4.1 样本外夏普", None, "E8"),
       ("V4.2 样本内夏普", None, "E8"), ("V4.2 样本外夏普", None, "E8"), ("V4.2 滑点20bp年化超额", None, "E5"), ("V4.2 最大回撤", None, "E8/E4"),
       ("V4.2 通缩夏普概率", None, "E7"), ("真实信号年化", None, "E9"), ("随机打乱年化95分位", None, "E9"), ("延迟1日年化超额", None, "E9"),
       ("无延迟年化超额", None, "E9"), ("最优参数点夏普", None, "E3"), ("最优点邻域平均夏普", None, "E3"), ("总试验次数", None, "trials.csv")]
for j, (h, w) in enumerate([("指标", 36), ("取值", 14), ("来源", 12)], 1):
    c = ws.cell(row=3, column=j, value=h); c.font = Font(name=F, bold=True, color="FFFFFF"); c.fill = HF; c.border = BD; ws.column_dimensions[CL(j)].width = w
for i, (k, v, src) in enumerate(reg, 4):
    ws.cell(row=i, column=1, value=k).font = Font(name=F); ws.cell(row=i, column=1).border = BD
    b = ws.cell(row=i, column=2, value=v); b.fill = IN; b.border = BD; b.font = Font(name=F, bold=True)
    ws.cell(row=i, column=3, value=src).border = BD
ws.sheet_view.showGridLines = False
R = {k: f"结果登记!$B${i}" for i, (k, _, _) in enumerate(reg, 4)}

ws = wb.create_sheet("验收门槛")
ws["A1"].value = "预先登记的验收门槛(阈值可改;必须在看到样本外结果之前确定)"; ws["A1"].font = Font(name=F, size=14, bold=True, color=NAVY)
for j, (h, w) in enumerate([("编号", 7), ("名称", 12), ("指标", 40), ("阈值", 10), ("本次取值", 12), ("结论", 10), ("说明", 36)], 1):
    c = ws.cell(row=3, column=j, value=h); c.font = Font(name=F, bold=True, color="FFFFFF"); c.fill = HF; c.border = BD; ws.column_dimensions[CL(j)].width = w
def reg_ref(i): return list(R.values())[i]
def g(refs, expr):
    return f'=IF(COUNT({",".join(refs)})<{len(refs)},"",{expr})'
vals = {
    "G1": g([reg_ref(2)], reg_ref(2)),
    "G2": g([reg_ref(7), reg_ref(8)], f"{reg_ref(8)}/{reg_ref(7)}"),
    "G3": g([reg_ref(9)], reg_ref(9)),
    "G4a": g([reg_ref(10)], reg_ref(10)),
    "G4b": g([reg_ref(11)], reg_ref(11)),
    "G4c": g([reg_ref(12), reg_ref(13)], f"{reg_ref(12)}-{reg_ref(13)}"),
    "G4d": g([reg_ref(14), reg_ref(15)], f"{reg_ref(14)}/{reg_ref(15)}"),
    "G4e": g([reg_ref(16), reg_ref(17)], f"{reg_ref(17)}/{reg_ref(16)}")}
for i, (gid, name, metric, thr, note) in enumerate(GATES, 4):
    vals_row = [gid, name, metric, thr, vals[gid], None, note]
    for j, v in enumerate(vals_row, 1):
        c = ws.cell(row=i, column=j, value=v); c.border = BD; c.font = Font(name=F, size=10); c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(row=i, column=4).fill = IN; ws.cell(row=i, column=5).fill = OUT
    cmp_ = "<=" if gid == "G4a" else ">="
    # G4a:回撤为负数,门槛 -20%:取值 >= -20% 为通过
    ws.cell(row=i, column=6, value=f'=IF(E{i}="","待填",IF(E{i}>=D{i},"PASS","FAIL"))').fill = OUT
    ws.cell(row=i, column=6).font = Font(name=F, bold=True)
    fmt = "0.0%" if gid in ("G3", "G4a", "G4b", "G4d", "G4e", "G2") else "0.000"
    ws.cell(row=i, column=4).number_format = fmt; ws.cell(row=i, column=5).number_format = fmt
n = 3 + len(GATES)
ws.cell(row=n + 2, column=3, value="综合结论").font = Font(name=F, bold=True)
ws.cell(row=n + 2, column=6, value=f'=IF(COUNTIF(F4:F{n},"待填")>0,"待填",IF(COUNTIF(F4:F{n},"FAIL")=0,"可进入前向模拟盘","不通过"))').font = Font(name=F, bold=True, color="B00020")
ws.cell(row=n + 3, column=3, value="规则:全部 PASS 才建议进入≥3 个月前向模拟盘;任一 FAIL 回到 E1/E2 找根因,不得放宽阈值。").font = Font(name=F, size=9)
for rng, col in (("PASS", "B7E1B5"), ("FAIL", "F4B6B6")):
    ws.conditional_formatting.add(f"F4:F{n}", CellIsRule(operator="equal", formula=[f'"{rng}"'], fill=PatternFill("solid", bgColor=col)))
ws.sheet_view.showGridLines = False

sheet("路线图", "实施路线图", ["周", "里程碑", "产出", "负责"], [8, 40, 52, 16], [
    ["第1周", "数据摸底与口径对齐", "db_schema.md、config.yaml、数据体检通过、V41_HOOK 对齐(前60名重合≥95%)", "本地 Claude Code + 你"],
    ["第2周", "E1 单因子体检 + E2 消融", "因子有效性结论;负贡献组件清单;是否继续的决策点", "本地 Claude Code"],
    ["第3周", "E3~E6", "持有期/止损平台区、V4.2 变体、成本容量、环境闸门", "本地 Claude Code"],
    ["第4周", "E7 滚动样本外、规则冻结", "冻结版 V4.2 规格书;试验次数登记", "你 + 投研评审"],
    ["第5周", "E8 样本外一次性检验 + E9", "验收门槛 PASS/FAIL;回测报告", "本地 Claude Code"],
    ["第6~18周", "前向模拟盘(≥3 个月)", "每日信号登记、滚动 IC、衰减报警;与回测偏差<阈值才可小仓实盘", "你"]])
sheet("本地Claude Code清单", "本地 Claude Code 执行清单(勾选)", ["#", "任务", "完成标准", "完成?"], [5, 56, 60, 8], [
    [1, "摸清数据库结构,写 db_schema.md", "日K/资金流/行业/指数的表、列、单位、区间、是否含退市股", ""],
    [2, "填 config.yaml,单位核对为 亿元/元", "数据体检各项达标", ""],
    [3, "封装生产评分为 V41_HOOK", "5 个历史日前60名重合≥95%", ""],
    [4, "selftest.py 全部 PASS;真实数据截断不变性", "无前视证明", ""],
    [5, "E1 → 决策点", "输出因子体检表;若 V4.1 综合分无预测力,先停下汇报", ""],
    [6, "E2~E6", "输出各表与净值图", ""],
    [7, "E7 滚动样本外,记录试验次数", "trials.csv", ""],
    [8, "冻结规则,运行 E8/E9(样本外只看一次)", "回测报告.md + 验收门槛填表", ""],
    [9, "回写《结果登记》", "验收门槛得出综合结论", ""]])
wb.save("V4.1_回测方案与实验矩阵.xlsx"); print("saved")
