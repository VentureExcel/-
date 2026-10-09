"""数据层:从本地数据库读入并整理为宽表面板(日期 × 代码)。

面板字段(P 为 dict):
  open/high/low/close   未复权价格         adj      复权因子(后复权累计,无则全 1)
  volume(股) amount(元)  turnover(%)        mktcap(亿元,流通或总市值,须与实盘一致)
  main_net(元)           主力净流入         small_net(元) 散户(小单)净流入;mid_net 可选
  is_st(bool) susp(bool) list_days(上市天数)  industry(Series 代码→申万一级)
  bench(DataFrame 日期×指数名)  基准指数收盘价
所有数据"点时(point-in-time)"使用:第 t 日的值只含 t 日收盘后可得信息。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = ["open", "high", "low", "close", "volume", "amount"]
OPTIONAL = ["adj", "turnover", "mktcap", "is_st", "susp", "list_days"]
FLOW = ["main_net", "small_net", "mid_net", "big_net", "super_net"]


def norm_code(s: pd.Series) -> pd.Series:
    """000001.SZ / sz000001 / 1 → 000001"""
    s = s.astype(str).str.upper().str.replace(r"[^0-9]", "", regex=True)
    return s.str[-6:].str.zfill(6)


def _connect(cfg_db: dict):
    url = cfg_db["url"]
    if url.startswith("sqlite:///"):
        return sqlite3.connect(url.replace("sqlite:///", "", 1))
    try:
        from sqlalchemy import create_engine
        return create_engine(url)
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("非 sqlite 数据库请 pip install sqlalchemy 及对应驱动(pymysql/psycopg2/duckdb-engine)") from e


def _read(conn, spec: dict) -> pd.DataFrame:
    """spec: {table, columns:{逻辑名:物理列}, where?} 或 {sql, columns}"""
    cols = spec["columns"]
    if "sql" in spec:
        q = spec["sql"]
    else:
        sel = ", ".join(f'{v} AS {k}' for k, v in cols.items())
        q = f"SELECT {sel} FROM {spec['table']}" + (f" WHERE {spec['where']}" if spec.get("where") else "")
    df = pd.read_sql(q, conn)
    if "sql" in spec:  # 自定义 SQL 需自行 AS 成逻辑名;缺失则按 columns 重命名
        df = df.rename(columns={v: k for k, v in cols.items() if v in df.columns and k not in df.columns})
    return df


def _pivot(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.pivot_table(index="date", columns="code", values=col, aggfunc="last")


def load_from_db(cfg: dict) -> dict:
    conn = _connect(cfg["db"])
    t = cfg["tables"]
    P: dict = {}
    k = _read(conn, t["kline"])
    k["date"] = pd.to_datetime(k["date"]); k["code"] = norm_code(k["code"])
    start, end = cfg.get("period", {}).get("start"), cfg.get("period", {}).get("end")
    if start: k = k[k["date"] >= pd.Timestamp(start) - pd.Timedelta(days=int(cfg.get("period", {}).get("warmup_days", 400)))]
    if end: k = k[k["date"] <= pd.Timestamp(end)]
    for c in REQUIRED + [c for c in OPTIONAL if c in k.columns]:
        if c in k.columns:
            P[c] = _pivot(k, c)
    if "is_st" in P: P["is_st"] = P["is_st"].fillna(0).astype(bool)
    if "susp" in P: P["susp"] = P["susp"].fillna(0).astype(bool)
    if "flow" in t:
        f = _read(conn, t["flow"])
        f["date"] = pd.to_datetime(f["date"]); f["code"] = norm_code(f["code"])
        for c in FLOW:
            if c in f.columns:
                P[c] = _pivot(f, c)
    if "industry" in t:
        ind = _read(conn, t["industry"]); ind["code"] = norm_code(ind["code"])
        P["industry"] = ind.drop_duplicates("code", keep="last").set_index("code")["industry"]
    if "bench" in t:
        b = _read(conn, t["bench"]); b["date"] = pd.to_datetime(b["date"])
        P["bench"] = b.pivot_table(index="date", columns="name", values="close", aggfunc="last")
    return finalize(P, cfg)


def finalize(P: dict, cfg: dict | None = None) -> dict:
    """对齐索引、补默认字段、派生复权价。"""
    cal = P["close"].index.sort_values()
    codes = P["close"].columns
    for k, v in list(P.items()):
        if isinstance(v, pd.DataFrame) and k != "bench":
            P[k] = v.reindex(index=cal, columns=codes)
    if "adj" not in P:
        P["adj"] = pd.DataFrame(1.0, index=cal, columns=codes)
    P["adj"] = P["adj"].ffill().fillna(1.0)
    if "susp" not in P:
        P["susp"] = P["volume"].fillna(0).le(0) | P["close"].isna()
    if "is_st" not in P:
        P["is_st"] = pd.DataFrame(False, index=cal, columns=codes)
    if "turnover" not in P and "mktcap" in P:
        P["turnover"] = P["amount"] / (P["mktcap"] * 1e8) * 100
    if "list_days" not in P:
        first = P["close"].notna().cumsum()
        P["list_days"] = first
    for k in ("open", "high", "low", "close"):
        P["a_" + k] = P[k] * P["adj"]
    if "industry" in P:
        P["industry"] = P["industry"].reindex(codes).fillna("未知")
    if cfg and "period" in cfg:
        P["_period"] = cfg["period"]
    return P


def quality_report(P: dict) -> pd.DataFrame:
    """数据体检:缺失率、异常值、重复、前视泄漏线索。"""
    rows = []
    c = P["close"]
    rows.append(("交易日数", len(c), "日历是否完整(对照交易所日历)"))
    rows.append(("股票数", c.shape[1], "含已退市/ST 才无幸存者偏差"))
    for k in ("open", "close", "amount", "mktcap", "main_net", "small_net", "turnover"):
        if k in P:
            rows.append((f"{k} 缺失率", float(P[k].isna().mean().mean()), "应 <2%,且不应集中在个别日期"))
    ret = c.pct_change()
    rows.append(("单日|收益|>25% 的占比(未复权)", float((ret.abs() > .25).mean().mean()), "过高=复权/拆股问题"))
    if "main_net" in P:
        rows.append(("main_net/amount 绝对值 >1 占比", float((P["main_net"].abs() > P["amount"]).mean().mean()), "应≈0,否则单位错误(元/万元)"))
    rows.append(("OHLC 不自洽占比", float((P["high"] < P["low"]).mean().mean()), "应=0"))
    return pd.DataFrame(rows, columns=["检查项", "值", "标准/说明"])
