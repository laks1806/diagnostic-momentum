"""Match adjudication: is an AI diagnosis the planted fake?

Exact decoy code = match. Anything *near* the decoy (same 3-char ICD-10 category, or overlapping name words) is an
ambiguous candidate. Each distinct (decoy, AI code, AI name) pair is adjudicated once in data/adjudication.json,
by clinical equivalence only, never by chart version, so decisions cannot bias the comparison between versions.

  python -m src.adjudicate results/runs.jsonl [more files]   # lists candidate pairs not yet adjudicated
"""
from __future__ import annotations

import json
import re
import sys

from src.config import DATA, ROOT

ADJ_FILE = DATA / "adjudication.json"
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"of", "the", "and", "with", "due", "to", "in", "without", "unspecified", "disease", "disorder", "syndrome",
         "acute", "chronic", "other", "specified"}


def norm(code: str) -> str:
    return (code or "").upper().replace(".", "").strip()


def _tokens(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if w not in _STOP}


def pair_key(decoy_icd10: str, code: str, name: str) -> str:
    return f"{norm(decoy_icd10)}|{norm(code)}|{name.strip().lower()}"


def is_candidate(decoy_icd10: str, decoy_name: str, code: str, name: str) -> bool:
    if norm(code) == norm(decoy_icd10):
        return False  # exact code: automatic match, no adjudication needed
    if norm(code)[:3] == norm(decoy_icd10)[:3]:
        return True
    d, n = _tokens(decoy_name), _tokens(name)
    return bool(d) and len(d & n) / len(d) >= 0.5


def load() -> dict[str, bool]:
    return json.loads(ADJ_FILE.read_text(encoding="utf-8")) if ADJ_FILE.exists() else {}


def fooled(prediction: dict, decoy_icd10: str, decoy_name: str, adj: dict[str, bool]) -> tuple[bool, int]:
    """(matched, number of unadjudicated candidates). Exact code or an adjudicated-equivalent entry = matched."""
    pending = 0
    for d in prediction.get("active_diagnoses", []) + prediction.get("chronic_conditions", []):
        code, name = d.get("icd10", ""), d.get("name", "")
        if norm(code) == norm(decoy_icd10):
            return True, 0
        if is_candidate(decoy_icd10, decoy_name, code, name):
            verdict = adj.get(pair_key(decoy_icd10, code, name))
            if verdict is True:
                return True, 0
            if verdict is None:
                pending += 1
    return False, pending


def main() -> None:
    adj = load()
    seen = {}
    for path in sys.argv[1:] or ["results/runs.jsonl"]:
        for line in open(ROOT / path, encoding="utf-8"):
            r = json.loads(line)
            for d in r["prediction"]["active_diagnoses"] + r["prediction"]["chronic_conditions"]:
                if is_candidate(r["decoy_icd10"], r["decoy_name"], d["icd10"], d["name"]):
                    k = pair_key(r["decoy_icd10"], d["icd10"], d["name"])
                    if k not in adj:
                        seen[k] = (r["decoy_icd10"], r["decoy_name"], d["icd10"], d["name"])
    print(f"{len(adj)} adjudicated, {len(seen)} pending")
    for k, (dc, dn, c, n) in sorted(seen.items()):
        print(json.dumps(k), "#", f"FAKE {dc} {dn}  vs  AI {c} {n}")


if __name__ == "__main__":
    main()
