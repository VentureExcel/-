"""入口:python run_backtest.py --config config.yaml --exp E1,E2,... --out out/
或    python run_backtest.py --synthetic --exp E1,E2 --out out_synth/   (框架自检)"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from bt import data as D  # noqa: E402
from bt.experiments import EXPERIMENTS  # noqa: E402
from bt.factors import build_features  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config"); ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--exp", default="E1,E2,E3,E4,E5,E6,E7,E8,E9"); ap.add_argument("--out", default="out")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config, encoding="utf8")) if a.config else {}
    if a.synthetic:
        from bt.synth import make_market
        P = make_market(**cfg.get("synthetic", {}))
    else:
        P = D.load_from_db(cfg)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    q = D.quality_report(P); q.to_csv(out / "00_数据体检.csv", index=False, encoding="utf-8-sig"); print(q.to_string())
    F = build_features(P)
    per = cfg.get("period", {})
    for e in a.exp.split(","):
        e = e.strip()
        print(f"=== {e} ...", flush=True)
        res = EXPERIMENTS[e](P, F, cfg)
        for k, v in res.items():
            if k.startswith("_nav"):
                v.to_csv(out / f"{k}.csv", encoding="utf-8-sig")
            else:
                v.to_csv(out / f"{k}.csv", index=False, encoding="utf-8-sig"); print(v.head(12).to_string())
    from bt.report import write_summary
    write_summary(out)


if __name__ == "__main__":
    main()
