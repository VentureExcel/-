"""合成市场(仅用于框架自检):植入"主力资金→未来收益"的弱信号,含涨跌停/ST/停牌/行业/市值。"""
import numpy as np
import pandas as pd

from .data import finalize


def make_market(n_stock=500, n_days=800, start="2023-01-03", seed=7, alpha_strength=0.0012, reversal_strength=0.0):
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range(start, periods=n_days)
    codes = [f"{600000 + i:06d}" if i < n_stock // 2 else f"{300000 + i:06d}" for i in range(n_stock)]
    ind = pd.Series(rng.integers(0, 28, n_stock), index=codes).map(lambda x: f"行业{x:02d}")
    mcap0 = np.exp(rng.normal(np.log(80), 0.8, n_stock)).clip(25, 900)          # 亿
    limit = np.where(np.array([c.startswith("300") for c in codes]), 0.20, 0.10)
    st = rng.random(n_stock) < 0.04
    limit = np.where(st, 0.05, limit)
    mkt = rng.normal(0.0002, 0.011, n_days)
    indr = rng.normal(0, 0.004, (n_days, 28))
    # 潜在资金 alpha:AR(1)
    a = np.zeros((n_days, n_stock)); e = rng.normal(0, 1, (n_days, n_stock))
    for t in range(1, n_days):
        a[t] = 0.55 * a[t - 1] + e[t]
    idio = rng.normal(0, 0.017, (n_days, n_stock))
    ret = np.zeros((n_days, n_stock))
    ind_idx = ind.str[2:].astype(int).values
    for t in range(1, n_days):
        ret[t] = (mkt[t] + indr[t, ind_idx] + 0.9 * rng.normal(0, 0.0005) + idio[t]
                  + alpha_strength * a[t - 1] - reversal_strength * np.clip(ret[t - 1], -.05, .05))
    prev = 20 * np.exp(rng.normal(0, .6, n_stock))
    O = np.zeros((n_days, n_stock)); H = O.copy(); L = O.copy(); C = O.copy(); susp = np.zeros((n_days, n_stock), bool)
    for t in range(n_days):
        susp[t] = rng.random(n_stock) < 0.004
        up = np.round(prev * (1 + limit), 2); dn = np.round(prev * (1 - limit), 2)
        gap = rng.normal(0, 0.004, n_stock)
        o = np.clip(prev * (1 + gap + 0.3 * ret[t]), dn, up)
        c = np.clip(prev * (1 + ret[t]), dn, up)
        o = np.round(o, 2); c = np.round(c, 2)
        hi = np.round(np.minimum(np.maximum(o, c) * (1 + np.abs(rng.normal(0, .006, n_stock))), up), 2)
        lo = np.round(np.maximum(np.minimum(o, c) * (1 - np.abs(rng.normal(0, .006, n_stock))), dn), 2)
        o = np.where(susp[t], prev, o); c = np.where(susp[t], prev, c); hi = np.where(susp[t], prev, hi); lo = np.where(susp[t], prev, lo)
        O[t], H[t], L[t], C[t] = o, hi, lo, c
        prev = c
    mcap = mcap0[None, :] * (C / C[0][None, :])
    turn = np.clip(np.exp(rng.normal(np.log(2.5), .5, (n_days, n_stock))) * (1 + 6 * np.abs(ret)), .3, 25)
    amount = mcap * 1e8 * turn / 100
    amount[susp] = 0
    volume = amount / C
    flow = (0.06 * a + rng.normal(0, 0.05, (n_days, n_stock))) * amount * 0.15      # 主力净流入(元)
    small = -0.5 * flow + rng.normal(0, 0.03, (n_days, n_stock)) * amount * 0.1
    idx = pd.DataFrame(index=pd.DatetimeIndex(cal))
    w = mcap / mcap.sum(1, keepdims=True)
    idx["沪深300"] = 3500 * np.cumprod(1 + (w * ret).sum(1)); idx["中证500"] = 5000 * np.cumprod(1 + ret.mean(1))
    df = lambda x: pd.DataFrame(x, index=cal, columns=codes)   # noqa: E731
    P = dict(open=df(O), high=df(H), low=df(L), close=df(C), volume=df(volume), amount=df(amount), turnover=df(turn),
             mktcap=df(mcap), main_net=df(flow), small_net=df(small), is_st=pd.DataFrame(np.tile(st, (n_days, 1)), index=cal, columns=codes),
             susp=df(susp), industry=ind, bench=idx)
    P["close"] = P["close"].where(~P["susp"]); P["open"] = P["open"].where(~P["susp"])
    return finalize(P)
