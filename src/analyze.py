"""Propagation rates, paired tests, and the headline figure.

  python -m src.analyze results/runs.jsonl
Writes results/summary.md, results/summary.json, results/fig_propagation.png
"""
from __future__ import annotations

import json
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from scipy.stats import binomtest, wilcoxon  # noqa: E402

from src import adjudicate  # noqa: E402
from src.config import RESULTS, ROOT  # noqa: E402
from src.score import propagated  # noqa: E402

VERSIONS = [  # order = the story: baseline -> dose -> contradiction -> recency
    ("clean", "Clean"),
    ("d1_late_nocontra", "Copied once"),
    ("d3_late_nocontra", "Copied 3×"),
    ("d3_late_contra", "3× + ruled out"),
    ("d3_early_nocontra", "Early, then dropped"),
]
SYSTEMS = [("S1_direct", "S1 · paper's prompt"), ("S2_caution", "S2 · + 'lists may be wrong'"),
           ("S3_verify", "S3 · coder + evidence auditor")]
COLORS = {"S1_direct": "#2a78d6", "S2_caution": "#eb6834", "S3_verify": "#1baf7a"}  # reference palette slots 1-3
INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar(a: dict[int, bool], b: dict[int, bool]) -> dict:
    """Exact McNemar on patients present in both: b10 = only A fooled, b01 = only B fooled."""
    pids = sorted(set(a) & set(b))
    b10 = sum(a[p] and not b[p] for p in pids)
    b01 = sum(b[p] and not a[p] for p in pids)
    pval = binomtest(b10, b10 + b01, 0.5).pvalue if b10 + b01 else 1.0
    return {"n_pairs": len(pids), "only_first": b10, "only_second": b01, "p": pval}


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "results/runs.jsonl"
    rows = [json.loads(l) for l in open(ROOT / path, encoding="utf-8")]
    model = sorted({r["model"] for r in rows})
    ok = [r for r in rows if r["parse_ok"]]
    adj = adjudicate.load()
    fooled = {}  # (system, condition) -> {patient: bool}   exact code or adjudicated match (primary)
    loose = {}   # same, 3-char category match (sensitivity)
    f1 = {}
    pending = 0
    for r in ok:
        p = propagated(r["prediction"], r["decoy_icd10"], r["decoy_name"])
        hit, n_pending = adjudicate.fooled(r["prediction"], r["decoy_icd10"], r["decoy_name"], adj)
        pending += n_pending
        fooled.setdefault((r["system"], r["condition"]), {})[r["patient_id"]] = hit
        loose.setdefault((r["system"], r["condition"]), {})[r["patient_id"]] = p["category"]
        f1.setdefault((r["system"], r["condition"]), {})[r["patient_id"]] = r["wf1n"]

    table = []
    for s, s_label in SYSTEMS:
        for c, c_label in VERSIONS:
            d = fooled.get((s, c))
            if not d:
                continue
            k, n = sum(d.values()), len(d)
            lo, hi = wilson(k, n)
            f = [v for v in f1[(s, c)].values() if v is not None]
            table.append({"system": s, "version": c, "label": c_label, "fooled": k, "n": n,
                          "rate": k / n, "ci_low": lo, "ci_high": hi, "mean_wf1n": sum(f) / len(f),
                          "loose_rate": sum(loose[(s, c)].values()) / n})

    S1 = lambda c: fooled.get(("S1_direct", c), {})  # noqa: E731
    tests = {
        "planted_3x_vs_clean (S1)": mcnemar(S1("d3_late_nocontra"), S1("clean")),
        "copied_3x_vs_once (S1)": mcnemar(S1("d3_late_nocontra"), S1("d1_late_nocontra")),
        "no_note_vs_ruled_out (S1)": mcnemar(S1("d3_late_nocontra"), S1("d3_late_contra")),
        "late_vs_early_dropped (S1)": mcnemar(S1("d3_late_nocontra"), S1("d3_early_nocontra")),
    }
    for sys_name in ("S2_caution", "S3_verify"):
        for c in ("d3_late_nocontra", "d3_late_contra"):
            if (sys_name, c) in fooled:
                tests[f"S1_vs_{sys_name[:2]} on {c}"] = mcnemar(S1(c), fooled[(sys_name, c)])

    def f1_change(label: str, a: dict, b: dict) -> None:
        pids = [p for p in a if p in b and a[p] is not None and b[p] is not None]
        if pids:
            diffs = [b[p] - a[p] for p in pids]
            tests[label] = {"n_pairs": len(pids), "mean_change": sum(diffs) / len(diffs),
                            "p": wilcoxon(diffs).pvalue if any(diffs) else 1.0}

    f1_change("F1 change: planted 3x vs clean (S1)", f1.get(("S1_direct", "clean"), {}),
              f1.get(("S1_direct", "d3_late_nocontra"), {}))
    f1_change("F1 change: S3 vs S1 on clean charts", f1.get(("S1_direct", "clean"), {}),
              f1.get(("S3_verify", "clean"), {}))
    f1_change("F1 change: S3 vs S1 on planted 3x", f1.get(("S1_direct", "d3_late_nocontra"), {}),
              f1.get(("S3_verify", "d3_late_nocontra"), {}))

    if pending:
        print(f"WARNING: {pending} AI diagnoses near the fake are not adjudicated yet; "
              f"run `python -m src.adjudicate {path}` and add them to data/adjudication.json\n")
    summary = {"source": path, "models": model, "rows": len(rows), "parse_failures": len(rows) - len(ok),
               "unadjudicated_candidates": pending,
               "cost_usd": round(sum(r.get("cost_usd", 0) for r in rows), 4), "table": table, "tests": tests}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=1))

    md = [f"# Results · {', '.join(model)} · {len(rows)} calls · ${summary['cost_usd']:.2f}",
          f"Parse failures: {summary['parse_failures']}", "",
          "Billed the fake = exact decoy code, or a diagnosis adjudicated as the same condition "
          "(data/adjudication.json). Loose = any code in the decoy's 3-character ICD-10 category "
          "(over-counts sibling diagnoses; sensitivity check only).", "",
          "| System | Version | Billed the fake | Rate | 95% CI | Loose rate | Mean wF1n |", "|---|---|---|---|---|---|---|"]
    for t in table:
        md.append(f"| {t['system']} | {t['label']} | {t['fooled']}/{t['n']} | {t['rate']:.0%} | "
                  f"{t['ci_low']:.0%}–{t['ci_high']:.0%} | {t['loose_rate']:.0%} | {t['mean_wf1n']:.3f} |")
    md += ["", "| Paired test | n | Only first | Only second | p |", "|---|---|---|---|---|"]
    for name, t in tests.items():
        if "mean_change" in t:
            md.append(f"| {name} | {t['n_pairs']} | mean change {t['mean_change']:+.3f} | | {t['p']:.3g} |")
        else:
            md.append(f"| {name} | {t['n_pairs']} | {t['only_first']} | {t['only_second']} | {t['p']:.3g} |")
    (RESULTS / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    figure(table, model, len(rows))


def figure(table: list[dict], model: list[str], n_calls: int, path=None, size=(9, 4.8), title=True,
           ylabel: str = "Charts where the AI billed the planted fake") -> None:
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 11})
    fig, ax = plt.subplots(figsize=size, dpi=200)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    labels = [lab for _, lab in VERSIONS]
    width = 0.24
    labelled = set()
    for j, (c, _) in enumerate(VERSIONS):
        present = [(s, s_label) for s, s_label in SYSTEMS if any(t["system"] == s and t["version"] == c for t in table)]
        for i, (s, s_label) in enumerate(present):
            t = next(u for u in table if u["system"] == s and u["version"] == c)
            x = j + (i - (len(present) - 1) / 2) * width
            ax.bar(x, t["rate"] * 100, width=width * 0.9, color=COLORS[s], zorder=3,
                   label=None if s in labelled else s_label)
            labelled.add(s)
            ax.plot([x, x], [t["ci_low"] * 100, t["ci_high"] * 100], color=INK2, lw=1.2, zorder=4)
            ax.text(x, t["ci_high"] * 100 + 2, f"{t['rate']:.0%}", ha="center", va="bottom", color=INK, fontsize=9)
    ax.set_xticks(range(len(labels)), labels, color=INK2)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], color=MUTED)
    ax.set_ylabel(ylabel, color=INK2)
    ax.grid(axis="y", color=GRID, lw=1, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.tick_params(length=0)
    handles, names = ax.get_legend_handles_labels()
    order = [lab for _, lab in SYSTEMS if lab in names]
    handles = [handles[names.index(lab)] for lab in order]
    ax.legend(handles, order, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=10,
              borderaxespad=0.2)
    n = max(t["n"] for t in table)
    if title:
        ax.set_title(f"How often the AI coder billed a planted wrong diagnosis ({', '.join(model)}, {n} patients)",
                     loc="left", color=INK, fontsize=12.5, pad=34)
        fig.text(0.01, 0.01, "Whiskers: 95% Wilson confidence interval. Same patients in every version. "
                 "A 0% label with no bar means no chart billed the fake.", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.03 if title else 0, 1, 1))
    fig.savefig(path or RESULTS / "fig_propagation.png", facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    main()
