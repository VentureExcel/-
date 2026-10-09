"""把 out/ 下的 CSV 汇总成 Excel + 净值图。"""
from pathlib import Path

import pandas as pd


def write_summary(out: Path):
    out = Path(out)
    with pd.ExcelWriter(out / "回测结果汇总.xlsx") as xw:
        for f in sorted(out.glob("*.csv")):
            if f.name.startswith("_nav"):
                continue
            df = pd.read_csv(f)
            df.to_excel(xw, sheet_name=f.stem[:31], index=False)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.family"] = ["WenQuanYi Zen Hei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        for f in out.glob("_nav_*.csv"):
            d = pd.read_csv(f, index_col=0, parse_dates=True)
            ax = d.plot(figsize=(10, 4.5), lw=1.2)
            ax.set_title(f.stem); ax.grid(alpha=.3)
            ax.figure.savefig(out / f"{f.stem}.png", dpi=150, bbox_inches="tight"); plt.close(ax.figure)
    except Exception as e:  # pragma: no cover
        print("画图跳过:", e)
