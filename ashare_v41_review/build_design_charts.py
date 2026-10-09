import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False})
NAVY, TEAL, GOLD, RED, GREY = "#1F3A5F", "#2A7F8E", "#E8B04B", "#C0392B", "#9AA5B1"
def box(ax, x, y, w, h, t, fc, tc="white", fs=9.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05", fc=fc, ec="none"))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", color=tc, fontsize=fs, linespacing=1.5)
def arr(ax, x0, y0, x1, y1): ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color="#5B6675", lw=1.3))

# 架构
fig, ax = plt.subplots(figsize=(10, 5.4)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 5.6)
ax.text(0.05, 5.35, "V4.2 架构:先验证、再打分;环境闸门管敞口,执行与风控落到 T+1", fontsize=12.5, fontweight="bold", color=NAVY)
box(ax, .1, 3.7, 2.2, 1.1, "数据层\n原始快照落库\n点时股票池(含退市/ST)", NAVY)
box(ax, 2.6, 3.7, 2.2, 1.1, "硬过滤\n流动性/市值/新股/ST\n5日涨幅∈[-12%,+25%]\n涨停不买", TEAL)
box(ax, 5.1, 3.7, 2.2, 1.1, "因子层(中性化)\n净流入/成交额·异常z·持续性\n散户背离·波动率·趋势", TEAL)
box(ax, 7.6, 3.7, 2.3, 1.1, "子策略\nmom 动量延续\nrev 超跌吸筹(分开评分)", GOLD, NAVY)
for x in (2.3, 4.8, 7.3): arr(ax, x, 4.25, x + .3, 4.25)
box(ax, .1, 1.95, 3.0, 1.2, "环境闸门(5项)\n广度·成交额分位·指数趋势\n跌停占比·波动率分位\n→ 敞口 0/25/50/75/100%", RED)
box(ax, 3.4, 1.95, 3.0, 1.2, "组合与执行\nTop10~20·单票≤10%·行业≤30%\nT收盘出信号→T+1开盘买\n成交额5%容量上限", NAVY)
box(ax, 6.7, 1.95, 3.2, 1.2, "退出与风控\n持有N日·7%/ATR止损\n资金流5日转负离场\n策略回撤熔断(20日净值)", TEAL)
arr(ax, 8.7, 3.7, 8.7, 3.2); arr(ax, 3.1, 2.55, 3.4, 2.55); arr(ax, 6.4, 2.55, 6.7, 2.55)
box(ax, .1, .2, 9.8, 1.2, "评估闭环:全池信号登记 → 与基准/随机组合对比 → 滚动 RankIC 监控 → 衰减报警 → 预先登记的验收门槛 G1~G4", "#F2F4F7", NAVY, 10)
arr(ax, 5, 1.95, 5, 1.4)
fig.savefig("assets/v42_arch.png", dpi=200, bbox_inches="tight"); plt.close(fig)

# 时间线 + 防前视
fig, ax = plt.subplots(figsize=(10, 3.6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 3.6)
ax.text(.05, 3.35, "回测时序与样本划分(防前视)", fontsize=12.5, fontweight="bold", color=NAVY)
ax.plot([.3, 9.7], [2.4, 2.4], color=GREY, lw=2)
ev = [(1.0, "T 日 15:00 收盘"), (3.0, "T 日 17:15 数据落地\n计算信号(只用≤T)"), (5.0, "T+1 日 09:30 开盘\n成交(涨停不买)"), (7.0, "T+1 起可卖\n持有N日/止损"), (9.0, "N 日后开盘\n离场")]
for x, t in ev:
    ax.plot(x, 2.4, "o", color=NAVY, ms=8); ax.text(x, 2.65, t, ha="center", fontsize=8.5, color=NAVY, va="bottom", linespacing=1.4)
for x0, x1, t, c in ((.3, 4.7, "训练 2021-01 ~ 2024-12(或库内最早)", TEAL), (4.7, 6.7, "验证 2025", GOLD), (6.7, 9.7, "样本外 2026-01-05 ~ 最新\n规则冻结后只看一次", RED)):
    ax.add_patch(FancyBboxPatch((x0, .6), x1 - x0 - .08, .9, boxstyle="round,pad=0.01,rounding_size=0.04", fc=c, ec="none"))
    ax.text((x0 + x1) / 2, 1.05, t, ha="center", va="center", color="white" if c != GOLD else NAVY, fontsize=9.5)
ax.text(.3, .2, "要点:信号用 T 日收盘后可得数据;成交价用 T+1 开盘;参数只在训练/验证里选,样本外不回调。", fontsize=9, color="#5B6675")
fig.savefig("assets/v42_timeline.png", dpi=200, bbox_inches="tight"); plt.close(fig)

# 实验漏斗/门槛
fig, ax = plt.subplots(figsize=(10, 3.3)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 3.3)
ax.text(.05, 3.05, "实验流程与停止规则:门槛未过就停,先找根因", fontsize=12.5, fontweight="bold", color=NAVY)
steps = [("数据体检\n+自检PASS", NAVY), ("E1 因子体检\nG1", TEAL), ("E2~E4\n消融/变体", TEAL), ("E5~E6\n成本/闸门 G3", TEAL), ("E7 滚动\nG2/G4b", GOLD), ("冻结规则\nE8 样本外 G4", RED), ("E9 安慰剂\nG4c/d", RED)]
for i, (t, c) in enumerate(steps):
    x = .1 + i * 1.42
    box(ax, x, 1.2, 1.25, 1.1, t, c, "white" if c != GOLD else NAVY, 8.5)
    if i < 6: arr(ax, x + 1.25, 1.75, x + 1.42, 1.75)
ax.text(.1, .6, "任一门槛 FAIL → 回到 E1/E2 找根因(组件/区间/数据),不得放宽阈值;全部 PASS → ≥3 个月前向模拟盘。", fontsize=9.5, color="#5B6675")
fig.savefig("assets/v42_gates.png", dpi=200, bbox_inches="tight"); plt.close(fig)
