"""Elder《以交易为生》指标与选股评分库(第一步交付,第二、三步复用)。

所有指标的定义与 Excel 模板(01_埃尔德选股评分模型.xlsx)中的公式一一对应,
用于:① 校验 Excel 公式;② 生成 Word 图表;③ 后续每日选股与回测引擎。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass
class Params:
    ema_fast: int = 13          # 快速 EMA(价值区间上沿)
    ema_slow: int = 26          # 慢速 EMA(趋势/价值区间下沿),与快线约 2:1
    macd_fast: int = 12
    macd_slow: int = 26
    macd_sig: int = 9
    atr_n: int = 13             # 平均真实波幅天数
    fi_short: int = 2           # 强力指数短周期
    fi_long: int = 13           # 强力指数长周期
    stoch_n: int = 5
    stoch_smooth: int = 3
    adx_n: int = 13
    channel_pct: float = 0.06   # 通道系数(占 EMA26 比例),需按 95% 覆盖率校准
    pen_lookback: int = 30      # 平均下跌穿透回溯期
    stop_lookback: int = 10     # 尼克止损回溯期(取次低点)
    stop_min_atr: float = 1.0   # 止损距入场至少 N 倍 ATR
    divg_min_gap: int = 10      # 背离两个谷底最小间隔(书:20-40 最佳)
    divg_max_gap: int = 60
    fi_newlow_lb: int = 20      # "几周内新低"回溯期
    rr_min: float = 2.0         # 最小盈亏比
    grade_a: float = 70.0
    grade_b: float = 55.0
    risk_trade: float = 0.01    # 单笔风险(上限 2%)
    risk_trade_cap: float = 0.02
    risk_month_cap: float = 0.06
    pos_cap: float = 0.20       # 单只股票最大仓位占比(设计假设)
    lot: int = 100


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=2.0 / (n + 1), adjust=False).mean()


def week_key(dates: pd.Series) -> pd.Series:
    """周一为周起始键,与 Excel: =日期-WEEKDAY(日期,3) 一致。"""
    d = pd.to_datetime(dates)
    return (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize()


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """日线 → 周线(周一为键)。df 需含 date/open/high/low/close/volume。"""
    k = week_key(df["date"])
    g = df.assign(wk=k).groupby("wk")
    w = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
        "close": g["close"].last(), "volume": g["volume"].sum(),
    })
    return w.reset_index().rename(columns={"wk": "date"})


def trend_block(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """EMA、MACD、动力系统(周线与日线共用)。"""
    o = pd.DataFrame(index=df.index)
    c = df["close"]
    o["ema_f"] = ema(c, p.ema_fast)
    o["ema_s"] = ema(c, p.ema_slow)
    o["macd"] = ema(c, p.macd_fast) - ema(c, p.macd_slow)
    o["macd_sig"] = ema(o["macd"], p.macd_sig)
    o["hist"] = o["macd"] - o["macd_sig"]
    o["ema_f_up"] = o["ema_f"] > o["ema_f"].shift(1)
    o["ema_f_dn"] = o["ema_f"] < o["ema_f"].shift(1)
    o["ema_s_up"] = o["ema_s"] > o["ema_s"].shift(1)
    o["hist_up"] = o["hist"] > o["hist"].shift(1)
    o["hist_dn"] = o["hist"] < o["hist"].shift(1)
    # 动力系统:+1 绿(禁止卖空) / -1 红(禁止买入) / 0 蓝
    o["impulse"] = np.where(o["ema_f_up"] & o["hist_up"], 1,
                            np.where(o["ema_f_dn"] & o["hist_dn"], -1, 0))
    o.loc[o.index[0], "impulse"] = 0
    return o


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]
    return tr


def adx_block(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    h, l = df["high"], df["low"]
    up = h - h.shift(1)
    dn = l.shift(1) - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pdm = pd.Series(pdm, index=df.index)
    mdm = pd.Series(mdm, index=df.index)
    pdm.iloc[0] = mdm.iloc[0] = 0.0
    tr = true_range(df)
    str_ = ema(tr, p.adx_n)
    pdi = 100 * ema(pdm, p.adx_n) / str_
    mdi = 100 * ema(mdm, p.adx_n) / str_
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adx = ema(dx.fillna(0), p.adx_n)
    return pd.DataFrame({"tr": tr, "pdi": pdi, "mdi": mdi, "dx": dx, "adx": adx})


def divergence_block(df: pd.DataFrame, hist: pd.Series, p: Params) -> pd.DataFrame:
    """MACD 柱状线牛市背离 + 向下假突破(书 23 节/55 节 A 级交易)。

    以"柱线<0 的连续区段(run)"为单位。当前区段的谷底(柱值 hist、价格最低 low)与
    上一区段谷底比较:价格更低 且 柱谷更浅 → 牛市背离;当 hist 由谷底回升(hist_t>hist_{t-1})
    时触发。收盘重新站上上一低点 → 视为向下假突破。
    """
    n = len(df)
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    h = hist.to_numpy()
    run_h = np.full(n, np.nan); run_l = np.full(n, np.nan); run_b = np.full(n, np.nan)
    p_h = np.full(n, np.nan); p_l = np.full(n, np.nan); p_b = np.full(n, np.nan)
    for i in range(n):
        neg = h[i] < 0
        pneg = i > 0 and h[i - 1] < 0
        if i == 0:
            if neg:
                run_h[i], run_l[i], run_b[i] = h[i], low[i], i
            continue
        if neg and not pneg:               # 新区段开始:上一区段成为"前一谷底"
            p_h[i], p_l[i], p_b[i] = run_h[i - 1], run_l[i - 1], run_b[i - 1]
            run_h[i], run_l[i], run_b[i] = h[i], low[i], i
        else:
            p_h[i], p_l[i], p_b[i] = p_h[i - 1], p_l[i - 1], p_b[i - 1]
            if neg:
                run_h[i] = min(run_h[i - 1], h[i])
                run_l[i] = min(run_l[i - 1], low[i])
                run_b[i] = i if h[i] < run_h[i - 1] else run_b[i - 1]
            else:
                run_h[i], run_l[i], run_b[i] = run_h[i - 1], run_l[i - 1], run_b[i - 1]
    o = pd.DataFrame({"run_h": run_h, "run_l": run_l, "run_b": run_b,
                      "p_h": p_h, "p_l": p_l, "p_b": p_b}, index=df.index)
    neg = hist < 0
    turn_up = hist > hist.shift(1)
    gap = o["run_b"] - o["p_b"]
    o["gap"] = gap
    o["bull_div"] = (neg & turn_up & (o["run_h"] > o["p_h"]) & (o["run_l"] < o["p_l"])
                     & (gap >= p.divg_min_gap) & (gap <= p.divg_max_gap))
    o["false_break"] = o["bull_div"] & (pd.Series(close, index=df.index) > o["p_l"])
    o["div_strong"] = o["bull_div"] & (o["run_h"] >= o["p_h"] * 0.5)  # 第二谷≤第一谷一半深度
    return o


def daily_indicators(daily: pd.DataFrame, weekly: pd.DataFrame | None = None,
                     p: Params | None = None) -> pd.DataFrame:
    """日线全部指标与信号(含上一完整周的周线状态,避免前视偏差)。"""
    p = p or Params()
    d = daily.reset_index(drop=True).copy()
    t = trend_block(d, p)
    c, v = d["close"], d["volume"]
    out = pd.concat([d, t], axis=1)
    # 强力指数
    fi1 = v * (c - c.shift(1)); fi1.iloc[0] = 0.0
    out["fi1"] = fi1
    out["fi2"] = ema(fi1, p.fi_short)
    out["fi13"] = ema(fi1, p.fi_long)
    # 波动率与通道
    a = adx_block(d, p)
    out = pd.concat([out, a], axis=1)
    out["atr"] = a["tr"].rolling(p.atr_n, min_periods=1).mean()
    out["ch_up"] = out["ema_s"] * (1 + p.channel_pct)
    out["ch_dn"] = out["ema_s"] * (1 - p.channel_pct)
    for k in (1, 2, 3):
        out[f"atr_up{k}"] = out["ema_s"] + k * out["atr"]
        out[f"atr_dn{k}"] = out["ema_s"] - k * out["atr"]
    # 随机指标(慢速)
    hh = d["high"].rolling(p.stoch_n, min_periods=1).max()
    ll = d["low"].rolling(p.stoch_n, min_periods=1).min()
    raw = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    raw = raw.fillna(50)
    out["stoch_k"] = raw.rolling(p.stoch_smooth, min_periods=1).mean()
    out["stoch_d"] = out["stoch_k"].rolling(p.stoch_smooth, min_periods=1).mean()
    # 平均下跌穿透(价格低于 EMA13 的平均深度)
    pen = (out["ema_f"] - d["low"]).clip(lower=0)
    cnt = (pen > 0).astype(float).rolling(p.pen_lookback, min_periods=1).sum()
    out["avg_pen"] = np.where(cnt > 0, pen.rolling(p.pen_lookback, min_periods=1).sum() / cnt.replace(0, np.nan), 0.5 * out["atr"])
    out["avg_pen"] = out["avg_pen"].astype(float)
    # 背离
    dv = divergence_block(d, out["hist"], p)
    out = pd.concat([out, dv], axis=1)
    # FI2 是否为 N 日新低
    out["fi2_not_low"] = out["fi2"] > out["fi2"].shift(1).rolling(p.fi_newlow_lb - 1, min_periods=1).min()
    out["fi2_neg_mean"] = out["fi2"].where(out["fi2"] < 0).rolling(100, min_periods=5).mean()
    out["extreme"] = (out["fi2"] < 5 * out["fi2_neg_mean"]) & (out["fi2"] > out["fi2"].shift(1)) \
        & (c < out["ch_dn"])
    out["vol_ma5"] = v.rolling(5, min_periods=1).mean()
    out["hi60"] = d["high"].rolling(60, min_periods=1).max()
    # 周线状态(上一完整周)
    if weekly is not None:
        w = trend_block(weekly, p)
        wk = weekly["date"].reset_index(drop=True)
        w = w.reset_index(drop=True)
        w["wk_ema_s_up"] = w["ema_s_up"]
        w["wk_hist_up"] = w["hist_up"]
        w["wk_impulse"] = w["impulse"]
        w["wk_hist"] = w["hist"]
        pos = pd.Series(np.arange(len(wk)), index=pd.DatetimeIndex(wk))
        cur = pos.reindex(pd.DatetimeIndex(week_key(d["date"]))).to_numpy()
        prev = cur - 1                                     # 上一"有交易的完整周"
        ok = prev >= 0
        for col, default in (("wk_ema_s_up", False), ("wk_hist_up", False), ("wk_impulse", 0), ("wk_hist", np.nan)):
            vals = np.where(ok, w[col].to_numpy()[np.clip(prev, 0, None).astype(int)], default)
            out[col] = vals if col in ("wk_hist", "wk_impulse") else vals.astype(bool)
    return out


def order_plan(r: pd.Series, p: Params) -> dict:
    """一根 K 线的次日挂单计划(三重滤网第三重 + 尼克止损 + 通道目标 + 2% 仓位)。"""
    ema_next = 2 * r["ema_f"] - r["ema_f_prev"]           # 明日 EMA 估计
    entry = round(max(ema_next - r["avg_pen"], 0.01), 2)
    nic = r["nic_low"]                                    # 近 N 日次低点
    stop = min(nic - 0.01, entry - p.stop_min_atr * r["atr"])
    stop = np.floor(round(stop * 100, 6)) / 100           # 与 Excel ROUNDDOWN(x,2) 一致(规避浮点误差)
    if int(round(stop * 100)) % 50 == 0:                  # 避开整数/半整数
        stop = round(stop - 0.01, 2)
    target = round(r["ch_up"], 2)
    risk = entry - stop
    rr = (target - entry) / risk if risk > 0 else np.nan
    return dict(entry=entry, stop=round(stop, 2), target=target, risk=round(risk, 2), rr=rr)


def score_row(r: pd.Series, p: Params) -> dict:
    """评分(0-100) + 硬性否决。r 为 daily_indicators 的一行,另需 nic_low/ema_f_prev。"""
    s_trend = 0.0
    s_trend += 10 if r.get("wk_ema_s_up") else 0
    imp = r.get("wk_impulse", 0)
    s_trend += 5 if imp == 1 else (3 if imp == 0 else 0)
    s_trend += 5 if r.get("wk_hist_up") else 0
    s_trend += 5 if (r["pdi"] > r["mdi"] and r["adx"] > r.get("adx_prev", r["adx"])) else 0

    in_zone = r["ema_s"] <= r["close"] <= r["ema_f"]
    below_s = r["ch_dn"] <= r["close"] < r["ema_s"]
    s_pull = (10 if in_zone else (6 if below_s else 0))
    s_pull += 8 if (r["fi2"] < 0 and r["fi2_not_low"]) else 0
    s_pull += 7 if r["stoch_k"] < 30 else (3 if r["stoch_k"] < 50 else 0)

    setup_a = bool(r["wk_ema_s_up"] and r["impulse"] != -1 and r["fi2"] < 0 and r["fi2_not_low"]
                   and r["close"] <= r["ema_f"] and r["close"] >= r["ch_dn"])
    setup_b = bool(r["bull_div"])
    setup_c = bool(r["extreme"])
    if setup_a and setup_b:
        s_sig = 25
    elif setup_b:
        s_sig = 22
    elif setup_a:
        s_sig = 15
    elif setup_c:
        s_sig = 12
    else:
        s_sig = 0
    s_vol = (6 if r["fi13"] > 0 else 0) + (4 if r["volume"] < r["vol_ma5"] else 0)

    plan = order_plan(r, p)
    rr = plan["rr"]
    s_rr = 15 if rr >= 3 else (10 if rr >= p.rr_min else (4 if rr >= 1.5 else 0))

    total = s_trend + s_pull + s_sig + s_vol + s_rr
    veto = []
    if not r.get("wk_ema_s_up") and not (setup_b or setup_c):   # 顺势回调(A)要求周趋势向上;背离/极值(B/C)只要求周线不红
        veto.append("周线EMA26未向上")
    if r.get("wk_impulse", 0) == -1:
        veto.append("周线动力系统红色")
    if r["impulse"] == -1:
        veto.append("日线动力系统红色")
    if not (setup_a or setup_b or setup_c):
        veto.append("无有效买入形态")
    if not (rr >= p.rr_min):
        veto.append("盈亏比<2")
    grade = "C"
    if not veto:
        grade = "A" if total >= p.grade_a else ("B" if total >= p.grade_b else "C")
    elif total >= p.grade_b and set(veto) == {"盈亏比<2"}:
        grade = "B"
    return dict(score=total, s_trend=s_trend, s_pull=s_pull, s_sig=s_sig, s_vol=s_vol, s_rr=s_rr,
                setup_a=setup_a, setup_b=setup_b, setup_c=setup_c, grade=grade,
                veto=";".join(veto), **plan)


def add_support(ind: pd.DataFrame, p: Params) -> pd.DataFrame:
    """补充 order_plan / score_row 所需的辅助列。"""
    o = ind.copy()
    o["ema_f_prev"] = o["ema_f"].shift(1).fillna(o["ema_f"])
    o["adx_prev"] = o["adx"].shift(1).fillna(o["adx"])
    n = p.stop_lookback
    # 近 n 日(含当日)次低点:第二低的最低价
    o["nic_low"] = o["low"].rolling(n, min_periods=2).apply(lambda x: np.sort(x)[1], raw=True)
    o["nic_low"] = o["nic_low"].fillna(o["low"])
    return o


def position_size(equity: float, entry: float, stop: float, p: Params, risk_pct: float | None = None,
                  avail_risk: float | None = None) -> int:
    """风险控制铁三角:股数 = 风险额度 / 每股风险,按手取整;受 2%/6% 约束。"""
    rp = min(risk_pct if risk_pct is not None else p.risk_trade, p.risk_trade_cap)
    budget = equity * rp
    if avail_risk is not None:
        budget = min(budget, max(avail_risk, 0))
    per = entry - stop
    if per <= 0:
        return 0
    cap_sh = equity * p.pos_cap / entry
    return int(min(budget / per, cap_sh) // p.lot * p.lot)


def trade_rating(buy: float, sell: float, day_buy: tuple, day_sell: tuple, ch_hi: float, ch_lo: float) -> dict:
    """买入评级、卖出评级、交易评级(书 55 节)。day_* = (low, high)。交易评级 >=30% 通道高度 = A 级。"""
    bl, bh = day_buy
    sl, sh = day_sell
    br = (bh - buy) / (bh - bl) if bh > bl else np.nan
    sr = (sell - sl) / (sh - sl) if sh > sl else np.nan
    tr = (sell - buy) / (ch_hi - ch_lo) if ch_hi > ch_lo else np.nan
    grade = "A" if tr >= 0.30 else ("B" if tr >= 0.15 else "C")
    return dict(buy_rating=br, sell_rating=sr, trade_rating=tr, grade=grade)
