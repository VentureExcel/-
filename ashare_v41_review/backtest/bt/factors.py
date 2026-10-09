"""因子库:V4.1 复刻(按报告文字口径)与 V4.2 候选因子。全部只用 t 日及以前数据。

注意:V4.1 子因子的精确公式以生产脚本为准;此处按报告描述复刻,
本地运行前请用 `bt/strategies.py::V41_HOOK` 挂接生产评分函数以消除复刻偏差。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def btw(df, lo, hi):
    return (df >= lo) & (df <= hi)


def rank01(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True)


def zclip(df: pd.DataFrame, k=3.0) -> pd.DataFrame:
    z = df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)
    return z.clip(-k, k)


def mm01(df: pd.DataFrame) -> pd.DataFrame:
    lo, hi = df.min(axis=1), df.max(axis=1)
    return df.sub(lo, axis=0).div((hi - lo).replace(0, np.nan), axis=0)


def limit_ratio(P) -> pd.DataFrame:
    """涨跌停幅度:ST 5%、创业板/科创板 20%、北交所 30%、其余 10%(可在配置中覆盖)。"""
    codes = P["close"].columns
    base = pd.Series(0.10, index=codes)
    base[[c.startswith(("300", "301", "688", "689")) for c in codes]] = 0.20
    base[[c.startswith(("8", "4", "92")) for c in codes]] = 0.30      # 北交所 30%
    r = pd.DataFrame(np.tile(base.values, (len(P["close"]), 1)), index=P["close"].index, columns=codes)
    return r.where(~P["is_st"], 0.05)


def limit_prices(P):
    prev = P["close"].shift(1)
    r = limit_ratio(P)
    return (prev * (1 + r)).round(2), (prev * (1 - r)).round(2)


def build_features(P: dict) -> dict:
    """基础特征面板。"""
    F = {}
    c, a, amt, m = P["close"], P["amount"], P["amount"], P["main_net"]
    mc = P.get("mktcap")
    F["chg"] = c.pct_change() * 100
    F["ret5"] = c / c.shift(5) - 1
    F["ret20"] = c / c.shift(20) - 1
    F["ma20"] = c.rolling(20).mean(); F["ma60"] = c.rolling(60).mean()
    F["bias20"] = (c / F["ma20"] - 1) * 100
    F["high60"] = P["high"].rolling(60).max(); F["high20"] = P["high"].rolling(20).max()
    F["amt20"] = amt.rolling(20).mean()
    F["main5"] = m.rolling(5).sum()
    F["main20"] = m.rolling(20).sum()
    F["flow_ratio"] = m / (mc * 1e8) * 100 if mc is not None else m / amt
    F["flow_amt"] = m / amt.replace(0, np.nan)                                   # 净流入占成交额
    F["flow5_amt"] = F["main5"] / amt.rolling(5).sum().replace(0, np.nan)
    F["flow20_amt"] = F["main20"] / amt.rolling(20).sum().replace(0, np.nan)
    mu, sd = F["flow_amt"].rolling(60).mean(), F["flow_amt"].rolling(60).std()
    F["flow_z60"] = (F["flow_amt"] - mu) / sd.replace(0, np.nan)                 # 相对自身历史的异常程度
    F["flow_pos5"] = (m > 0).rolling(5).sum()
    F["flow_accel"] = F["flow_amt"] - F["flow_amt"].shift(1).rolling(4).mean()
    if "small_net" in P:
        F["retail_div"] = (m - P["small_net"]) / amt.replace(0, np.nan)
        F["flow_conc"] = m.abs() / (m.abs() + P["small_net"].abs()).replace(0, np.nan) * np.sign(m)
    t = P["turnover"]
    F["turn_rel"] = t / t.rolling(60).mean()
    F["amt_rank"] = rank01(F["amt20"])
    tr = pd.concat([P["high"] - P["low"], (P["high"] - c.shift(1)).abs(), (P["low"] - c.shift(1)).abs()]).groupby(level=0).max()
    F["atr14"] = tr.rolling(14).mean()
    F["atr_pct"] = F["atr14"] / c
    return F


def overheat(P, F):
    """Overheat = 0.4×涨幅占比 + 0.3×5日涨幅 + 0.3×BIAS20,三分量各自截面 min-max 归一(报告口径)。"""
    lim = limit_ratio(P) * 100
    share = (F["chg"] / lim).clip(lower=0)
    return 0.4 * mm01(share) + 0.3 * mm01(F["ret5"]) + 0.3 * mm01(F["bias20"])


def space_to_pressure(P, F):
    """距真实压力位空间%:近20/60日高点、MA60 中高于现价且最近者;无则 0(报告:压力位缺省 space=0)。"""
    c = P["close"]
    cands = [F["high60"], F["high20"], F["ma60"]]
    best = None
    for x in cands:
        x = x.where(x > c)
        best = x if best is None else np.fmin(best, x)
    return ((best / c - 1) * 100).fillna(0)
