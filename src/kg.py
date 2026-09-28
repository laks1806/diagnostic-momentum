"""Knowledge-graph queries: patient findings and decoy (planted wrong diagnosis) selection."""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from src.load import Patient, render_chart

SUPPORT_RELATIONS = ("commonly_seen", "highly_suggestive", "pathognomonic")
ICD10_RE = re.compile(r"^[A-Z][0-9][0-9A-Z]")
DISEASE_CHAPTERS = set("ABCDEFGHIJKLMNQ")  # infections … genitourinary, congenital; no symptoms/injuries/Z-factors
NON_DIAGNOSIS = re.compile(r"\b(prophylaxis|therapy|treatment|management|managed|screening|counsel\w*|encounter|"
                           r"vaccin\w*|candidate|test|exam\w*|requiring|tolerating|controlled|history of|"
                           r"status post|refractory)\b| or |/", re.I)
WORD = re.compile(r"[a-z0-9]+")


def _too_similar(name: str, true_names: set[str]) -> bool:
    """Near-duplicate of a true diagnosis (e.g. 'Complete androgen insensitivity' vs 'Androgen insensitivity')."""
    a = set(WORD.findall(name.lower()))
    for t in true_names:
        b = set(WORD.findall(t))
        if a and b and (len(a & b) / len(a | b) >= 0.5 or t in name.lower() or name.lower() in t):
            return True
    return False


@dataclass
class Decoy:
    diagnosis_id: int
    icd10: str
    name: str
    acuity: str
    support_present: int          # supporting findings of the decoy present in the patient's chart
    natural_rules_out: list[str]  # findings already in the chart that the KG says rule the decoy out
    mentioned_in_chart: bool      # decoy name already appears in the clean chart (e.g. as a differential)


MALE_ONLY = [("N40", "N53"), ("C60", "C63"), ("E29", "E29"), ("D29", "D29"), ("D40", "D40")]
FEMALE_ONLY = [("N70", "N98"), ("C51", "C58"), ("E28", "E28"), ("D25", "D28"), ("D39", "D39")]


def _in_ranges(cat: str, ranges: list[tuple[str, str]]) -> bool:
    return any(lo <= cat <= hi for lo, hi in ranges)


def _fits_patient(icd: str, patient: Patient) -> bool:
    cat = icd[:3]
    if (patient.sex == "F" and _in_ranges(cat, MALE_ONLY)) or (patient.sex == "M" and _in_ranges(cat, FEMALE_ONLY)):
        return False
    ch = icd[0]
    if ch == "O":
        return patient.sex == "F" and 12 <= (patient.age or 0) <= 55
    if ch == "P":
        return (patient.age or 0) < 1
    return ch in DISEASE_CHAPTERS


class KG:
    def __init__(self, con: sqlite3.Connection):
        self.diagnoses = {did: (icd, name, acuity) for did, icd, name, acuity in
                          con.execute("select diagnosis_id, icd10_code, display_name, acuity from diagnoses")}
        self.finding_names = dict(con.execute("select finding_id, display_name from clinical_findings"))
        self.support: dict[int, set[int]] = defaultdict(set)
        self.rules_out: dict[int, set[int]] = defaultdict(set)
        for did, fid, rel in con.execute("select diagnosis_id, finding_id, relationship from diagnosis_findings"):
            if rel in SUPPORT_RELATIONS:
                self.support[did].add(fid)
            elif rel == "rules_out":
                self.rules_out[did].add(fid)
        self.question_dx: dict[int, list[tuple[int, str]]] = defaultdict(list)
        for qid, did, role in con.execute("select question_id, diagnosis_id, role from question_diagnoses"):
            self.question_dx[qid].append((did, role))
        self.question_findings: dict[int, set[int]] = defaultdict(set)
        for qid, fid in con.execute("select question_id, finding_id from question_findings where present = 1"):
            self.question_findings[qid].add(fid)

    def present_findings(self, patient: Patient) -> set[int]:
        return {f for enc in patient.encounters for q in enc.question_ids for f in self.question_findings[q]}

    def decoy_candidates(self, patient: Patient) -> list[Decoy]:
        """Board-exam distractors for this patient's questions that are plausible but wrong.

        Plausible: >= 2 of the decoy's supporting findings are present in the chart, and the code is a
        disease that fits the patient's age/sex. Wrong: not a true diagnosis, and its ICD-10 category is
        neither a true category nor chart-neutral (so the official scorer would count it as an error).
        Ranked: not already mentioned in the chart first (clean baseline), then most supporting findings.
        """
        true_ids = {d["diagnosis_id"] for d in patient.true_codes}
        blocked_cats = {d["icd10"][:3] for d in patient.true_codes if d.get("icd10")} | patient.neutral_categories
        true_names = {d["display_name"].lower() for d in patient.true_codes}
        present = self.present_findings(patient)
        chart = render_chart(patient.encounters).lower()

        distractors = {did for enc in patient.encounters for q in enc.question_ids
                       for did, role in self.question_dx[q] if role == "distractor"}
        out = []
        for did in distractors:
            icd, name, acuity = self.diagnoses.get(did, (None, None, None))
            if not icd or not ICD10_RE.match(icd) or did in true_ids or icd[:3] in blocked_cats:
                continue
            if _too_similar(name, true_names) or NON_DIAGNOSIS.search(name) or not _fits_patient(icd, patient):
                continue
            support = len(self.support[did] & present)
            if support < 2:
                continue
            natural = sorted(self.finding_names[f] for f in self.rules_out[did] & present)
            out.append(Decoy(did, icd, name, acuity or "unspecified", support, natural, name.lower() in chart))
        return sorted(out, key=lambda d: (d.mentioned_in_chart, -d.support_present, d.diagnosis_id))
