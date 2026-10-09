"""实验矩阵 E1~E9(见 docs/回测方案)。每个实验返回 dict[name -> DataFrame],由 runner 落盘。"""
from __future__ import annotations

import copy
import itertools

import numpy as np
import pandas as pd

from . import metrics as M
from .engine import BtParams, run_backtest
from .factors import btw, build_features
from .strategies import build_signal, neutralize, v41_score


def bench_ret(P, name=None):
    b = P.get("bench")
    if b is None or b.empty:
        return None
    name = name if name in b.columns else b.columns[0]
    return b[name].pct_change()


def run_spec(P, F, spec: dict, bt: BtParams, period: tuple | None = None, bench_name=None, cache: dict | None = None):
    key = repr(sorted((k, repr(v)) for k, v in spec.items()))
    if cache is not None and key in cache:
        sig = cache[key]
    else:
        sig = build_signal(P, F, spec)
        if cache is not None:
            cache[key] = sig
    score, elig, expo = sig
    res = run_backtest(P, score, elig, expo, bt, *(period or (None, None)))
    st = M.perf(res["ret"], bench_ret(P, bench_name))
    st.update(M.trade_stats(res["trades"]))
    st["平均敞口"] = res["exposure"].mean()
    return res, st


def _bt(cfg, **kw):
    d = {**cfg.get("backtest", {}), **kw}
    return BtParams(**d)


def E1_factor_ic(P, F, cfg, horizons=(1, 3, 5, 10, 20), neutral=True):
    """单因子体检:IC/ICIR/多空/单调性,原始 vs 行业市值中性。"""
    rows = []
    elig = btw(P["mktcap"], 30, 500) & (~P["is_st"]) & (~P["susp"]) & (P["list_days"] >= 120)
    score, dims = v41_score(P, F, cfg)
    cand = {k: F[k] for k in ("flow_ratio", "flow_amt", "flow5_amt", "flow20_amt", "flow_z60", "flow_pos5", "flow_accel", "retail_div",
                              "flow_conc", "turn_rel", "amt_rank", "ret5", "ret20", "bias20", "atr_pct") if k in F}
    cand.update({f"V41_{k}": v for k, v in dims.items()})
    cand["V41_修正综合分"] = score
    cand["V41_space"] = None
    from .factors import space_to_pressure
    cand["V41_space"] = space_to_pressure(P, F)
    logcap = np.log(P["mktcap"])
    for name, x in cand.items():
        xx = x.where(elig)
        for r in M.factor_report(name, xx, P, horizons):
            r["中性化"] = "否"; rows.append(r)
        if neutral:
            xn = neutralize(xx, P["industry"], logcap)
            for r in M.factor_report(name, xn, P, horizons):
                r["中性化"] = "行业+市值"; rows.append(r)
    return {"E1_因子体检": pd.DataFrame(rows)}


def E2_baseline_ablation(P, F, cfg):
    bt = _bt(cfg)
    base = dict(strategy="v41")
    variants = {
        "E2-0 V4.1复刻(基线)": {},
        "E2-1 去掉Overheat": dict(v41=dict(overheat_k=0)),
        "E2-2 Overheat系数3.0": dict(v41=dict(overheat_k=3.0)),
        "E2-3 去掉D4空间性价比": dict(v41=dict(weights=dict(D1=.4375, D2=.3125, D3=.25, D4=0.0))),
        "E2-4 等权四维": dict(v41=dict(weights=dict(D1=.25, D2=.25, D3=.25, D4=.25))),
        "E2-5 去掉[4]主力散户同向剔除": dict(v41=dict(filter_retail_same_sign=False)),
        "E2-6 去掉C4(5日累计>0)": dict(v41=dict(c4=False)),
        "E2-7 前5%": dict(v41=dict(top_pct=0.05)),
        "E2-8 前30%": dict(v41=dict(top_pct=0.30)),
        "E2-9 去掉初筛主力>0当日条件": None,
    }
    rows, navs = [], {}
    cache = {}
    for name, ov in variants.items():
        if ov is None:
            continue
        spec = {**base, **ov}
        res, st = run_spec(P, F, spec, bt, cache=cache)
        rows.append(dict(方案=name, **st)); navs[name] = (1 + res["ret"]).cumprod()
    return {"E2_基线与消融": pd.DataFrame(rows), "_nav_E2": pd.DataFrame(navs)}


def E3_hold_stop_grid(P, F, cfg, strategies=("v41", "v42")):
    rows = []
    for sname in strategies:
        spec = dict(strategy=sname, **cfg.get(sname, {}) and {sname: cfg.get(sname)})
        sig = build_signal(P, F, spec)
        grid = itertools.product((3, 5), (None, 0.08), (10,)) if cfg.get('fast') else itertools.product((1, 3, 5, 10, 20), (None, 0.05, 0.08, 0.12), (5, 10, 20))
        for hold, stop, topn in grid:
            bt = _bt(cfg, hold=hold, stop_loss=stop, top_n=topn)
            res = run_backtest(P, *sig, bt)
            st = M.perf(res["ret"], bench_ret(P)); st.update(M.trade_stats(res["trades"]))
            rows.append(dict(策略=sname, 持有=hold, 止损=stop, TopN=topn, **st))
    return {"E3_持有期止损网格": pd.DataFrame(rows)}


def E4_v42_variants(P, F, cfg):
    bt = _bt(cfg)
    variants = {
        "E4-0 V4.2 动量子策略(默认)": dict(v42=dict(sleeve="mom")),
        "E4-1 V4.2 反转子策略": dict(v42=dict(sleeve="rev")),
        "E4-2 动量+不中性化": dict(v42=dict(sleeve="mom", neutralize=False)),
        "E4-3 动量+无大盘闸门": dict(v42=dict(sleeve="mom", gate=dict(enabled=False))),
        "E4-4 仅资金类因子": dict(v42=dict(sleeve="mom", factors={"flow5_amt": .4, "flow_z60": .3, "flow_pos5": .15, "retail_div": .15})),
        "E4-5 资金+低波动": dict(v42=dict(sleeve="mom", factors={"flow5_amt": .35, "flow_z60": .25, "atr_pct": -.25, "ret20": .15})),
    }
    rows, navs = [], {}
    cache = {}
    for name, ov in variants.items():
        res, st = run_spec(P, F, dict(strategy="v42", **ov), bt, cache=cache)
        rows.append(dict(方案=name, **st)); navs[name] = (1 + res["ret"]).cumprod()
    res, st = run_spec(P, F, dict(strategy="v41"), bt)
    rows.insert(0, dict(方案="V4.1 复刻(对照)", **st)); navs["V4.1 复刻(对照)"] = (1 + res["ret"]).cumprod()
    return {"E4_V42变体": pd.DataFrame(rows), "_nav_E4": pd.DataFrame(navs)}


def E5_costs_capacity(P, F, cfg, spec=None):
    spec = spec or dict(strategy="v42")
    sig = build_signal(P, F, spec)
    rows = []
    for slip, cap in (itertools.product((5, 20), (5e6, 2e8)) if cfg.get('fast') else itertools.product((0, 5, 10, 20, 30), (5e6, 5e7, 2e8, 1e9))):
        res = run_backtest(P, *sig, _bt(cfg, slip_bps=slip, capital=cap))
        st = M.perf(res["ret"], bench_ret(P)); st.update(M.trade_stats(res["trades"]))
        rows.append(dict(滑点bp=slip, 资金规模=cap, **st))
    return {"E5_成本与容量": pd.DataFrame(rows)}


def E6_gate(P, F, cfg):
    bt = _bt(cfg); rows = []; navs = {}
    for name, g in {"无闸门": dict(enabled=False), "默认闸门": dict(enabled=True),
                    "严格闸门(广度≥45%)": dict(enabled=True, breadth_min=.45), "宽松闸门(广度≥25%)": dict(enabled=True, breadth_min=.25)}.items():
        res, st = run_spec(P, F, dict(strategy="v42", v42=dict(gate=g)), bt)
        rows.append(dict(方案=name, **st)); navs[name] = (1 + res["ret"]).cumprod()
    return {"E6_大盘闸门": pd.DataFrame(rows), "_nav_E6": pd.DataFrame(navs)}


def E7_walk_forward(P, F, cfg, train=250, test=60):
    """候选集 = 持有期×止损×TopN 的 v42 变体;滚动窗口在训练期选夏普最高者,拼接样本外。"""
    sig = build_signal(P, F, dict(strategy="v42"))
    cands = {}
    for hold, stop, topn in (itertools.product((3, 5), (None, 0.08), (10,)) if cfg.get('fast') else itertools.product((3, 5, 10), (None, 0.08), (10, 20))):
        res = run_backtest(P, *sig, _bt(cfg, hold=hold, stop_loss=stop, top_n=topn))
        cands[(hold, stop, topn)] = res["ret"]
    R = pd.DataFrame(cands)
    idx = R.index; oos = []; chosen = []
    i = train
    while i < len(idx):
        tr, te = R.iloc[i - train:i], R.iloc[i:i + test]
        sh = tr.mean() / tr.std().replace(0, np.nan)
        best = sh.idxmax(); chosen.append(dict(起=te.index[0], 止=te.index[-1], 选中=str(best), 训练夏普=float(sh[best] * np.sqrt(252))))
        oos.append(te[best]); i += test
    oos = pd.concat(oos) if oos else pd.Series(dtype=float)
    st = M.perf(oos, bench_ret(P)); st["候选数"] = R.shape[1]
    st["通缩夏普概率"] = M.deflated_sharpe(oos, R.shape[1])
    allperf = pd.DataFrame({str(k): M.perf(R[k]) for k in R.columns}).T
    return {"E7_滚动样本外": pd.DataFrame([dict(方案="Walk-forward样本外", **st)]), "E7_每期选择": pd.DataFrame(chosen), "E7_全部候选": allperf}


def E8_oos_split(P, F, cfg, oos_start="2026-01-01"):
    oos_start = cfg.get("period", {}).get("oos_start", oos_start)
    rows = []; bt = _bt(cfg)
    for sname in ("v41", "v42"):
        sig = build_signal(P, F, dict(strategy=sname))
        for lab, per in (("样本内", (None, pd.Timestamp(oos_start) - pd.Timedelta(days=1))), ("样本外", (oos_start, None)), ("全样本", (None, None))):
            res = run_backtest(P, *sig, bt, *per)
            st = M.perf(res["ret"], bench_ret(P)); st.update(M.trade_stats(res["trades"]))
            lo, hi = M.block_bootstrap_sharpe(res["ret"], B=300)
            rows.append(dict(策略=sname, 区间=lab, 夏普5分位=lo, 夏普95分位=hi, **st))
    return {"E8_样本内外": pd.DataFrame(rows)}


def E9_placebo_delay(P, F, cfg, n_shuffle=20):
    n_shuffle = 5 if cfg.get('fast') else n_shuffle
    """安慰剂:同日随机打乱得分;延迟检验:信号延后 1/2/3 日执行,衡量信息衰减。"""
    bt = _bt(cfg); rows = []
    score, elig, expo = build_signal(P, F, dict(strategy="v42"))
    base = M.perf(run_backtest(P, score, elig, expo, bt)["ret"], bench_ret(P))
    rng = np.random.default_rng(1)
    sh = []
    for _ in range(n_shuffle):
        s2 = score.copy()
        arr = s2.values.copy()
        for k in range(arr.shape[0]):
            m = np.isfinite(arr[k]); v = arr[k][m]; rng.shuffle(v); arr[k][m] = v
        s2 = pd.DataFrame(arr, index=score.index, columns=score.columns)
        sh.append(M.perf(run_backtest(P, s2, elig, expo, bt)["ret"], bench_ret(P)).get("年化收益", np.nan))
    rows.append(dict(检验="真实信号年化", 值=base.get("年化收益")))
    rows.append(dict(检验="随机打乱年化均值", 值=float(np.nanmean(sh))))
    rows.append(dict(检验="随机打乱年化95分位", 值=float(np.nanpercentile(sh, 95))))
    rows.append(dict(检验="真实信号高于随机95分位?", 值=bool(base.get("年化收益", -9) > np.nanpercentile(sh, 95))))
    for d in (1, 2, 3):
        res = run_backtest(P, score.shift(d), elig.shift(d, fill_value=False), expo.shift(d).fillna(0), bt)
        rows.append(dict(检验=f"信号延迟{d}日年化", 值=M.perf(res["ret"], bench_ret(P)).get("年化收益")))
    return {"E9_安慰剂与延迟": pd.DataFrame(rows)}


EXPERIMENTS = {"E1": E1_factor_ic, "E2": E2_baseline_ablation, "E3": E3_hold_stop_grid, "E4": E4_v42_variants,
               "E5": E5_costs_capacity, "E6": E6_gate, "E7": E7_walk_forward, "E8": E8_oos_split, "E9": E9_placebo_delay}
