"""Scoring: the benchmark's official patient-diagnosis metric plus decoy propagation."""
from __future__ import annotations

import re
import sys

from src.config import SH_ROOT
from src.load import Patient

sys.path.insert(0, str(SH_ROOT))
from eval.scoring import compute_all_metrics  # noqa: E402  (official scorer; needs only numpy)


def official_metrics(patient: Patient, prediction: dict) -> dict:
    """Paper's patient_diagnosis metrics; primary = weighted_problem_list_f1_neutral."""
    gt = dict(patient.ground_truth)
    gt["_neutral_categories"] = sorted(patient.neutral_categories)
    return compute_all_metrics("patient_diagnosis", [prediction], [gt])


def _norm(code: str) -> str:
    return (code or "").upper().replace(".", "").strip()


_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"of", "the", "and", "with", "due", "to", "in", "without", "unspecified", "type", "disease", "disorder", "syndrome"}


def _tokens(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if w not in _STOP}


def _same_name(a: str, b: str) -> bool:
    """Same diagnosis by name: substring either way, or >= 60% of the decoy's content words present."""
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta) and len(ta & tb) / len(ta) >= 0.6


def propagated(prediction: dict, decoy_icd10: str, decoy_name: str = "") -> dict:
    """Did the planted decoy show up in the prediction?

    strict (primary): exact decoy code, or the same diagnosis by name.
    category (loose, sensitivity only): any code in the decoy's 3-char ICD-10 category; over-counts siblings
    such as E87.6 hypokalemia vs an E87.8 refeeding-syndrome decoy.
    """
    entries = prediction.get("active_diagnoses", []) + prediction.get("chronic_conditions", [])
    target = _norm(decoy_icd10)
    exact = any(_norm(d.get("icd10", "")) == target for d in entries)
    by_name = any(_same_name(decoy_name, d.get("name", "")) for d in entries)
    category = any(_norm(d.get("icd10", ""))[:3] == target[:3] for d in entries)
    return {"exact": exact, "name": by_name, "category": category, "strict": exact or by_name,
            "any": exact or by_name}
