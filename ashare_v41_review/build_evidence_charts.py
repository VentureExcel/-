"""用用户上传的 V4.1 报告(2026-10-09 候选池 387 只)做证据图。"""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
f = "/root/.claude/uploads/86780e19-db10-5c2a-91bd-2ea57e593921/eafebee5-_____V4______2026-10-09.xlsx"
pool = pd.read_excel(f, sheet_name="候选池", header=4, dtype={"代码": str}).dropna(subset=["名称"])
sc = pd.read_excel(f, sheet_name="评分明细", header=4, dtype={"代码": str}).dropna(subset=["名称"])
m = pool.merge(sc[["代码", "D1主力质量", "D2筹码博弈", "D3量能活性", "D4空间性价比"]], on="代码")
plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#E6EAF0", "axes.axisbelow": True,
                     "axes.titleweight": "bold", "axes.titlecolor": "#1F3A5F"})
NAVY, TEAL, GOLD, RED = "#1F3A5F", "#2A7F8E", "#E8B04B", "#C0392B"
out = "assets/"
# 1 相关性热力图
cols = ["D1主力质量", "D2筹码博弈", "D3量能活性", "D4空间性价比", "资金/市值比%", "市值(亿)", "涨跌幅%", "Overheat"]
C = m[cols].corr(method="spearman")
fig, ax = plt.subplots(figsize=(7.2, 5.6))
im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=40, ha="right", fontsize=8); ax.set_yticks(range(len(cols))); ax.set_yticklabels(cols, fontsize=8)
for i in range(len(cols)):
    for j in range(len(cols)):
        ax.text(j, i, f"{C.values[i, j]:.2f}", ha="center", va="center", fontsize=7.5, color="white" if abs(C.values[i, j]) > .6 else "#333")
ax.grid(False); ax.set_title("四维分并不独立:D1≈资金/市值比(ρ=0.97),D1与D2 ρ=0.83")
fig.colorbar(im, shrink=.8); fig.savefig(out + "ev1_corr.png", dpi=200, bbox_inches="tight"); plt.close(fig)
# 2 当日涨跌幅五分位 vs 分数(U 型)
q = pd.qcut(m["涨跌幅%"], 5, labels=["最跌20%", "较跌", "中间", "较涨", "最涨20%"])
g = m.groupby(q, observed=True)[["D4空间性价比", "Overheat", "修正综合分"]].mean()
fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.9))
a.bar(g.index, g["修正综合分"], color=[RED, "#D98E3C", "#9AA5B1", TEAL, NAVY], width=.62)
for i, v in enumerate(g["修正综合分"]): a.text(i, v + .05, f"{v:.2f}", ha="center", fontsize=9)
a.set_title("修正综合分按当日涨跌幅五分位:U 型"); a.set_ylabel("平均修正综合分")
b.bar(g.index, g["D4空间性价比"], color=GOLD, width=.62, label="D4 空间性价比")
b2 = b.twinx(); b2.plot(g.index, g["Overheat"], color=NAVY, marker="o", label="Overheat"); b2.grid(False)
b.set_title("跌得越多 D4 越高、Overheat 越低"); b.set_ylabel("D4 均值"); b2.set_ylabel("Overheat 均值")
fig.tight_layout(); fig.savefig(out + "ev2_ushape.png", dpi=200, bbox_inches="tight"); plt.close(fig)
# 3 Overheat 影响
raw_top = set(m.nlargest(60, "原始综合分")["代码"]); adj_top = set(m.nlargest(60, "修正综合分")["代码"])
fig, a = plt.subplots(figsize=(6.4, 3.6))
a.bar(["原始分前60", "修正分前60", "两者重合", "被过热惩罚\n换出"], [60, 60, len(raw_top & adj_top), 60 - len(raw_top & adj_top)], color=[GOLD, TEAL, NAVY, RED], width=.6)
for i, v in enumerate([60, 60, len(raw_top & adj_top), 60 - len(raw_top & adj_top)]): a.text(i, v + 1, str(v), ha="center")
a.set_title("1.5×Overheat 只换出 %d/60 只:惩罚近乎装饰" % (60 - len(raw_top & adj_top))); a.set_ylim(0, 70)
fig.savefig(out + "ev3_overheat.png", dpi=200, bbox_inches="tight"); plt.close(fig)
# 4 市值倾斜
top = m.nlargest(60, "修正综合分")
fig, a = plt.subplots(figsize=(6.4, 3.6))
a.hist(m["市值(亿)"].clip(upper=300), bins=30, alpha=.55, color=GOLD, label="候选池387只", density=True)
a.hist(top["市值(亿)"].clip(upper=300), bins=30, alpha=.6, color=NAVY, label="观察名单60只", density=True)
a.axvline(m["市值(亿)"].median(), color=GOLD, ls="--"); a.axvline(top["市值(亿)"].median(), color=NAVY, ls="--")
a.set_title(f"无意中的大市值倾斜:中位数 {m['市值(亿)'].median():.0f}亿 → {top['市值(亿)'].median():.0f}亿"); a.legend(frameon=False); a.set_xlabel("市值(亿,截断300)")
fig.savefig(out + "ev4_size.png", dpi=200, bbox_inches="tight"); plt.close(fig)
print({"corr_D1_ratio": C.loc["D1主力质量", "资金/市值比%"], "D1_D2": C.loc["D1主力质量", "D2筹码博弈"], "overlap": len(raw_top & adj_top),
       "top_mc": top["市值(亿)"].median(), "pool_mc": m["市值(亿)"].median(), "ushape": g["修正综合分"].round(2).tolist(),
       "d2_size": C.loc["D2筹码博弈", "市值(亿)"], "d3_size": C.loc["D3量能活性", "市值(亿)"]})
