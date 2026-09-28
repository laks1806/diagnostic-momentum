"""Load Synthetic Hospital patients as longitudinal timelines (read-only SQLite)."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from dataclasses import dataclass, field

from src.config import DATA, DB_PATH, SH_ROOT

HIDDEN_SECTIONS = {"assessment", "plan"}  # stripped, as in the paper's protocol


@dataclass
class Encounter:
    encounter_id: int
    order: int
    date: str
    type: str
    department: str
    chief_complaint: str
    question_ids: list[int]
    sections: list[tuple[str, str]]  # (section_type, text) in section order


@dataclass
class Patient:
    patient_id: int
    gt_id: int
    split: str
    ground_truth: dict
    profile: dict
    age: int
    sex: str
    encounters: list[Encounter]
    neutral_categories: set[str] = field(default_factory=set)

    @property
    def true_codes(self) -> list[dict]:
        gt = self.ground_truth
        return [d for d in gt["active_diagnoses"] + gt["chronic_conditions"]
                if not d.get("excluded_nondiagnostic")]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    # The chart-neutral mapper also reads ICD-10 titles from `terminology_codes`, which the release
    # ships empty/absent (licensing). An empty temp table reproduces that state without touching the DB.
    con.execute("create temp table if not exists terminology_codes(system text, code text, display text)")
    return con


def _neutral_sets(con: sqlite3.Connection) -> dict[int, set[str]]:
    """Chart-neutral ICD-10 categories per patient, via the benchmark's own script (cached to disk)."""
    cache = DATA / "chart_neutral_sets.json"
    if cache.exists():
        return {int(k): set(v) for k, v in json.loads(cache.read_text()).items()}
    spec = importlib.util.spec_from_file_location("chart_neutral_sets", SH_ROOT / "scripts" / "chart_neutral_sets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sets, _how, _unmapped = module.neutral_sets(con.cursor())
    DATA.mkdir(exist_ok=True)
    cache.write_text(json.dumps({str(k): sorted(v) for k, v in sets.items()}))
    return {int(k): set(v) for k, v in sets.items()}


def eligible_patient_ids(con: sqlite3.Connection, split: str = "public", min_encounters: int = 5) -> list[int]:
    rows = con.execute(
        """select g.patient_id from benchmark_ground_truth g
           join longitudinal_patients p on p.patient_id = g.patient_id
           where g.task = 'patient_diagnosis' and g.is_diagnostic and g.split = ? and p.num_encounters >= ?
           order by g.patient_id""",
        (split, min_encounters),
    ).fetchall()
    return [r[0] for r in rows]


def load_patient(con: sqlite3.Connection, patient_id: int) -> Patient:
    gt_id, split, gt_json = con.execute(
        "select gt_id, split, ground_truth from benchmark_ground_truth where task='patient_diagnosis' and patient_id=?",
        (patient_id,),
    ).fetchone()
    profile_json, age, sex = con.execute(
        "select profile, age, sex from longitudinal_patients where patient_id=?", (patient_id,)).fetchone()

    encounters = []
    for eid, order, date, etype, dept, cc, sq in con.execute(
        """select encounter_id, encounter_order, encounter_date, encounter_type, department, chief_complaint,
                  source_question_ids
           from longitudinal_encounters where patient_id=? order by encounter_order""",
        (patient_id,),
    ).fetchall():
        sections = con.execute(
            "select section_type, section_text from encounter_ehr_sections where encounter_id=? order by section_order",
            (eid,),
        ).fetchall()
        encounters.append(Encounter(eid, order, date, etype, dept or "", cc or "", json.loads(sq or "[]"), sections))

    return Patient(
        patient_id=patient_id,
        gt_id=gt_id,
        split=split,
        ground_truth=json.loads(gt_json),
        profile=json.loads(profile_json or "{}"),
        age=age,
        sex=sex,
        encounters=encounters,
        neutral_categories=_neutral_sets(con).get(patient_id, set()),
    )


def render_chart(encounters: list[Encounter]) -> str:
    """Longitudinal chart text in the same layout as the benchmark's patient_diagnosis inputs."""
    parts = []
    for enc in encounters:
        cc = f" — {enc.chief_complaint}" if enc.chief_complaint else ""
        parts.append(f"\n{'=' * 60}\nENCOUNTER: {enc.date} ({enc.type}){cc}\n{'=' * 60}")
        for sec_type, text in enc.sections:
            if sec_type in HIDDEN_SECTIONS:
                continue
            parts.append(f"[{sec_type.upper().replace('_', ' ')}]\n{text}")
    return "\n\n".join(parts)
