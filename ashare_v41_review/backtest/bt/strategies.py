"""策略定义:V4.1 复刻 与 V4.2 优化版。均输出 (score, eligible, exposure),由 engine 统一撮合。

score      DataFrame 日期×代码,越高越好(NaN=不可选)
eligible   DataFrame bool,通过全部硬筛选
exposure   Series 日期→0~1,当日风险敞口(大盘闸门)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .factors import btw, build_features, limit_prices, mm01, overheat, rank01, space_to_pressure, zclip

# 若要用生产评分,把函数赋给它:fn(P, F) -> (score, eligible);签名保持一致即可
V41_HOOK = None


def dim_score(x: pd.DataFrame) -> pd.DataFrame:
    """维度分 = 0.5×批内 Z 排名(0-10) + 0.5×批内分位(0-10)(报告:历史分位暂以批内替代)。"""
    z = (zclip(x) + 3) / 6 * 10
    return 0.5 * z + 0.5 * rank01(x) * 10


def v41_universe(P, F, cfg):
    """初筛 + 质量门 + C4(报告口径)。"""
    u = cfg.get("v41", {})
    mc = P["mktcap"]
    elig = (P["main_net"] > 0) & btw(mc, u.get("mc_min", 30), u.get("mc_max", 500)) \
        & btw(P["turnover"], u.get("turn_min", 1.0), u.get("turn_max", 5.0)) & (~P["is_st"]) & (~P["susp"])
    elig &= P["main_net"].notna() & F["main5"].notna()
    if u.get("filter_retail_same_sign", True):          # [4] 主力与散户同为净流入 → 剔除(报告:816/1432)
        elig &= ~((P["main_net"] > 0) & (P["small_net"] > 0))
    if u.get("c4", True):
        elig &= F["main5"] > 0
    if u.get("min_list_days", 60):
        elig &= P["list_days"] >= u.get("min_list_days", 60)
    return elig


def v41_score(P, F, cfg):
    u = cfg.get("v41", {})
    w = u.get("weights", dict(D1=.35, D2=.25, D3=.20, D4=.20))
    # D1 主力质量:资金/市值比60% + 5日方向20% + 加速度20%
    d1 = .6 * dim_score(F["flow_ratio"]) + .2 * dim_score(F["main5"] / (P["mktcap"] * 1e8)) + .2 * dim_score(F["flow_accel"])
    # D2 筹码博弈:主力vs散户背离50% + 资金集中度50%
    d2 = .5 * dim_score(F["retail_div"]) + .5 * dim_score(F["flow_conc"])
    # D3 量能活性:换手相对强度50% + 成交额排名50%
    d3 = .5 * dim_score(F["turn_rel"]) + .5 * dim_score(F["amt_rank"])
    # D4 空间性价比:距压力位空间 + 跌透反弹加分
    space = space_to_pressure(P, F)
    bonus = ((F["bias20"] < -10) & (P["main_net"] > 0)).astype(float) * 1.5
    d4 = (dim_score(space) + bonus).clip(upper=10)
    raw = w["D1"] * d1 + w["D2"] * d2 + w["D3"] * d3 + w["D4"] * d4
    oh = overheat(P, F)
    k = u.get("overheat_k", 1.5)
    adj = raw - k * oh if k else raw
    return adj, dict(D1=d1, D2=d2, D3=d3, D4=d4, raw=raw, overheat=oh)


def v41(P, F, cfg):
    if V41_HOOK is not None:
        score, elig = V41_HOOK(P, F)
    else:
        elig = v41_universe(P, F, cfg)
        score, _ = v41_score(P, F, cfg)
    elig = elig & score.notna()
    # 相对门槛:当日批内前 top_pct(报告:前15%)
    pct = cfg.get("v41", {}).get("top_pct", 0.15)
    sc = score.where(elig)
    thr = sc.quantile(1 - pct, axis=1)
    elig = elig & sc.ge(thr, axis=0)
    # 涨停硬约束:当日涨幅达板块涨停幅度 → 不可买(次日也可能高开涨停)
    up, _ = limit_prices(P)
    elig &= ~(P["close"] >= up - 0.005)
    return sc, elig, pd.Series(1.0, index=P["close"].index)


# ───────────────────────── V4.2 ─────────────────────────
DEFAULT_V42 = dict(
    # 子策略(sleeve):mom=资金动量延续;rev=资金逆势吸筹反转。分别验证,不混在同一分数里
    sleeve="mom",
    factors={  # 因子: 权重(方向已内置)。均为截面分位后再加权
        "flow5_amt": 0.30, "flow_z60": 0.20, "flow_pos5": 0.10, "retail_div": 0.10,
        "ret20": 0.10, "turn_rel": -0.05, "atr_pct": -0.15,
    },
    neutralize=True,
    universe=dict(mc_min=30, mc_max=500, amt20_min=1e8, min_list_days=120, exclude_st=True, max_ret5=0.25, min_ret5=-0.12),
    gate=dict(enabled=True),
    top_n=15, ind_cap=2,
)


def neutralize(x: pd.DataFrame, ind: pd.Series, logcap: pd.DataFrame) -> pd.DataFrame:
    """逐日对 [行业哑变量 + ln(市值)] 回归取残差。"""
    codes = x.columns
    D = pd.get_dummies(ind.reindex(codes).fillna("未知")).values.astype(float)
    out = pd.DataFrame(np.nan, index=x.index, columns=codes)
    for t in x.index:
        y = x.loc[t].values; lc = logcap.loc[t].values
        ok = np.isfinite(y) & np.isfinite(lc)
        if ok.sum() < 50:
            continue
        X = np.column_stack([D[ok], lc[ok]])
        keep = X.sum(0) != 0
        beta, *_ = np.linalg.lstsq(X[:, keep], y[ok], rcond=None)
        r = np.full(len(y), np.nan); r[ok] = y[ok] - X[:, keep] @ beta
        out.loc[t] = r
    return out


def market_gate(P, F, g: dict) -> pd.Series:
    """大盘环境闸门(0~1):广度、成交额分位、指数趋势、跌停家数、波动率。阈值为设计假设,由回测校准。"""
    c = P["close"]
    breadth = (c > F["ma20"]).where(c.notna()).mean(axis=1)                       # 站上20日线占比
    amt = P["amount"].sum(axis=1)
    amt_pct = amt.rolling(250, min_periods=60).rank(pct=True)
    ret = c.pct_change()
    ld = (ret < -0.095).sum(axis=1) / c.notna().sum(axis=1)                         # 近似跌停占比
    if "bench" in P and P["bench"].shape[1]:
        bn = g.get("bench", P["bench"].columns[0])
        b = P["bench"][bn].reindex(c.index).ffill()
        trend = (b > b.rolling(60).mean()).astype(float)
        rv = b.pct_change().rolling(20).std() * np.sqrt(252)
        vol_pct = rv.rolling(250, min_periods=60).rank(pct=True)
    else:
        trend = pd.Series(1.0, index=c.index); vol_pct = pd.Series(0.5, index=c.index)
    score = (breadth >= g.get("breadth_min", 0.35)).astype(int) + (amt_pct >= g.get("amt_pct_min", 0.3)).astype(int) \
        + trend.astype(int) + (ld <= g.get("limit_down_max", 0.02)).astype(int) + (vol_pct <= g.get("vol_pct_max", 0.9)).astype(int)
    expo = score.map({0: 0.0, 1: 0.0, 2: 0.25, 3: 0.5, 4: 0.75, 5: 1.0}).astype(float)
    return expo.shift(0)          # t 日收盘信息 → t+1 日执行,无前视


def v42(P, F, cfg):
    s = {**DEFAULT_V42, **cfg.get("v42", {})}
    u = {**DEFAULT_V42["universe"], **s.get("universe", {})}
    elig = btw(P["mktcap"], u["mc_min"], u["mc_max"]) & (F["amt20"] >= u["amt20_min"]) & (P["list_days"] >= u["min_list_days"]) & (~P["susp"])
    if u.get("exclude_st", True):
        elig &= ~P["is_st"]
    elig &= btw(F["ret5"], u["min_ret5"], u["max_ret5"])
    up, _ = limit_prices(P)
    elig &= ~(P["close"] >= up - 0.005)
    if s["sleeve"] == "mom":
        elig &= (F["main5"] > 0) & (P["close"] > F["ma20"])
    elif s["sleeve"] == "rev":
        elig &= (F["main5"] > 0) & (F["bias20"] < -8) & (F["ret5"] < 0)
    # 因子合成:截面分位 → (中性化) → 加权
    comp = None
    for name, w in s["factors"].items():
        if name not in F:
            continue
        x = F[name]
        if s.get("neutralize", True):
            x = neutralize(x.where(elig), P["industry"], np.log(P["mktcap"]))
        x = rank01(x.where(elig))
        comp = x * w if comp is None else comp.add(x * w, fill_value=0)
    comp = comp.where(elig)
    expo = market_gate(P, F, s["gate"]) if s["gate"].get("enabled", True) else pd.Series(1.0, index=P["close"].index)
    return comp, elig & comp.notna(), expo


STRATS = {"v41": v41, "v42": v42}


def build_signal(P, F, spec):
    return STRATS[spec["strategy"]](P, F, spec)
