"""Quick tables from a results file: propagation rate and official F1 by model x system x condition.

  python -m src.summarize results/smoke.jsonl
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from src.config import ROOT


def load(path: str) -> pd.DataFrame:
    rows = [json.loads(l) for l in open(ROOT / path, encoding="utf-8")]
    df = pd.DataFrame(rows)
    df["propagated_any"] = df["propagated"].map(lambda p: p["any"])
    df["propagated_exact"] = df["propagated"].map(lambda p: p["exact"])
    return df


def main() -> None:
    df = load(sys.argv[1] if len(sys.argv) > 1 else "results/runs.jsonl")
    ok = df[df["parse_ok"]]
    print(f"rows: {len(df)} | parsed: {len(ok)} | parse failures: {len(df) - len(ok)}")
    table = (ok.groupby(["model", "system", "condition"])
               .agg(n=("key", "size"), propagation=("propagated_any", "mean"),
                    wF1n=("wf1n", "mean"), recall=("recall", "mean"), out_tok=("output_tokens", "mean"),
                    secs=("seconds", "mean"))
               .round(3))
    with pd.option_context("display.width", 200, "display.max_rows", 500):
        print(table)


if __name__ == "__main__":
    main()
