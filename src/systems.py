"""Systems under test. S1 = the paper's locked CoT prompt verbatim; S2 = S1 + a caution instruction."""
from __future__ import annotations

import json
import re
import sys

from src.config import SH_ROOT

sys.path.insert(0, str(SH_ROOT))
from eval.prompts import PATIENT_DIAGNOSIS_COT  # noqa: E402

CAUTION = (
    "\n\nImportant: problem lists in this record are carried forward from earlier notes and may contain "
    "outdated or incorrect entries. Include a diagnosis only if the clinical evidence in the encounters "
    "supports it; do not copy problem-list entries that the record does not support or that were later ruled out."
)

ACUITY = {"acute": "acute", "chronic": "chronic", "acute_on_chronic": "acute_on_chronic", "subacute": "acute",
          "resolving": "acute", "stable": "chronic", "exacerbation": "acute_on_chronic", "flare": "acute_on_chronic",
          "acute on chronic": "acute_on_chronic", "acute-on-chronic": "acute_on_chronic"}


AUDITOR_SYSTEM = (
    "You are a clinical documentation integrity auditor for a health plan. You verify that every diagnosis "
    "billed for a patient is supported by clinical evidence documented in the encounter notes."
)

AUDITOR_USER = """PATIENT MEDICAL RECORD:
{ehr_text}

CANDIDATE DIAGNOSES (from a coder):
{candidates}

How to check: search every encounter, not just the latest. Problem-list entries show "(diagnosed YYYY-MM-DD)"; \
open the encounter on that date and look for the presentation and workup of that condition. Clinical evidence does \
not have to name the diagnosis: symptoms, examination findings, test or imaging results, procedures or treatment \
consistent with it all count.

For each candidate, decide:
- "supported": some encounter's history, examination, labs, imaging, procedures or treatment gives clinical evidence \
for this condition. Quote the most specific supporting sentence and give that encounter's date.
- "unsupported": the only mention is a problem-list line (problem lists are copied forward between notes and are \
not evidence by themselves), and no encounter shows a presentation or workup of this condition.
- "ruled_out": a note states the condition was excluded or ruled out.

Return ONLY valid JSON:
{{"verdicts": [{{"id": 1, "verdict": "supported|unsupported|ruled_out", "evidence": "quoted sentence or empty", "encounter_date": "YYYY-MM-DD or empty"}}, ...]}}"""


def build_audit_messages(chart_text: str, prediction: dict) -> tuple[list[dict], list[dict]]:
    """S3 step 2: ask an auditor to verify each of the coder's diagnoses against note evidence."""
    items = prediction.get("active_diagnoses", []) + prediction.get("chronic_conditions", [])
    lines = "\n".join(f"{i}. {d['icd10']} {d['name']}" for i, d in enumerate(items, 1))
    user = AUDITOR_USER.format(ehr_text=chart_text, candidates=lines or "(none)")
    return [{"role": "system", "content": AUDITOR_SYSTEM}, {"role": "user", "content": user}], items


def apply_audit(text: str, prediction: dict) -> tuple[dict, list[dict], bool]:
    """Keep only diagnoses the auditor marked 'supported'. Returns (filtered prediction, verdicts, parse_ok)."""
    items_active = prediction.get("active_diagnoses", [])
    items = items_active + prediction.get("chronic_conditions", [])
    text = re.sub(r"```(?:json)?", "", text)
    data = None
    for candidate in (text.strip(), *(m.group() for m in re.finditer(r"\{.*\}", text, re.DOTALL))):
        try:
            data = json.loads(candidate, strict=False)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(data, dict) or not isinstance(data.get("verdicts"), list):
        return prediction, [], False  # audit failed: fall back to the coder's list (counted as a parse failure)
    verdicts = [v for v in data["verdicts"] if isinstance(v, dict)]
    keep = {int(v["id"]) for v in verdicts if str(v.get("verdict", "")).lower() == "supported"
            and str(v.get("id", "")).isdigit()}
    n_active = len(items_active)
    filtered = {
        "active_diagnoses": [d for i, d in enumerate(items, 1) if i in keep and i <= n_active],
        "chronic_conditions": [d for i, d in enumerate(items, 1) if i in keep and i > n_active],
        "reasoning": prediction.get("reasoning", ""),
        "_parse_ok": True,
    }
    return filtered, verdicts, True


def build_messages(system: str, chart_text: str) -> list[dict]:
    user = PATIENT_DIAGNOSIS_COT.user.format(ehr_text=chart_text)
    if system == "S2_caution":
        user += CAUTION
    elif system != "S1_direct":
        raise ValueError(f"unknown system {system}")
    return [{"role": "system", "content": PATIENT_DIAGNOSIS_COT.system}, {"role": "user", "content": user}]


def _entries(items, default: str) -> list[dict]:
    out = []
    for d in items or []:
        if isinstance(d, dict) and d.get("icd10"):
            acuity = ACUITY.get(str(d.get("acuity", default)).lower().strip(), default)
            out.append({"icd10": str(d["icd10"]).strip(), "name": str(d.get("name", "")), "acuity": acuity})
    return out


def parse(text: str) -> dict:
    """Extract the final JSON object (the benchmark's parser needs licensed ICD-10 files, so we don't reuse it;
    unlike it, we do not prefix-correct invalid codes)."""
    text = re.sub(r"```(?:json)?", "", text)
    data = None
    for candidate in (text.strip(), *(m.group() for m in re.finditer(r"\{.*\}", text, re.DOTALL))):
        try:
            data = json.loads(candidate, strict=False)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(data, dict):
        return {"active_diagnoses": [], "chronic_conditions": [], "reasoning": "", "_parse_ok": False}
    active = data.get("active_diagnoses") or data.get("diagnoses") or []
    return {"active_diagnoses": _entries(active, "acute"),
            "chronic_conditions": _entries(data.get("chronic_conditions"), "chronic"),
            "reasoning": str(data.get("reasoning", "")), "_parse_ok": True}
