"""Run systems x models over planted charts; append one JSON line per call (resumable).

Example (smoke test):
  python -m src.run --models kimi-k3 deepseek-v4-flash --systems S1_direct --patients 5 \
      --conditions clean d3_late_nocontra d3_late_contra --out results/smoke.jsonl
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import DATA, ROOT
from src.llm import chat, cost_usd, has_price
from src.load import connect, load_patient
from src.score import official_metrics, propagated
from src.systems import apply_audit, build_audit_messages, build_messages, parse

PRIMARY = "weighted_problem_list_f1_neutral"
_lock = threading.Lock()


class Budget:
    """Hard spending cap. A call starts only while spent + one worst-case call stays under the limit."""

    def __init__(self, limit: float, spent: float):
        self.limit, self.spent, self.stopped = limit, spent, False

    def try_start(self, worst_case: float) -> bool:
        with _lock:
            if self.spent + worst_case > self.limit:
                self.stopped = True
                return False
            self.spent += worst_case  # reserve; settled to the real cost when the call returns
            return True

    def settle(self, reserved: float, actual: float) -> None:
        with _lock:
            self.spent += actual - reserved


def load_charts(patients: int | None, conditions: list[str] | None) -> list[dict]:
    rows = [json.loads(l) for l in open(DATA / "charts.jsonl", encoding="utf-8")]
    pids = sorted({r["patient_id"] for r in rows})[:patients] if patients else None
    return [r for r in rows if (pids is None or r["patient_id"] in pids)
            and (not conditions or r["condition"] in conditions)]


def key(model: str, system: str, chart: dict) -> str:
    return f"{model}|{system}|{chart['patient_id']}|{chart['condition']}"


MAX_OUTPUT = 16384


REASONING_EFFORT: str | None = None  # set from --reasoning-effort; recorded on every row
MIN_INTERVAL = 0.0  # set from --min-interval: seconds between call starts (free-tier per-minute limits)
_pace_lock = threading.Lock()
_last_start = [0.0]


def _pace() -> None:
    if MIN_INTERVAL <= 0:
        return
    with _pace_lock:
        wait = _last_start[0] + MIN_INTERVAL - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_start[0] = time.time()


def run_one(model: str, system: str, chart: dict, patient, budget: Budget, coder_pred: dict | None = None) -> dict | None:
    """S1/S2: one coding call. S3_verify: an auditor call that checks `coder_pred` (the saved S1 answer)."""
    audit = system == "S3_verify"
    if audit:
        messages, _ = build_audit_messages(chart["chart_text"], coder_pred)
    else:
        messages = build_messages(system, chart["chart_text"])
    est_input = sum(len(m["content"]) for m in messages) // 3  # generous chars-per-token estimate
    worst = cost_usd(model, est_input, MAX_OUTPUT)
    if not budget.try_start(worst):
        return None
    try:
        _pace()
        resp = chat(model, messages, max_tokens=MAX_OUTPUT, reasoning_effort=REASONING_EFFORT)
    except Exception:
        budget.settle(worst, 0.0)  # conservative: failed calls are rarely billed
        raise
    cost = cost_usd(model, resp["input_tokens"], resp["output_tokens"])
    budget.settle(worst, cost)
    verdicts = None
    if audit:
        pred, verdicts, ok = apply_audit(resp["text"] or resp["reasoning"], coder_pred)
        pred = {**pred, "_parse_ok": ok}
    else:
        pred = parse(resp["text"])
        if not pred["_parse_ok"] and resp["reasoning"]:
            pred = parse(resp["reasoning"])
    metrics = official_metrics(patient, pred) if pred["_parse_ok"] else {}
    d = chart["decoy"]
    return {
        "key": key(model, system, chart), "model": model, "system": system,
        **{k: chart[k] for k in ("patient_id", "gt_id", "condition", "dose", "recency", "contradiction")},
        "decoy_icd10": d["icd10"], "decoy_name": d["name"],
        "parse_ok": pred["_parse_ok"], "wf1n": metrics.get(PRIMARY),
        "recall": metrics.get("problem_list_recall"), "precision_neutral": metrics.get("problem_list_precision_neutral"),
        "propagated": propagated(pred, d["icd10"], d["name"]),
        "prediction": {k: pred[k] for k in ("active_diagnoses", "chronic_conditions")},
        "reasoning": pred.get("reasoning", "")[:4000],
        "raw_tail": resp["text"][-1500:],
        **{k: resp[k] for k in ("input_tokens", "output_tokens", "finish_reason", "seconds")},
        "cost_usd": round(cost, 6),
        "reasoning_effort": REASONING_EFFORT,
        **({"audit_verdicts": verdicts, "coder_prediction": {k: coder_pred[k] for k in
            ("active_diagnoses", "chronic_conditions")}} if audit else {}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--systems", nargs="+", default=["S1_direct"])
    ap.add_argument("--patients", type=int)
    ap.add_argument("--conditions", nargs="*")
    ap.add_argument("--out", default="results/runs.jsonl")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--budget", type=float, default=2.0, help="hard cap in USD for everything in --out")
    ap.add_argument("--reasoning-effort", choices=["low", "medium", "high"], help="omit for the model default")
    ap.add_argument("--min-interval", type=float, default=0.0, help="seconds between call starts, e.g. 15 for Gemini free tier")
    args = ap.parse_args()
    global REASONING_EFFORT, MIN_INTERVAL
    REASONING_EFFORT = args.reasoning_effort
    MIN_INTERVAL = args.min_interval

    unknown = [m for m in args.models if not has_price(m)]
    if unknown:
        raise SystemExit(f"no price on file for {unknown}; add it to PRICES in src/llm.py first")
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    previous = [json.loads(l) for l in open(out, encoding="utf-8")] if out.exists() else []
    done = {r["key"] for r in previous}
    budget = Budget(args.budget, sum(r.get("cost_usd", 0.0) for r in previous))
    charts = load_charts(args.patients, args.conditions)
    con = connect()
    patients = {pid: load_patient(con, pid) for pid in {c["patient_id"] for c in charts}}
    coder = {(r["model"], r["patient_id"], r["condition"]): r["prediction"]  # saved S1 answers, for S3's auditor
             for r in previous if r["system"] == "S1_direct" and r["parse_ok"]}
    jobs = [(m, s, c) for m in args.models for s in args.systems for c in charts if key(m, s, c) not in done]
    missing = [j for j in jobs if j[1] == "S3_verify" and (j[0], j[2]["patient_id"], j[2]["condition"]) not in coder]
    if missing:
        print(f"skipping {len(missing)} S3 calls with no saved S1 answer in {args.out} (run S1 first)")
        jobs = [j for j in jobs if j not in missing]
    print(f"{len(jobs)} calls to make ({len(done)} already done) | spent so far ${budget.spent:.4f} of ${args.budget:.2f}")

    with ThreadPoolExecutor(args.workers) as pool, open(out, "a", encoding="utf-8") as f:
        futures = {pool.submit(run_one, m, s, c, patients[c["patient_id"]], budget,
                               coder.get((m, c["patient_id"], c["condition"]))): (m, s, c) for m, s, c in jobs}
        for i, fut in enumerate(as_completed(futures), 1):
            m, s, c = futures[fut]
            try:
                row = fut.result()
            except Exception as e:
                print(f"[{i}/{len(jobs)}] FAILED {key(m, s, c)}: {type(e).__name__}: {str(e)[:200]}")
                continue
            if row is None:
                continue  # skipped by the budget cap
            with _lock:
                f.write(json.dumps(row) + "\n")
                f.flush()
            wf1 = f"{row['wf1n']:.2f}" if row["wf1n"] is not None else "n/a"
            print(f"[{i}/{len(jobs)}] {row['key']}  wF1n={wf1}  decoy={'YES' if row['propagated']['any'] else 'no'}"
                  f"  parse={row['parse_ok']}  {row['seconds']}s  out_tok={row['output_tokens']}  ${row['cost_usd']:.4f}")

    print(f"\nTotal spent in {args.out}: ${budget.spent:.4f} (cap ${args.budget:.2f})")
    if budget.stopped:
        print("Budget cap reached: some calls were skipped. Rerun with a higher --budget to finish them.")


if __name__ == "__main__":
    main()
