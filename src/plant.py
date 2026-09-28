"""Plant a decoy diagnosis into carried-forward problem lists and build every experimental condition.

Run:  python -m src.plant            (writes data/pilot_patients.json and data/charts.jsonl)
"""
from __future__ import annotations

import copy
import itertools
import json
import random
import re
from dataclasses import asdict, dataclass

from src.config import DATA, MIN_ENCOUNTERS, PILOT_SIZE, SEED
from src.kg import KG, Decoy
from src.load import Encounter, Patient, connect, eligible_patient_ids, load_patient, render_chart

HEADER = "Active Problem List:"
DATED = re.compile(r"\(diagnosed (\d{4}-\d{2}-\d{2})\)")


@dataclass(frozen=True)
class Condition:
    name: str
    dose: int                 # number of notes whose problem list carries the decoy
    recency: str | None       # "early": planted at visit 0, later dropped; "late": persists into the latest note
    contradiction: bool       # latest note states the decoy was ruled out


ALL_CONDITIONS = [Condition("clean", 0, None, False)] + [
    Condition(f"d{dose}_{rec}_{'contra' if con else 'nocontra'}", dose, rec, con)
    for dose, rec, con in itertools.product((1, 3), ("early", "late"), (False, True))
]
# Budget design: the 5 versions that answer RQ1-RQ4 (full 9-cell grid kept above for a later scale-up).
CONDITIONS = [c for c in ALL_CONDITIONS if c.name in
              ("clean", "d1_late_nocontra", "d3_late_nocontra", "d3_late_contra", "d3_early_nocontra")]


def _insert_problem(pmh: str, line: str, date: str) -> str:
    """Insert `line` into the Active Problem List, keeping dated entries in date order."""
    lines = pmh.split("\n")
    if HEADER not in lines:
        return f"{HEADER}\n{line}\n\n{pmh}".rstrip()
    i = lines.index(HEADER) + 1
    pos = i
    while pos < len(lines) and lines[pos].startswith("- "):
        m = DATED.search(lines[pos])
        if not m or m.group(1) > date:
            break
        pos += 1
    lines.insert(pos, line)
    return "\n".join(lines)


def _set_section(enc: Encounter, sec_type: str, fn, fallback_after: str = "hpi") -> None:
    """Apply fn to a section's text, creating the section if the note lacks it."""
    for idx, (t, text) in enumerate(enc.sections):
        if t == sec_type:
            enc.sections[idx] = (t, fn(text))
            return
    after = next((i for i, (t, _) in enumerate(enc.sections) if t == fallback_after), 0)
    enc.sections.insert(after + 1, (sec_type, fn("").strip()))


def plant(patient: Patient, decoy: Decoy, cond: Condition) -> tuple[list[Encounter], dict]:
    encs = copy.deepcopy(patient.encounters)
    n = len(encs)
    manifest = {"patient_id": patient.patient_id, "gt_id": patient.gt_id, "condition": cond.name,
                "dose": cond.dose, "recency": cond.recency, "contradiction": cond.contradiction,
                "decoy": asdict(decoy)}
    if cond.dose == 0:
        return encs, manifest

    if cond.recency == "early":
        diagnosed_at = 0
        copies = list(range(1, 1 + cond.dose))
    else:
        diagnosed_at = n - 1 - cond.dose
        copies = list(range(n - cond.dose, n))
    date = encs[diagnosed_at].date
    line = f"- {decoy.name} (diagnosed {date})"
    for k in copies:
        _set_section(encs[k], "pmh", lambda t: _insert_problem(t, line, date))

    manifest.update(diagnosed_visit=diagnosed_at, diagnosed_date=date, copy_visits=copies)
    if cond.contradiction:
        sentence = f"Of note, {decoy.name.lower()} was considered earlier but has since been ruled out on further workup."
        target = "hpi" if any(t == "hpi" for t, _ in encs[-1].sections) else "pmh"
        _set_section(encs[-1], target, lambda t: f"{t.rstrip()} {sentence}".strip())
        manifest.update(contradiction_visit=n - 1, contradiction_text=sentence)
    return encs, manifest


def select_pilot(con, kg: KG) -> list[tuple[Patient, Decoy]]:
    chosen = []
    for pid in eligible_patient_ids(con, "public", MIN_ENCOUNTERS):
        p = load_patient(con, pid)
        cands = kg.decoy_candidates(p)
        if cands:
            chosen.append((p, cands[0]))
    rng = random.Random(SEED)
    return sorted(rng.sample(chosen, min(PILOT_SIZE, len(chosen))), key=lambda x: x[0].patient_id)


def main() -> None:
    con = connect()
    kg = KG(con)
    pilot = select_pilot(con, kg)
    DATA.mkdir(exist_ok=True)
    (DATA / "pilot_patients.json").write_text(json.dumps(
        [{"patient_id": p.patient_id, "gt_id": p.gt_id, "n_encounters": len(p.encounters), "decoy": asdict(d)}
         for p, d in pilot], indent=1))
    with open(DATA / "charts.jsonl", "w", encoding="utf-8") as f:
        for p, d in pilot:
            for cond in CONDITIONS:
                encs, manifest = plant(p, d, cond)
                f.write(json.dumps({**manifest, "chart_text": render_chart(encs)}) + "\n")
    natural = sum(1 for _, d in pilot if d.natural_rules_out)
    print(f"pilot patients: {len(pilot)} | conditions: {len(CONDITIONS)} | charts: {len(pilot) * len(CONDITIONS)}")
    print(f"decoys with a natural KG rules-out finding already in the chart: {natural}/{len(pilot)}")


if __name__ == "__main__":
    main()
