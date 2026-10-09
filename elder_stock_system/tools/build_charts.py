"""Word 报告用图表(PNG)。示例行情为合成数据,示意用途。"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, str(Path(__file__).parent))
from elder_lib import Params, add_support, daily_indicators, score_row, to_weekly  # noqa: E402

A = Path(__file__).parent.parent / "step1" / "assets"
plt.rcParams.update({
    "font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#9AA5B1",
    "axes.grid": True, "grid.color": "#E6EAF0", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.dpi": 100, "savefig.dpi": 200, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlecolor": "#1F3A5F", "xtick.color": "#5B6675", "ytick.color": "#5B6675",
})
NAVY, TEAL, GOLD, RED, GREEN, BLUE, GREY = "#1F3A5F", "#2A7F8E", "#E8B04B", "#C0392B", "#2E8B57", "#4A8FD6", "#9AA5B1"

p = Params()
d = pd.read_csv(A / "sample_ohlcv.csv", parse_dates=["date"])
ind = add_support(daily_indicators(d, to_weekly(d), p), p)
sc = pd.DataFrame([score_row(ind.iloc[i], p) for i in range(len(ind))])
ind = pd.concat([ind, sc.add_prefix("sc_")], axis=1)


def save(fig, name):
    fig.savefig(A / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", name)


def box(ax, x, y, w, h, text, fc, tc="white", fs=10, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.03", fc=fc, ec="none"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc, fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.5)


def arrow(ax, x0, y0, x1, y1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color="#5B6675", lw=1.4))


# 1 三重滤网流程 ----------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 4.6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 5)
ax.text(0.1, 4.7, "三重滤网交易系统(第39节):先定方向,再找折价,最后下单", fontsize=13, fontweight="bold", color=NAVY)
steps = [("第一重滤网·潮流\n周线", "周线EMA斜率 / MACD柱斜率\n+ 动力系统\n只允许一个方向:\n上升→只买;下降→只卖空", NAVY),
         ("第二重滤网·波浪\n日线", "与潮流相反的日线波动:\n2日强力指数<0、随机指标<30、\n价格回到EMA价值区间", TEAL),
         ("第三重滤网·浪花\n买入技术", "挂单价=明日EMA估计−平均下跌穿透\n(或前日高点+1个最小单位,逐日下移)\n以折价成交,不追高", GOLD)]
for i, (t, body, c) in enumerate(steps):
    x = 0.2 + i * 3.3
    box(ax, x, 3.0, 2.9, 1.1, t, c, "white" if c != GOLD else "#1F3A5F", 11, True)
    box(ax, x, 1.15, 2.9, 1.65, body, "#F2F4F7", "#1F3A5F", 9.5)
    if i < 2:
        arrow(ax, x + 2.95, 3.55, x + 3.25, 3.55)
box(ax, 0.2, 0.1, 9.5, 0.75, "止损看中期图(日线)·止盈看长期图(周线价值区间/通道)·每笔先写下:买入价、目标价、止损价,盈亏比≥2:1", "#FFF6D6", "#1F3A5F", 10)
save(fig, "fig1_triple_screen.png")

# 2 价值区间 + 通道 + 买点 + 强力指数 -------------------------------------
v = ind.iloc[-150:].reset_index(drop=True)
x = np.arange(len(v))
fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 7.4), sharex=True, gridspec_kw={"height_ratios": [3.2, 1.1, 1]})
a1.fill_between(x, v["ema_f"], v["ema_s"], color=GOLD, alpha=0.28, label="价值区间(EMA13~EMA26)", lw=0)
a1.plot(x, v["ch_up"], color=GREY, lw=1, ls="--", label="通道上轨/下轨(约95%覆盖)")
a1.plot(x, v["ch_dn"], color=GREY, lw=1, ls="--")
a1.plot(x, v["ema_s"], color=TEAL, lw=1.6, label="EMA26")
a1.plot(x, v["ema_f"], color=GOLD, lw=1.6, label="EMA13")
a1.plot(x, v["close"], color=NAVY, lw=1.4, label="收盘价")
for g, col, lab in (("A", RED, "A级"), ("B", BLUE, "B级")):
    m = v["sc_grade"] == g
    a1.scatter(x[m], v["low"][m] * 0.985, marker="^", s=70, color=col, zorder=5, label=f"{lab}候选(评分)")
a1.set_title("价值区间与通道:在上升趋势的回调里、价值区间附近买,而不是追涨"); a1.legend(ncol=3, fontsize=8, frameon=False, loc="upper left")
a2.bar(x, v["fi2"] / 1e6, color=np.where(v["fi2"] < 0, RED, GREEN), width=0.8)
a2.set_ylabel("2日强力指数\n(百万)", fontsize=8); a2.axhline(0, color=GREY, lw=0.8)
a3.plot(x, v["stoch_k"], color=TEAL, lw=1.2, label="慢%K"); a3.plot(x, v["stoch_d"], color=GOLD, lw=1.2, label="慢%D")
a3.axhline(30, color=GREY, lw=0.8, ls=":"); a3.axhline(70, color=GREY, lw=0.8, ls=":"); a3.set_ylim(0, 100)
a3.set_ylabel("随机指标", fontsize=8); a3.legend(fontsize=8, frameon=False, ncol=2, loc="upper left")
ticks = np.arange(0, len(v), 25); a3.set_xticks(ticks); a3.set_xticklabels(v["date"].dt.strftime("%m-%d").iloc[ticks])
save(fig, "fig2_value_zone.png")

# 3 动力系统 ----------------------------------------------------------------
v = ind.iloc[-110:].reset_index(drop=True); x = np.arange(len(v))
col = np.where(v["impulse"] == 1, GREEN, np.where(v["impulse"] == -1, RED, BLUE))
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.8), sharex=True, gridspec_kw={"height_ratios": [2.6, 1]})
for i in x:
    a1.plot([i, i], [v["low"][i], v["high"][i]], color=col[i], lw=1)
    a1.plot([i - .3, i + .3], [v["close"][i]] * 2, color=col[i], lw=2.4)
a1.plot(x, v["ema_f"], color="#444", lw=1.2)
a1.set_title("动力系统:EMA13斜率(惯性)+ MACD柱斜率(能量),绿=禁止卖空,红=禁止买入,蓝=无禁止")
a2.bar(x, v["hist"], color=col, width=0.8); a2.axhline(0, color=GREY, lw=0.8); a2.set_ylabel("MACD柱", fontsize=8)
from matplotlib.lines import Line2D
a1.legend(handles=[Line2D([0], [0], color=GREEN, lw=3, label="绿(允许买入/观望)"), Line2D([0], [0], color=RED, lw=3, label="红(允许卖出/观望)"),
                   Line2D([0], [0], color=BLUE, lw=3, label="蓝(中性)")], frameon=False, fontsize=8, ncol=3, loc="upper left")
ticks = np.arange(0, len(v), 20); a2.set_xticks(ticks); a2.set_xticklabels(v["date"].dt.strftime("%m-%d").iloc[ticks])
save(fig, "fig3_impulse.png")

# 4 背离 + 假突破(取样本里最清晰的一次) ----------------------------------------
cand = ind.index[ind["false_break"]].tolist() or ind.index[ind["bull_div"]].tolist()
i1 = cand[0]
lo, hi = max(0, int(ind.loc[i1, "p_b"]) - 12), min(len(ind), i1 + 15)
v = ind.iloc[lo:hi].reset_index(drop=True); x = np.arange(len(v))
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, gridspec_kw={"height_ratios": [2, 1.2]})
a1.plot(x, v["close"], color=NAVY, lw=1.4); a1.fill_between(x, v["low"], v["high"], color=NAVY, alpha=.12, lw=0)
pb, rb = int(ind.loc[i1, "p_b"]) - lo, int(ind.loc[i1, "run_b"]) - lo
a1.axhline(ind.loc[i1, "p_l"], color=RED, ls="--", lw=1); a1.text(0, ind.loc[i1, "p_l"], " 前一低点", color=RED, va="bottom", fontsize=9)
a1.scatter([pb, rb], [ind.loc[i1, "p_l"], ind.loc[i1, "run_l"]], color=RED, s=60, zorder=5)
AP = dict(arrowstyle="-", color="#5B6675", lw=.8)
a1.annotate("A 第一底", (pb, ind.loc[i1, "p_l"]), xytext=(-10, -34), textcoords="offset points", fontsize=9, arrowprops=AP)
a1.annotate("C 价格更低(向下假突破)\n随后收盘重回前低之上", (rb, ind.loc[i1, "run_l"]), xytext=(-40, -44), textcoords="offset points", fontsize=9, arrowprops=AP)
a1.set_ylim(ind.loc[i1, "run_l"] - 1.3, None)
a1.set_title("MACD柱牛市背离 + 向下假突破(埃尔德的\"A级交易\"):价格新低而空头力量更浅")
a2.bar(x, v["hist"], color=np.where(v["hist"] >= 0, GREEN, RED), width=.8); a2.axhline(0, color=GREY, lw=.8)
a2.scatter([pb, rb], [ind.loc[i1, "p_h"], ind.loc[i1, "run_h"]], color=NAVY, s=60, zorder=5)
a2.annotate("A谷(深)", (pb, ind.loc[i1, "p_h"]), xytext=(28, 4), textcoords="offset points", fontsize=9, arrowprops=AP)
a2.annotate("C谷(浅):柱线回升 = 买入信号", (rb, ind.loc[i1, "run_h"]), xytext=(-30, -28), textcoords="offset points", fontsize=9, arrowprops=AP)
a2.set_ylim(ind.loc[i1, "p_h"] * 1.45, None)
a2.set_ylabel("MACD柱", fontsize=8)
ticks = np.arange(0, len(v), 10); a2.set_xticks(ticks); a2.set_xticklabels(v["date"].dt.strftime("%m-%d").iloc[ticks])
save(fig, "fig4_divergence.png")

# 5 交易解剖:挂单/止损/目标/ATR通道 ----------------------------------------------
j = ind.index[(ind["sc_grade"] != "C") & (ind.index < len(ind) - 40)][0]
pl = ind.iloc[j]
fw = ind.iloc[j - 25: j + 26].reset_index(drop=True); x = np.arange(len(fw)); t0 = 25
fig, ax = plt.subplots(figsize=(10, 5.2))
entry, stop, tgt = pl["sc_entry"], pl["sc_stop"], pl["sc_target"]
ax.axhspan(stop, entry, xmin=0.48, color=RED, alpha=.10); ax.axhspan(entry, tgt, xmin=0.48, color=GREEN, alpha=.10)
ax.plot(x, fw["close"], color=NAVY, lw=1.4, label="收盘价"); ax.plot(x, fw["ema_s"], color=TEAL, lw=1.4, label="EMA26")
for k, c in zip((1, 2, 3), ("#B8C4D0", "#9AA5B1", "#6C7A89")):
    ax.plot(x, fw[f"atr_up{k}"], color=c, lw=1, ls="--"); ax.text(len(fw) - 1, fw[f"atr_up{k}"].iloc[-1], f" +{k}ATR", fontsize=8, va="center", color="#5B6675")
for lv, lab, c in ((entry, f"买入限价 {entry:.2f}", NAVY), (stop, f"止损 {stop:.2f}(尼克止损,避开整数)", RED), (tgt, f"目标 {tgt:.2f}(上轨)", GREEN)):
    ax.axhline(lv, color=c, lw=1.1, ls="-." if c != NAVY else "-"); ax.text(len(fw) - 1, lv, " " + lab, color=c, fontsize=9, ha="right", va="bottom" if c != RED else "top")
ax.text(len(fw) * 0.62, stop - 0.75, "本例随后跌破止损:亏损被限制在计划的 1R\n(合成数据示例;并非每笔交易都盈利)", ha="left", va="top", fontsize=9, color=RED)
ax.axvline(t0, color=GREY, lw=.8, ls=":"); ax.text(t0, ax.get_ylim()[0], " 信号日(收盘后计划)", fontsize=8, color="#5B6675", va="bottom")
ax.set_title(f"一笔交易的解剖:盈亏比 {pl['sc_rr']:.1f}:1,每股风险 {entry - stop:.2f} → 股数由2%法则决定")
ax.legend(frameon=False, fontsize=8, loc="lower right")
ticks = np.arange(0, len(fw), 10); ax.set_xticks(ticks); ax.set_xticklabels(fw["date"].dt.strftime("%m-%d").iloc[ticks])
save(fig, "fig5_trade_anatomy.png")

# 6 风险法则 ---------------------------------------------------------------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4), gridspec_kw={"width_ratios": [1, 1.25]})
a1.axis("off"); a1.set_xlim(0, 10); a1.set_ylim(0, 10)
a1.set_title("2%法则 · 风险控制铁三角", loc="left")
box(a1, 0.3, 7.2, 9.4, 1.8, "A 单笔最大风险额度\n= 账户资金 × 2%(专业人士≤1%)", NAVY, "white", 10)
box(a1, 0.3, 4.6, 9.4, 1.8, "B 每股风险\n= 买入价 − 止损价", TEAL, "white", 10)
box(a1, 0.3, 2.3, 9.4, 1.6, "C 最大股数 = A ÷ B(按100股取整)", GOLD, NAVY, 10, True)
a1.text(0.3, 0.2, "例:资金100万、风险1%=1万\n买33.09、止损32.23 → 每股风险0.86\n→ 最多11600股(再受单只仓位上限约束)", fontsize=8.5, color="#5B6675", va="bottom")
steps = ["买A\n风险2%", "买B", "买C", "D被拒\n已达6%", "A止损\n上移保本", "买D", "E被拒", "B止损\n触发(-2%)"]
used = [2, 4, 6, 6, 4, 6, 6, 6]
cols = [GREEN if u < 6 else RED for u in used]
a2.bar(range(len(used)), used, color=cols, width=.62)
a2.axhline(6, color=RED, lw=1.2, ls="--"); a2.text(-0.45, 6.15, "6%上限(红=已达上限)", color=RED, ha="left", fontsize=9)
for i, u in enumerate(used): a2.text(i, u + .12, f"{u}%", ha="center", fontsize=8, color="#5B6675")
a2.set_xticks(range(len(used))); a2.set_xticklabels(steps, fontsize=7.5); a2.set_ylim(0, 7.4); a2.set_ylabel("本月风险占用(已亏损+持仓风险)")
a2.set_title("6%法则 · 书中示例的风险额度占用轨迹", loc="left")
save(fig, "fig6_risk_rules.png")

# 7 选股漏斗 ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6.2)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 9.0)
layers = [("L0 大盘闸门(市场温度)", "周线动力系统 + 50日均线占比 + 20日新高-新低 → 决定风险额度系数 0/50%/75%/100%", NAVY),
          ("L1 股票池与流动性(负面规则)", "剔除ST/次新/停牌/涨跌停;20日均成交额不足;ADX过低的死水股;限制最大仓位", "#2B5A87"),
          ("L2 第一重滤网·周线潮流", "周EMA26向上 + 周动力系统非红(背离类形态仅要求非红)", TEAL),
          ("L3 第二重滤网·日线回调", "日线非红;2日强力指数<0且非数周新低;价格回到价值区间/通道内", "#3C9A8E"),
          ("L4 买入形态", "A回调到价值区 / B MACD柱牛市背离+向下假突破 / C极端超卖反弹", "#6BB0A0"),
          ("L5 评分与A级交易判定", "趋势25+回调25+形态25+量能10+盈亏比15,≥70分且盈亏比≥2:1才是A级", GOLD),
          ("L6 挂单·止损·仓位", "折价买入价 / 尼克止损 / 通道目标 / 2%与6%法则取股数", "#D98E3C")]
for i, (t, b, c) in enumerate(layers):
    w = 9.6 - i * 0.8; x0 = (10 - w) / 2; y = 7.55 - i * 1.15
    ax.add_patch(FancyBboxPatch((x0, y), w, 1.0, boxstyle="round,pad=0.01,rounding_size=0.06", fc=c, ec="none"))
    fc = "white" if c not in (GOLD, "#6BB0A0") else NAVY
    ax.text(5, y + .68, t, ha="center", va="center", color=fc, fontsize=10.5, fontweight="bold")
    ax.text(5, y + .28, b, ha="center", va="center", color=fc, fontsize=8.2)
ax.text(0.05, 8.75, "选股漏斗:逐层否决,而不是堆指标(书:交易者最大的错误是\"采购各种指标\")", fontsize=12, fontweight="bold", color=NAVY)
save(fig, "fig7_funnel.png")

# 8 评分模型 ----------------------------------------------------------------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw={"width_ratios": [1.5, 1]})
dims = ["趋势", "回调质量", "买入形态", "量能", "盈亏比"]; wts = [25, 25, 25, 10, 15]; cc = [NAVY, TEAL, GOLD, "#6BB0A0", "#D98E3C"]
left = 0
for dname, wv, c in zip(dims, wts, cc):
    a1.barh(0, wv, left=left, color=c, height=.5, edgecolor="white", lw=2)
    a1.text(left + wv / 2, 0, f"{dname}\n{wv}", ha="center", va="center", color="white" if c not in (GOLD, "#6BB0A0") else NAVY, fontsize=9, fontweight="bold"); left += wv
a1.set_xlim(0, 100); a1.set_ylim(-.6, 1.3); a1.axis("off"); a1.set_title("评分构成(满分100)", loc="left")
a1.text(0, -.5, "硬性否决(任一触发即不买):周线红 / 日线红 / 无买入形态 / 盈亏比<2 / 周趋势闸门", fontsize=8.5, color=RED)
a2.barh([2, 1, 0], [100 - p.grade_a, p.grade_a - p.grade_b, p.grade_b], left=[p.grade_a, p.grade_b, 0], color=[GOLD, TEAL, "#C9CED6"], height=.55, edgecolor="white", lw=2)
for y, t in ((2, f"A  ≥{p.grade_a:.0f}\n全额风险"), (1, f"B  {p.grade_b:.0f}-{p.grade_a:.0f}\n1/3风险"), (0, f"C  <{p.grade_b:.0f}\n放弃")):
    a2.text(50, y, t, ha="center", va="center", fontsize=9, fontweight="bold", color=NAVY)
a2.set_xlim(0, 100); a2.set_yticks([]); a2.set_title("评级与仓位权限(阈值待回测校准)", loc="left"); a2.grid(False)
save(fig, "fig8_score_model.png")

# 9 市场温度 ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3.4)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4)
ax.text(0, 3.7, "第0层:市场温度 → 风险额度系数(逆风时,最好的交易是不交易)", fontsize=12, fontweight="bold", color=NAVY)
cells = [("0-1 分", "空仓观望\n系数 0%", RED), ("2 分", "降风险\n系数 50%", GOLD), ("3 分", "稳健进攻\n系数 75%", "#6BB0A0"), ("4 分", "正常进攻\n系数 100%", GREEN)]
for i, (a, b, c) in enumerate(cells):
    box(ax, .1 + i * 2.45, 1.4, 2.25, 1.8, f"{a}\n{b}", c, "white" if c in (RED, GREEN) else NAVY, 11, True)
ax.text(.1, .85, "加分项:基准指数周EMA慢向上 +1 · 周动力系统非红 +1 · 50日均线上方占比≥40% +1 · 20日新高−新低>0 +1", fontsize=9, color="#5B6675")
ax.text(.1, .35, "例外:周动力系统为红色但出现\"尖峰反弹\"(20日NH-NL跌破-500后回升)→ 仅允许50%试探仓", fontsize=9, color="#5B6675")
save(fig, "fig9_market_regime.png")

# 10 工作簿结构 ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3.8)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4)
names = [("参数", .1, 2.9), ("日线\n(粘贴OHLCV)", 2.2, 2.9), ("周线\n(自动汇总)", 4.4, 2.9), ("评分卡\n(结论)", 6.6, 2.9), ("图表", 8.5, 2.9)]
for t, x0, y0 in names:
    box(ax, x0, y0 - 1.2, 1.7, 1.2, t, NAVY if t != "评分卡\n(结论)" else GOLD, "white" if t != "评分卡\n(结论)" else NAVY, 10, True)
for x0 in (1.85, 3.95, 6.15): arrow(ax, x0, 2.3, x0 + .3, 2.3)
box(ax, 2.2, .2, 1.7, 1.0, "市场温度", TEAL, "white", 10, True); box(ax, 4.4, .2, 1.7, 1.0, "仓位与风险\n(2%/6%)", TEAL, "white", 10, True); box(ax, 6.6, .2, 1.7, 1.0, "交易评级\n(复盘)", TEAL, "white", 10, True)
for x0 in (3.05, 5.25): arrow(ax, x0, 1.25, 7.2 if x0 > 5 else 6.9, 1.7)
ax.text(.1, 3.75, "Excel 工作簿的数据流:全部为公式,可粘贴任意股票的日线", fontsize=12, fontweight="bold", color=NAVY)
save(fig, "fig10_workbook.png")
