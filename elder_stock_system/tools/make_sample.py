"""生成示例数据(合成,仅用于演示公式与图表,非真实行情)。"""
import numpy as np, pandas as pd

def make_sample(n=306, seed=146, start="2025-01-02", gen=330):
    """先按 gen 根生成再截取前 n 根(保证随机路径固定)。"""
    n_out, n = n, gen
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n)
    # 周期性趋势+回调的状态机,制造"上升趋势中回调到价值区"与背离场景
    drift = np.zeros(n)
    phase = 0
    i = 0
    while i < n:
        L = rng.integers(18, 40)
        up = (phase % 3 != 2)
        drift[i:i+L] = (0.0045 if up else -0.0070) * (1 if rng.random() > .15 else -.4)
        phase += 1; i += L
    ret = drift + rng.normal(0, 0.014, n)
    close = 20 * np.exp(np.cumsum(ret))
    openp = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.004, n))
    rngd = np.abs(rng.normal(0.012, 0.005, n)) * close
    high = np.maximum(openp, close) + rngd * rng.uniform(.2, .8, n)
    low = np.minimum(openp, close) - rngd * rng.uniform(.2, .8, n)
    vol = (3e6 * (1 + 25 * np.abs(ret)) * rng.uniform(.7, 1.3, n)).round(-2)
    df = pd.DataFrame({"date": dates, "open": openp.round(2), "high": high.round(2),
                       "low": low.round(2), "close": close.round(2), "volume": vol})
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
    return df.iloc[:n_out].reset_index(drop=True)

if __name__ == "__main__":
    df = make_sample(); df.to_csv("../step1/assets/sample_ohlcv.csv", index=False)
    print(df.describe().T[["min","max"]]); print(df.tail(3))
