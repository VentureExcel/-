"""撮合与组合:T 日收盘出信号 → T+1 开盘成交 → 持有 H 个隔夜 → 次日开盘卖出。

A股约束:T+1(买入当日不可卖)、涨停开盘买不到、停牌无法成交、跌停锁死无法卖出(顺延)、
最小100股(以权重近似,不取整)、佣金/印花税/过户费/滑点/冲击成本。
组合为"逐日分仓":每个信号日的组合占 1/H 资金 × 当日风险敞口,持有期内不再平衡(固定名义)。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .factors import limit_prices


@dataclass
class BtParams:
    hold: int = 5                 # 持有隔夜数(最早 1 = T+1 开盘卖出)
    top_n: int = 10
    ind_cap: int = 2              # 同行业最多只数
    max_w: float = 0.15           # 单票最大权重(占当日分仓)
    stop_loss: float | None = 0.07   # 固定止损(相对买入价),None=不止损
    intraday_stop: bool = True    # 用最低价触发(次日起),跳空按开盘价成交
    take_profit: float | None = None
    capital: float = 5e6          # 资金规模(元),用于容量/冲击
    part_cap: float = 0.05        # 单票占 20 日均成交额上限
    commission: float = 2.5e-4    # 佣金(双边)
    stamp: float = 5e-4           # 印花税(卖出,0.05%)
    transfer: float = 1e-5        # 过户费(双边)
    slip_bps: float = 10.0        # 基础滑点(单边,bp)
    impact_k: float = 10.0        # 冲击:k × 参与率(bp)
    rf: float = 0.02              # 现金收益(年化)
    exposure_scale: float = 1.0
    min_score_pct: float | None = None


def _select(sc_row: pd.Series, el_row: pd.Series, ind: pd.Series | None, p: BtParams) -> list[str]:
    s = sc_row[el_row].dropna().sort_values(ascending=False)
    out, cnt = [], {}
    for code in s.index:
        if ind is not None and p.ind_cap:
            g = ind.get(code, "?")
            if cnt.get(g, 0) >= p.ind_cap:
                continue
            cnt[g] = cnt.get(g, 0) + 1
        out.append(code)
        if len(out) >= p.top_n:
            break
    return out


def run_backtest(P: dict, score: pd.DataFrame, elig: pd.DataFrame, expo: pd.Series, p: BtParams,
                 start=None, end=None) -> dict:
    cal = P["close"].index
    ao, ac, al = P["a_open"], P["a_close"], P["a_low"]
    ro, rh, rl, rc = P["open"], P["high"], P["low"], P["close"]
    up, dn = limit_prices(P)
    susp = P["susp"]
    amt20 = P["amount"].rolling(20).mean()
    ind = P.get("industry")
    pos = {d: i for i, d in enumerate(cal)}
    ds = cal if start is None else cal[cal >= pd.Timestamp(start)]
    if end is not None:
        ds = ds[ds <= pd.Timestamp(end)]
    trades, daily = [], pd.Series(0.0, index=cal)
    daily_expo = pd.Series(0.0, index=cal)
    slip = p.slip_bps / 1e4
    for s_day in ds:
        i = pos[s_day]
        if i + 1 >= len(cal):
            continue
        e_day = cal[i + 1]
        ex = float(expo.get(s_day, 0.0)) * p.exposure_scale
        if ex <= 0:
            continue
        picks = _select(score.loc[s_day], elig.loc[s_day], ind, p)
        if not picks:
            continue
        w = np.minimum(1.0 / len(picks), p.max_w)
        for code in picks:
            o_raw = ro.at[e_day, code]
            if not np.isfinite(o_raw) or susp.at[e_day, code] or o_raw >= up.at[e_day, code] - 0.005:
                continue                                   # 停牌/涨停开盘买不到
            f = ex * w / p.hold                            # 占总资金比例
            part = f * p.capital / max(amt20.at[s_day, code], 1.0)
            if part > p.part_cap:                          # 容量约束:按上限缩量
                f *= p.part_cap / part; part = p.part_cap
            slip_in = slip + p.impact_k * part / 1e4
            entry = ao.at[e_day, code] * (1 + slip_in)
            ei = i + 1
            stop_px = entry * (1 - p.stop_loss) if p.stop_loss else None
            tp_px = entry * (1 + p.take_profit) if p.take_profit else None
            path = []          # [(date, 当日回报率)]
            cost_in = p.commission + p.transfer
            prev_val = entry
            exit_px, exit_i, reason = None, None, "time"
            j = ei
            while j < len(cal):
                d = cal[j]
                hi_raw_lock = False
                if susp.at[d, code] or not np.isfinite(ac.at[d, code]):
                    path.append((d, 0.0 if j > ei else -cost_in)); j += 1
                    if j - ei > p.hold + 20: break
                    continue
                if j > ei:   # T+1:入场次日起可卖
                    locked = (ro.at[d, code] <= dn.at[d, code] + 0.005) and (rh.at[d, code] <= dn.at[d, code] + 0.005)
                    trig = None
                    if p.stop_loss and not locked:
                        if ao.at[d, code] <= stop_px:
                            trig = ("stop", ao.at[d, code] * (1 - slip))
                        elif p.intraday_stop and al.at[d, code] <= stop_px:
                            trig = ("stop", stop_px * (1 - slip))
                    if trig is None and p.take_profit and not locked and P["a_high"].at[d, code] >= tp_px:
                        trig = ("tp", max(tp_px, ao.at[d, code]) * (1 - slip))
                    if trig is None and (j - ei) >= p.hold and not locked:
                        trig = ("time", ao.at[d, code] * (1 - slip - p.impact_k * part / 1e4))
                    if trig:
                        reason, px = trig
                        exit_px, exit_i = px, j
                        ret = px / prev_val - 1 - (p.commission + p.stamp + p.transfer)
                        path.append((d, ret)); break
                if j == ei:
                    path.append((d, ac.at[d, code] / entry - 1 - cost_in)); prev_val = ac.at[d, code]
                else:
                    path.append((d, ac.at[d, code] / prev_val - 1)); prev_val = ac.at[d, code]
                j += 1
            if exit_px is None:   # 数据末尾仍持有:按最后收盘估值
                exit_px, exit_i, reason = prev_val, min(j, len(cal) - 1), "open_end"
            for d, r in path:
                daily.at[d] += f * r
                daily_expo.at[d] += f
            trades.append(dict(signal=s_day, entry=e_day, exit=cal[min(exit_i, len(cal) - 1)], code=code, w=f,
                               entry_px=entry, exit_px=exit_px, ret=exit_px / entry - 1 - (2 * p.commission + p.stamp + 2 * p.transfer),
                               reason=reason, score=float(score.at[s_day, code])))
    cash = (1 - daily_expo.clip(upper=1)) * p.rf / 252
    r = (daily + cash).loc[ds[0]:ds[-1]] if len(ds) else daily
    return dict(ret=r, trades=pd.DataFrame(trades), exposure=daily_expo.loc[r.index])
