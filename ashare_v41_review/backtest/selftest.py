"""框架自检(合成数据):验证无前视、T+1、涨停不可买、植入信号可被发现、安慰剂无效、成本单调。
运行:python selftest.py  → 全部 PASS 才可信任引擎。"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from bt import metrics as M  # noqa: E402
from bt.engine import BtParams, run_backtest  # noqa: E402
from bt.factors import build_features, limit_prices  # noqa: E402
from bt.strategies import build_signal  # noqa: E402
from bt.synth import make_market  # noqa: E402

ok_all = True


def check(name, cond, info=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, info)


P = make_market(n_stock=300, n_days=520, alpha_strength=0.002)
F = build_features(P)

# 1 植入信号可识别:flow5_amt 的 5 日 IC 显著为正
rep = M.factor_report("flow5_amt", F["flow5_amt"].where(~P["is_st"]), P, horizons=(5,))[0]
check("植入的资金信号被 IC 检出", rep["IC均值"] > 0.015 and rep["IC_NW_t"] > 2, f"IC={rep['IC均值']:.4f} t={rep['IC_NW_t']:.1f}")

# 2 无前视:截断数据后同一天的信号必须与全样本一致
T = P["close"].index[400]
def trunc(P, T):
    Q = {}
    for k, v in P.items():
        if isinstance(v, pd.DataFrame) and k != "bench":
            Q[k] = v.loc[:T]
        elif k == "bench":
            Q[k] = v.loc[:T]
        else:
            Q[k] = v
    return Q
for st in ("v41", "v42"):
    s_full, e_full, x_full = build_signal(P, F, dict(strategy=st))
    Pq = trunc(P, T); Fq = build_features(Pq)
    s_cut, e_cut, x_cut = build_signal(Pq, Fq, dict(strategy=st))
    a, b = s_full.loc[T], s_cut.loc[T]
    m = a.notna() & b.notna()
    same = (e_full.loc[T] == e_cut.loc[T]).all() and np.allclose(a[m], b[m], atol=1e-8) and (a.notna() == b.notna()).all()
    check(f"{st} 信号无前视(截断不变性)", same and abs(x_full.loc[T] - x_cut.loc[T]) < 1e-12)

# 3 T+1 与涨停:所有交易退出日晚于入场日;入场开盘不是涨停
sc, el, ex = build_signal(P, F, dict(strategy="v42"))
res = run_backtest(P, sc, el, ex, BtParams())
tr = res["trades"]
check("T+1:退出日 > 入场日", (pd.to_datetime(tr["exit"]) > pd.to_datetime(tr["entry"])).all(), f"{len(tr)}笔")
up, dn = limit_prices(P)
bad = sum(P["open"].at[r.entry, r.code] >= up.at[r.entry, r.code] - 0.005 for r in tr.itertuples())
check("涨停开盘不可买入", bad == 0)
check("信号日早于入场日", (pd.to_datetime(tr["signal"]) < pd.to_datetime(tr["entry"])).all())

# 4 成本单调:滑点越高收益越低
r0 = M.perf(run_backtest(P, sc, el, ex, BtParams(slip_bps=0))["ret"])["总收益"]
r1 = M.perf(run_backtest(P, sc, el, ex, BtParams(slip_bps=30))["ret"])["总收益"]
check("成本单调(滑点0bp > 30bp)", r0 > r1, f"{r0:.3f} > {r1:.3f}")

# 5 安慰剂:同日随机打乱得分后,收益显著低于真实信号(植入 alpha 下)
rng = np.random.default_rng(3)
arr = sc.values.copy()
for k in range(arr.shape[0]):
    m = np.isfinite(arr[k]); v = arr[k][m]; rng.shuffle(v); arr[k][m] = v
sh = M.perf(run_backtest(P, pd.DataFrame(arr, index=sc.index, columns=sc.columns), el, ex, BtParams())["ret"])["年化收益"]
real = M.perf(res["ret"])["年化收益"]
check("安慰剂(打乱信号)劣于真实信号", real > sh, f"真实 {real:.3f} vs 打乱 {sh:.3f}")

# 6 无信号市场:alpha=0 时 IC≈0
P0 = make_market(n_stock=300, n_days=520, alpha_strength=0.0, seed=11)
rep0 = M.factor_report("flow5_amt", build_features(P0)["flow5_amt"], P0, horizons=(5,))[0]
check("无植入 alpha 时 IC 不显著", abs(rep0["IC_NW_t"]) < 3, f"IC={rep0['IC均值']:.4f} t={rep0['IC_NW_t']:.1f}")

print("\n=== 自检", "全部通过" if ok_all else "存在失败,请勿使用回测结果 ===")
sys.exit(0 if ok_all else 1)
