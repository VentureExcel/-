import sys
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
sys.path.insert(0, ".")
from content import *

NAVY, TEAL, RED = RGBColor(0x1F, 0x3A, 0x5F), RGBColor(0x2A, 0x7F, 0x8E), RGBColor(0xB0, 0x00, 0x20)
FONT = "Microsoft YaHei"
doc = Document(); s0 = doc.sections[0]
s0.page_width, s0.page_height = Cm(21), Cm(29.7); s0.left_margin = s0.right_margin = Cm(1.9); s0.top_margin = Cm(1.9); s0.bottom_margin = Cm(1.7)


def setf(st, size, bold=None, color=None):
    st.font.name = FONT; st.font.size = Pt(size)
    if bold is not None: st.font.bold = bold
    if color is not None: st.font.color.rgb = color
    r = st.element.get_or_add_rPr(); rf = r.find(qn("w:rFonts"))
    if rf is None: rf = OxmlElement("w:rFonts"); r.append(rf)
    rf.set(qn("w:eastAsia"), FONT)


setf(doc.styles["Normal"], 10.5); doc.styles["Normal"].paragraph_format.line_spacing = 1.35; doc.styles["Normal"].paragraph_format.space_after = Pt(4)
for n, z, c in (("Heading 1", 17, NAVY), ("Heading 2", 13.5, TEAL), ("Heading 3", 11.5, NAVY)):
    setf(doc.styles[n], z, True, c); doc.styles[n].paragraph_format.space_before = Pt(14 if n == "Heading 1" else 9); doc.styles[n].paragraph_format.space_after = Pt(5)


def shade(c, hexc):
    p = c._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexc); p.append(sh)


def para(t, bold=False, color=None, size=None, align=None, italic=False):
    p = doc.add_paragraph(); r = p.add_run(t); r.bold, r.italic = bold, italic
    if color is not None: r.font.color.rgb = color
    if size: r.font.size = Pt(size)
    if align is not None: p.alignment = align
    return p


def bullets(items):
    for t in items:
        p = doc.add_paragraph(style="List Bullet")
        if "::" in t:
            h, b = t.split("::", 1); r = p.add_run(h); r.bold = True; p.add_run(b)
        else: p.add_run(t)


def table(rows, widths, fs=8.5, sev=None):
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for j, w in enumerate(widths): t.columns[j].width = Cm(w)
    colors = {"致命": "F4B6B6", "严重": "FFD9A8", "中": "FFF1BF", "低": "DDE6EE"}
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.width = Cm(widths[j]); c.text = ""
            p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(1); p.paragraph_format.line_spacing = 1.12
            r = p.add_run(str(v)); r.font.size = Pt(fs)
            if i == 0:
                r.bold = True; r.font.color.rgb = RGBColor(255, 255, 255); shade(c, "1F3A5F")
            else:
                if j == 0: r.bold = True
                if sev is not None and j == sev and v in colors: shade(c, colors[v]); r.bold = True
                elif i % 2 == 0: shade(c, "F2F4F7")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def fig(name, cap, w=16.3):
    doc.add_picture(f"assets/{name}", width=Cm(w)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(cap, size=9, color=RGBColor(0x5B, 0x66, 0x75), align=WD_ALIGN_PARAGRAPH.CENTER, italic=True)


def callout(t, fill="FFF6D6"):
    tb = doc.add_table(rows=1, cols=1); tb.style = "Table Grid"; c = tb.cell(0, 0); shade(c, fill); c.text = ""
    r = c.paragraphs[0].add_run(t); r.font.size = Pt(10); doc.add_paragraph().paragraph_format.space_after = Pt(2)


# 封面
for _ in range(5): doc.add_paragraph()
para("主力净流入策略 V4.1", bold=True, color=NAVY, size=26, align=WD_ALIGN_PARAGRAPH.CENTER)
para("投研评审、V4.2 优化方案与回测方案", bold=True, color=TEAL, size=21, align=WD_ALIGN_PARAGRAPH.CENTER)
para("—— 面向 A 股的机构级评审:不足、调整、可交由本地 Claude Code 执行的回测 ——", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
para("评审对象:V4.1 每日选股报告 2026-10-09(候选池 387 只 / 观察 60 只 / 0 买入)", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
para("日期:2026-10-09", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
callout("说明:本评审基于你上传的报告与 Excel 中可见的数字与规则文字,未看到生产脚本与历史数据库,因此\"证据\"限于 2026-10-09 截面;凡涉及历史有效性的判断,均已转化为可检验的假设,交由本地回测验证。回测框架已用合成数据完成无前视/T+1/涨停/安慰剂等 9 项自检,合成结果不是策略证据。仅供研究,不构成投资建议。")
doc.add_page_break()

doc.add_heading("1  评审结论", 1)
para("总评:V4.1 的工程纪律(数据质量门、拒绝估算、方向自检、涨停硬约束、如实标注选择性偏差)优于多数散户级方案,但在\"策略是否有效\"这一根本问题上证据为零:没有历史回测、没有样本外、没有成本与持有期定义。当前 0 买入是 C1 熔断的结果,而不是风控的结果。在补齐证据之前,V4.1 只适合作为观察工具,不应实盘。")
table([
    ["评审维度", "评级(1~5)", "结论"],
    ["数据与点时性", "3", "质量门细致;但依赖供应商快照、不可回放、历史资金流口径未沉淀"],
    ["信号有效性证据", "1", "无 IC/分层/样本外;核心因子预测力未检验"],
    ["评分结构", "2", "名义四维实为约 2.5 维;动量与反转混合(U 型);批内相对化缺时间序列信息"],
    ["风险与熔断", "2", "多数熔断为恒真/弱检验;宏观闸门阈值几乎不触发;无策略回撤熔断"],
    ["执行与组合", "1", "无持有期/止损/仓位/成本/T+1 建模"],
    ["流程与治理", "3", "纪律好;缺预先登记验收标准与试验次数记录"],
], [4.0, 2.4, 10.6], fs=9)
doc.add_heading("1.1  做得好的地方(保留)", 2)
bullets(["数据质量门::单位核对、5 日资金流逐日取真实值(严禁\"当日×3\")、缺失/零值剔除、C5 如实披露选择性偏差。",
         "涨停硬约束::涨幅达板块上限不给买入区间,符合 A 股可成交性现实。",
         "方向自检与风险披露::每只标的有\"最弱一维/主风险\",避免只讲优点。",
         "禁止批内 60 分位替代绝对门槛::识别了\"恒真\"陷阱——这个问题意识是对的,只是解法还要换(见 P6)。"])
doc.add_heading("1.2  最关键的 5 个问题", 2)
bullets(["P1 无样本外证据(致命)::定稿 2026-08-12,至今 60 个交易日仅观察,0 买入,所有参数未经检验。",
         "P2 核心因子未验证(致命)::\"主力净流入\"是数据商按单笔大小分类的成交结果,买卖必有对手方;短期可能延续也可能反转,需自测 IC。",
         "P3/P4 评分共线与 U 型::D1 与资金/市值比 ρ=0.97,四维有效维度≈2.5;最跌与最涨的两端分数都偏高。",
         "P6/P7 熔断与惩罚形同虚设::C2 恒真;Overheat 惩罚仅换出 6/60;C1 在批内构造下无信息。",
         "P10 执行层缺失::没有持有期、止损、成本、T+1,收益无法计算。"])
fig("ev1_corr.png", "图1  候选池 387 只的 Spearman 相关:D1 与资金/市值比 0.97,D1–D2 0.83(数据来自 2026-10-09 评分明细)", 12.5)
fig("ev2_ushape.png", "图2  修正综合分按当日涨跌幅分五档:最跌与最涨两端都偏高(U 型),D4 与 Overheat 对下跌股双重\"优待\"", 16)
doc.add_page_break()

doc.add_heading("2  问题清单(15 项)", 1)
para("按严重度排序;\"证据\"全部来自你提供的 10-09 报告/Excel;\"实验\"对应第 4 章的回测实验编号。")
table([["编号", "严重度", "问题", "证据", "调整", "实验"]] + [[i[0], i[1], i[3], i[4], i[6], i[7]] for i in ISSUES],
      [1.0, 1.3, 3.2, 5.6, 5.2, 1.2], fs=7.8, sev=1)
fig("ev3_overheat.png", "图3  1.5×Overheat 在前 60 名里只换出 6 只", 9.5)
fig("ev4_size.png", "图4  观察名单的市值中位数是候选池的 2.2 倍:无意中的大市值倾斜(未做市值中性)", 9.5)

doc.add_heading("3  V4.2 调整方案", 1)
doc.add_heading("3.1  设计原则", 2)
bullets(["先因子后策略::没有通过 IC 与分层检验的因子,不进入打分。",
         "动量与反转分开::同一资金信号在\"上涨趋势中\"和\"超跌后\"含义不同,各自一个子策略、各自回测。",
         "硬过滤优于减法惩罚::追高与接飞刀用可审计的区间过滤,而不是调一个无来源的系数。",
         "熔断要降低真实风险::数据熔断、环境闸门(敞口)、策略回撤熔断、容量熔断。",
         "执行先于收益::T+1、涨跌停、成本、容量进入回测,再谈净值。",
         "预先登记、一次性样本外::验收门槛先定;样本外规则冻结后只看一次;记录全部试验次数。"])
fig("v42_arch.png", "图5  V4.2 架构", 16.2)
doc.add_heading("3.2  V4.1 → V4.2 逐项调整", 2)
table([["领域", "V4.1 现状", "V4.2 调整", "理由"]] + [list(c) for c in CHANGES], [2.2, 3.8, 7.3, 3.7], fs=8)
doc.add_heading("3.3  V4.2 默认规则(待回测校准的初值)", 2)
table([
    ["模块", "默认设定(初值,非结论)", "校准实验"],
    ["股票池", "非 ST;上市>120 日;市值 30~500 亿;20 日均成交额≥1 亿;非停牌;涨停不买", "E3"],
    ["过滤", "5 日涨幅∈[-12%,+25%];mom:5 日资金累计>0 且收盘>MA20;rev:5 日资金累计>0 且 BIAS20<-8% 且 5 日跌幅<0", "E4"],
    ["因子(mom)", "净流入占成交额 5 日 30%、相对自身 60 日 z 20%、连续净流入天数 10%、主力-小单背离 10%、20 日趋势 10%、换手相对强度 -5%、ATR% -15%;行业+市值中性后截面分位加权", "E1/E4"],
    ["环境闸门", "5 项各 1 分:广度(站上 20 日线)≥35%、成交额 250 日分位≥30%、指数>MA60、跌停占比≤2%、波动率分位≤90% → 敞口 0/0/25/50/75/100%", "E6"],
    ["组合", "Top10(行业≤2 只);单票≤15%(分仓内);单票≤20 日成交额 5%", "E3/E5"],
    ["持有与退出", "持有 5 个隔夜;7% 止损(次日起、最低价触发,跳空按开盘);5 日资金累计转负离场(待加入);策略 20 日净值回撤熔断", "E3/E7"],
    ["成本", "佣金万 2.5×2、印花税 0.05%(卖)、过户费 0.001%×2、滑点 10bp + 冲击 10bp×参与率", "E5"],
], [2.3, 12.0, 2.7], fs=8.5)

doc.add_heading("4  回测方案", 1)
doc.add_heading("4.1  目标与原则", 2)
para("回答三个问题:(1) V4.1 的信号有没有预测力,收益来自哪里?(2) V4.2 的改动是否带来可复现的改进?(3) 扣除成本、考虑 T+1 与容量之后是否仍然盈利,且通过统计显著性与稳健性检验?")
fig("v42_timeline.png", "图6  时序与样本划分", 16)
bullets(["点时数据::所有字段取 T 日收盘后可得值;股票池含退市/ST/停牌;不用最新市值/行业回填历史。",
         "成交假设::T+1 开盘价成交;涨停开盘买不到、停牌无法成交、跌停锁死顺延卖出;次日起可卖。",
         "基准::中证 500 与中证 1000 等权混合(与 30~500 亿市值池相近);同时报告全 A 等权。",
         "区间::训练 2021-01~2024-12(或库内最早)、验证 2025、样本外 2026-01-05~最新;样本外只看一次。",
         "统计::Newey-West t、块自助法、通缩夏普(用总试验次数)、随机打乱与信号延迟检验。"])
doc.add_heading("4.2  实验矩阵", 2)
table([["编号", "实验", "预先登记的假设", "通过标准"]] + [[e[0], e[1], e[3], e[6]] for e in EXPERIMENTS], [1.0, 2.6, 7.4, 6.0], fs=8.2)
fig("v42_gates.png", "图7  实验流程与停止规则", 16)
doc.add_heading("4.3  验收门槛(预先登记)", 2)
table([["编号", "名称", "指标", "阈值", "说明"]] + [[g[0], g[1], g[2], (f"{g[3]:.0%}" if abs(g[3]) >= 0.05 and g[3] != 0.02 else f"{g[3]}"), g[4]] for g in GATES], [1.2, 2.4, 6.4, 1.8, 5.2], fs=8.5)
callout("规则:全部 PASS 才建议进入 ≥3 个月的前向模拟盘;任一 FAIL 回到 E1/E2 找根因,不得放宽阈值。阈值是建议初值,你可按风险偏好调整,但必须在看到样本外结果之前确定;配套 Excel《验收门槛》自动判定 PASS/FAIL。", "E3F1F4")
doc.add_heading("4.4  数据需求(本地库)", 2)
table([["表", "字段", "单位", "点时规则", "检验"]] + [list(d) for d in DATA_DICT], [1.6, 3.0, 1.3, 6.0, 5.1], fs=8)
para("若本地库的资金流历史不足 2 年:E1~E8 无法给出可靠结论,应先把历史补齐(同一口径),或改为\"每日全池快照 + 前向跟踪\";不得用估算数据补历史。", color=RED)
doc.add_heading("4.5  防坑清单", 2)
bullets(["幸存者偏差::股票池必须含退市与 ST 历史。", "前视偏差::信号只用 T 日及以前;已用截断不变性测试证明引擎与因子无泄漏(真实数据请重做)。",
         "复权::收益用复权价,涨跌停/成交用未复权价。", "停牌/涨跌停::买不到的单要剔除,卖不出的要顺延,不能假设成交。",
         "参数过拟合::看平台区而非尖峰;记录试验次数;通缩夏普折扣。", "容量::5% 成交额上限,并给 500 万~10 亿规模的衰减曲线。",
         "成本::往返≥0.3%,年换手 40 倍时成本拖累≈6%/年(见 Excel《成本模型》)。"])

doc.add_heading("5  如何交给本地 Claude Code 执行", 1)
para("backtest/ 目录是一个可直接运行的回测框架,配套 CLAUDE_CODE_TASK.md 是逐步任务书。")
table([
    ["步骤", "做什么", "产出 / 门槛"],
    ["1 摸库", "探查日K/资金流/行业/指数表,确认单位、区间、是否含退市", "db_schema.md"],
    ["2 配置", "复制 config.example.yaml → config.yaml,映射真实列名", "数据体检达标"],
    ["3 对齐", "把生产评分封装成 V41_HOOK,前 60 名重合率≥95%", "消除复刻偏差"],
    ["4 自检", "python selftest.py 全部 PASS;真实数据重做截断不变性", "无前视证明"],
    ["5 实验", "E1→E9 严格顺序,每步有停止规则", "各实验表、净值图"],
    ["6 验收", "填《结果登记》,《验收门槛》自动判定", "回测报告.md + PASS/FAIL"],
], [2.2, 9.6, 5.2], fs=9)
doc.add_heading("5.1  框架已验证的内容(合成数据自检)", 2)
bullets(["植入的资金信号能被 IC 检出(IC≈0.058、NW-t≈12.9);无植入时 IC 不显著(t≈0.8)。",
         "V4.1 与 V4.2 的信号都通过截断不变性测试(无前视)。",
         "全部交易满足:信号日<入场日<退出日;涨停开盘无成交;滑点 0bp 的收益高于 30bp。",
         "同日随机打乱得分后收益显著低于真实信号。",
         "E1~E9 全部实验在合成数据上端到端跑通(约 3.5 分钟,300 只×520 日)。"])
callout("重要:以上只证明\"机器没坏\"。合成数据里的任何收益数字都不是对 V4.1/V4.2 的证据;真实结论必须来自你本地的历史数据。", "FFF6D6")

doc.add_heading("6  预期与决策树", 1)
table([
    ["E1 结果", "含义", "下一步"],
    ["V4.1 综合分中性后 5 日 RankIC≥0.02 且显著", "资金流信号有效,问题主要在结构", "按 V4.2 重构、做 E2~E6"],
    ["子因子有效、综合分无效", "合成方式(权重/共线/U 型)拖累", "用 IC/岭回归重做权重,拆动量/反转"],
    ["仅短周期(1~3 日)有效", "更像短线反转/情绪因子", "缩短持有期;重点看成本与容量(E5)"],
    ["全部不显著", "资金流在该池内无稳定预测力", "降级为\"流动性/风险过滤器\";更换信号来源"],
], [5.2, 5.6, 6.2], fs=9)

doc.add_heading("7  风险与局限", 1)
bullets(["评审证据仅限 2026-10-09 截面,无法替代历史回测。", "V4.1 子因子按报告文字复刻,必须与生产脚本对齐。",
         "引擎采用逐日分仓、固定名义近似,未按 100 股取整,止损用日线最低价近似;结果应视为趋势性判断而非精确净值。",
         "V4.2 的所有数值(权重、阈值、闸门)均为待校准初值;校准只允许在训练/验证区间进行。",
         "回测盈利不保证未来;仅供研究,不构成投资建议。"])
for s in doc.sections:
    fp = s.footer.paragraphs[0]; fp.text = "V4.1 评审与 V4.2 回测方案 · 仅供研究,不构成投资建议"; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in fp.runs: r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x7A, 0x84, 0x90)
doc.save("V4.1_评审与V4.2优化及回测方案.docx"); print("saved")
