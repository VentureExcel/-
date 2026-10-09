from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

ND = NormalDist()


def perf(r: pd.Series, bench: pd.Series | None = None, rf=0.02) -> dict:
    r = r.dropna()
    if len(r) < 5:
        return {}
    nav = (1 + r).cumprod()
    yrs = len(r) / 252
    ann = nav.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    vol = r.std() * math.sqrt(252)
    dd = nav / nav.cummax() - 1
    out = dict(总收益=nav.iloc[-1] - 1, 年化收益=ann, 年化波动=vol, 夏普=(r.mean() * 252 - rf) / vol if vol > 0 else np.nan,
               最大回撤=dd.min(), 卡玛=ann / abs(dd.min()) if dd.min() < 0 else np.nan, 日胜率=(r > 0).mean(), 交易日=len(r))
    if bench is not None:
        b = bench.reindex(r.index).fillna(0)
        ex = r - b
        te = ex.std() * math.sqrt(252)
        out.update(基准年化=(1 + b).prod() ** (1 / yrs) - 1, 超额年化=ex.mean() * 252, 信息比率=ex.mean() * 252 / te if te > 0 else np.nan,
                   超额t值=ex.mean() / (ex.std() / math.sqrt(len(ex))) if ex.std() > 0 else np.nan,
                   超额最大回撤=((1 + ex).cumprod() / (1 + ex).cumprod().cummax() - 1).min())
    return out


def trade_stats(tr: pd.DataFrame) -> dict:
    if tr is None or tr.empty:
        return {}
    r = tr["ret"]
    w, l = r[r > 0], r[r <= 0]
    return dict(笔数=len(r), 胜率=(r > 0).mean(), 平均收益=r.mean(), 平均盈利=w.mean(), 平均亏损=l.mean(),
                盈亏比=(w.mean() / abs(l.mean())) if len(l) and l.mean() != 0 else np.nan, 收益中位数=r.median(),
                止损占比=(tr["reason"] == "stop").mean(), 平均持有天数=(pd.to_datetime(tr["exit"]) - pd.to_datetime(tr["entry"])).dt.days.mean())


def forward_returns(P: dict, h: int) -> pd.DataFrame:
    """信号日 t → t+1 开盘买入,持有至 t+h 收盘(h≥1)。剔除涨停开盘/停牌买不到的样本。"""
    from .factors import limit_prices
    up, _ = limit_prices(P)
    entry = P["a_open"].shift(-1)
    fwd = P["a_close"].shift(-h) / entry - 1
    buyable = ~(P["susp"].shift(-1).fillna(True).astype(bool)) & ~(P["open"].shift(-1) >= up.shift(-1) - 0.005)
    return fwd.where(buyable)


def ic_series(factor: pd.DataFrame, fwd: pd.DataFrame, min_n=30) -> pd.Series:
    fr, rr = factor.rank(axis=1), fwd.rank(axis=1)
    ok = factor.notna() & fwd.notna()
    fr, rr = fr.where(ok), rr.where(ok)
    n = ok.sum(axis=1)
    fc = fr.sub(fr.mean(axis=1), axis=0); rc = rr.sub(rr.mean(axis=1), axis=0)
    ic = (fc * rc).sum(axis=1) / np.sqrt((fc ** 2).sum(axis=1) * (rc ** 2).sum(axis=1))
    return ic.where(n >= min_n).dropna()


def nw_t(x: pd.Series, lag: int) -> float:
    """Newey-West t 值(处理重叠收益造成的自相关)。"""
    x = x.dropna(); n = len(x)
    if n < 10:
        return np.nan
    mu = x.mean(); e = (x - mu).values
    g0 = (e * e).sum() / n
    s = g0
    for k in range(1, min(lag, n - 1) + 1):
        s += 2 * (1 - k / (lag + 1)) * (e[k:] * e[:-k]).sum() / n
    return mu / math.sqrt(s / n) if s > 0 else np.nan


def quantile_returns(factor: pd.DataFrame, fwd: pd.DataFrame, q=5) -> pd.DataFrame:
    ok = factor.notna() & fwd.notna()
    pr = factor.where(ok).rank(axis=1, pct=True)
    b = np.ceil(pr * q).clip(1, q)
    df = pd.DataFrame({"b": b.stack(), "r": fwd.where(ok).stack()}).dropna()
    df["d"] = df.index.get_level_values(0)
    return df.groupby(["d", "b"])["r"].mean().unstack()


def factor_report(name: str, factor: pd.DataFrame, P: dict, horizons=(1, 3, 5, 10, 20), q=5) -> list[dict]:
    rows = []
    for h in horizons:
        fwd = forward_returns(P, h)
        ic = ic_series(factor, fwd)
        qr = quantile_returns(factor, fwd, q)
        spread = (qr[q] - qr[1]).dropna() if q in qr.columns else pd.Series(dtype=float)
        rows.append(dict(因子=name, 持有天数=h, IC均值=ic.mean(), IC标准差=ic.std(), ICIR=ic.mean() / ic.std() if ic.std() > 0 else np.nan,
                         IC_NW_t=nw_t(ic, h), IC正占比=(ic > 0).mean(), 多空日均收益=spread.mean(),
                         多空年化=spread.mean() * 252 / h if len(spread) else np.nan,
                         单调性=float(np.corrcoef(qr.mean().rank().values, np.arange(qr.shape[1]))[0, 1]) if len(qr) and qr.shape[1] > 2 else np.nan,
                         样本日数=len(ic)))
    return rows


def deflated_sharpe(r: pd.Series, n_trials: int, sr_var: float | None = None) -> float:
    """Bailey & López de Prado 通缩夏普概率:多次试验选最优后,真实夏普>0 的概率。"""
    r = r.dropna(); n = len(r)
    if n < 30 or n_trials < 1:
        return np.nan
    sr = r.mean() / r.std()                         # 日度
    skew, kurt = r.skew(), r.kurt() + 3
    v = sr_var if sr_var is not None else 1.0 / n
    gamma = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - gamma) * ND.inv_cdf(1 - 1 / max(n_trials, 2)) + gamma * ND.inv_cdf(1 - 1 / (max(n_trials, 2) * math.e)))
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    return ND.cdf((sr - sr0) * math.sqrt(n - 1) / denom)


def block_bootstrap_sharpe(r: pd.Series, B=1000, block=10, seed=0) -> tuple[float, float]:
    x = r.dropna().values; n = len(x)
    if n < 40:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    out = []
    nb = int(np.ceil(n / block))
    for _ in range(B):
        st = rng.integers(0, n - block + 1, nb)
        s = np.concatenate([x[a:a + block] for a in st])[:n]
        out.append(s.mean() / s.std() * math.sqrt(252) if s.std() > 0 else np.nan)
    return float(np.nanpercentile(out, 5)), float(np.nanpercentile(out, 95))


def monthly_table(r: pd.Series) -> pd.DataFrame:
    m = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    return m.unstack()
