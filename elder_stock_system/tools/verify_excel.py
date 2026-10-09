"""逐行对账:Excel(LibreOffice 重算) vs Python 引擎。"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from openpyxl import load_workbook
sys.path.insert(0, str(Path(__file__).parent))
from elder_lib import *

xl = Path(sys.argv[1]); csv = Path(sys.argv[2])
p = Params()
d = pd.read_csv(csv, parse_dates=["date"])
ind = add_support(daily_indicators(d, to_weekly(d), p), p)
wb = load_workbook(xl, data_only=True)
ws = wb["日线"]
hdr = {ws.cell(row=4, column=c).value: c for c in range(1, ws.max_column + 1)}
def colv(h):
    c = hdr[h]; return [ws.cell(row=5 + i, column=c).value for i in range(len(d))]
pairs = {  # excel header -> (python col, tolerance)
 "EMA快":"ema_f","EMA慢":"ema_s","MACD柱":"hist","动力系统(1绿/-1红/0蓝)":"impulse","FI-2日EMA":"fi2","FI-13日EMA":"fi13",
 "ATR":"atr","ADX":"adx","+DI":"pdi","-DI":"mdi","通道上轨":"ch_up","通道下轨":"ch_dn","慢%K":"stoch_k","慢%D":"stoch_d",
 "平均下跌穿透":"avg_pen","近期次低点":"nic_low","牛市背离":"bull_div","向下假突破":"false_break","强背离":"div_strong",
 "FI2非新低":"fi2_not_low","极端超卖反弹":"extreme","5日均量":"vol_ma5",
}
bad = 0
for h, pc in pairs.items():
    x = pd.to_numeric(pd.Series(colv(h)), errors="coerce").to_numpy(float)
    y = ind[pc].astype(float).to_numpy()
    diff = np.nanmax(np.abs(x - y)) if np.isfinite(x - y).any() else np.nan
    mism = int((np.abs(np.nan_to_num(x) - np.nan_to_num(y)) > 1e-6 * (1 + np.abs(np.nan_to_num(y)))).sum())
    print(f"{h:22s} maxdiff={diff:.2e}  mismatches={mism}")
    bad += mism
# 评分对账(预热后)
rows = [score_row(ind.iloc[i], p) for i in range(len(ind))]
sc = pd.DataFrame(rows)
for h, pc in {"趋势25":"s_trend","回调25":"s_pull","形态25":"s_sig","量能10":"s_vol","盈亏15":"s_rr","总分":"score","评级":"grade","买入挂单价":"entry","止损价":"stop","目标价(上轨)":"target"}.items():
    x = pd.Series(colv(h)); y = sc[pc]
    if h == "评级":
        m = int((x.iloc[40:].astype(str).values != y.iloc[40:].astype(str).values).sum())
    else:
        m = int((np.abs(pd.to_numeric(x, errors="coerce").iloc[40:].values - y.iloc[40:].astype(float).values) > 1e-6).sum())
    print(f"{h:22s} mismatches(rows>=40)={m}")
    bad += m
# 评分卡
sc_ws = wb["评分卡"]
print("评分卡: 总分", sc_ws["E21"].value, "评级", sc_ws["B30"].value, "买/止/目标", sc_ws["B33"].value, sc_ws["B34"].value, sc_ws["B35"].value if False else sc_ws["B35"].value, "股数", sc_ws["B40"].value)
print("python last:", {k: rows[-1][k] for k in ("score","grade","entry","stop","target")})
# 错误扫描
errs = 0
for w in wb.worksheets:
    for row in w.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.startswith(("#", "Err:")):
                errs += 1
                if errs < 10: print("ERR", w.title, c.coordinate, c.value)
print("error cells:", errs, "total mismatches:", bad)
