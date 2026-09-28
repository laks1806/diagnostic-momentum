"""Diagnostic Momentum demo: explore planted charts and what the AI coder and auditor did with them.

  streamlit run app.py
Reads saved results only (no API calls).
"""
from __future__ import annotations

import html
import json
import re

import streamlit as st

from src import adjudicate
from src.config import DATA, RESULTS
from src.kg import Decoy
from src.load import HIDDEN_SECTIONS, connect, load_patient
from src.plant import CONDITIONS, HEADER, plant

st.set_page_config(page_title="Diagnostic Momentum", page_icon="🩺", layout="wide")

VERSION_LABELS = {
    "clean": "Clean (nothing planted)",
    "d1_late_nocontra": "Copied once",
    "d3_late_nocontra": "Copied 3×",
    "d3_late_contra": "Copied 3× + ruled out",
    "d3_early_nocontra": "Early, then dropped",
}
MODEL = "gpt-oss-120b"
TYPE = {"outpatient": "Clinic", "ed": "Emergency", "inpatient": "Inpatient", "icu": "ICU",
        "telehealth": "Telehealth", "procedure": "Procedure", "follow_up": "Follow-up"}

st.markdown("""
<style>
.planted { background:#F8E08E; color:#4F3B00; border-radius:3px; padding:0 4px; }
.plist { font-family: ui-monospace, Consolas, monospace; font-size:0.86rem; line-height:1.55; }
.note { border-left:3px solid #B88A00; padding:2px 0 2px 10px; margin:6px 0; font-size:0.92rem; }
.tag { font-size:0.72rem; font-weight:600; letter-spacing:0.04em; text-transform:uppercase; border-radius:999px;
       padding:1px 8px; margin-left:6px; white-space:nowrap; }
.t-true { background:#DFF1E7; color:#23714F; } .t-fake { background:#F8E1DE; color:#A8322A; }
.t-hist { background:#E8ECEC; color:#56666D; } .t-other { background:#E8ECEC; color:#56666D; }
.t-kept { background:#E3EEF2; color:#1D5C74; } .t-dropped { background:#F3E9D6; color:#7A5A12; }
.dx { padding:6px 0; border-bottom:1px solid rgba(128,128,128,0.2); }
.ev { font-size:0.85rem; opacity:0.8; margin-top:2px; }
</style>
""", unsafe_allow_html=True)


# ---------- data ----------
@st.cache_resource
def db():
    return connect()


@st.cache_data
def pilot() -> list[dict]:
    return json.loads((DATA / "pilot_patients.json").read_text())


@st.cache_data
def runs() -> dict:
    out = {}
    path = RESULTS / "runs.jsonl"
    if path.exists():
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            out[(r["model"], r["system"], r["patient_id"], r["condition"])] = r
    return out


@st.cache_data
def summary() -> dict | None:
    p = RESULTS / "summary.json"
    return json.loads(p.read_text()) if p.exists() else None


@st.cache_resource
def patient(pid: int):
    return load_patient(db(), pid)


def planted_encounters(pid: int, version: str):
    row = next(r for r in pilot() if r["patient_id"] == pid)
    decoy = Decoy(**row["decoy"])
    cond = next(c for c in CONDITIONS if c.name == version)
    encs, _manifest = plant(patient(pid), decoy, cond)
    return encs, decoy


def problem_lines(sections) -> list[str]:
    txt = next((t for s, t in sections if s == "pmh"), "")
    lines = txt.split("\n")
    if HEADER not in lines:
        return []
    i, out = lines.index(HEADER) + 1, []
    while i < len(lines) and lines[i].startswith("- "):
        out.append(lines[i][2:])
        i += 1
    return out


# ---------- diagnosis tagging ----------
def classify(entry: dict, p, decoy: Decoy, adj: dict) -> tuple[str, str]:
    """(css class, label) for one AI diagnosis."""
    hit, _ = adjudicate.fooled({"active_diagnoses": [entry]}, decoy.icd10, decoy.name, adj)
    if hit:
        return "t-fake", "Planted fake"
    cat = adjudicate.norm(entry.get("icd10", ""))[:3]
    if cat in {adjudicate.norm(d["icd10"])[:3] for d in p.true_codes}:
        return "t-true", "True diagnosis"
    if cat in p.neutral_categories:
        return "t-hist", "Old history · not scored"
    return "t-other", "Not in answer key"


def dx_block(entries: list[dict], p, decoy, adj, verdicts: dict | None = None) -> str:
    parts = []
    for i, d in enumerate(entries, 1):
        cls, label = classify(d, p, decoy, adj)
        extra = ""
        if verdicts is not None:
            v = verdicts.get(i, {})
            verdict = str(v.get("verdict", "no verdict")).lower()
            kept = verdict == "supported"
            extra = f'<span class="tag {"t-kept" if kept else "t-dropped"}">{"kept" if kept else verdict.replace("_", " ")}</span>'
            if v.get("evidence"):
                extra += f'<div class="ev">“{html.escape(str(v["evidence"])[:220])}” <i>{html.escape(str(v.get("encounter_date", "")))}</i></div>'
        parts.append(f'<div class="dx"><b>{html.escape(d.get("icd10", ""))}</b> {html.escape(d.get("name", ""))}'
                     f'<span class="tag {cls}">{label}</span>{extra}</div>')
    return "".join(parts) or "<i>No diagnoses returned.</i>"


# ---------- UI ----------
st.title("Diagnostic Momentum")
st.caption("When a wrong diagnosis is copied forward through a patient's problem lists, does an AI coder bill it? "
           "Lakshita Singh · Synthetic Hospital v1.3 · 50 pilot patients · gpt-oss-120b")

tab_results, tab_explore, tab_how = st.tabs(["Results", "Patient explorer", "How it works"])

with tab_results:
    s = summary()
    if not s:
        st.info("No results yet. Run `python -m src.analyze results/runs.jsonl`.")
    else:
        rate = {(t["system"], t["version"]): t for t in s["table"]}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Billed the fake, clean charts", f"{rate[('S1_direct', 'clean')]['rate']:.0%}")
        c2.metric("Billed the fake, copied once", f"{rate[('S1_direct', 'd1_late_nocontra')]['rate']:.0%}")
        c3.metric("Even when the chart says ruled out", f"{rate[('S1_direct', 'd3_late_contra')]['rate']:.0%}")
        if ("S3_verify", "d3_late_nocontra") in rate:
            c4.metric("With the evidence auditor (S3), copied 3×",
                      f"{rate[('S3_verify', 'd3_late_nocontra')]['rate']:.0%}",
                      delta=f"{(rate[('S3_verify', 'd3_late_nocontra')]['rate'] - rate[('S1_direct', 'd3_late_nocontra')]['rate']) * 100:+.0f} pts vs S1",
                      delta_color="inverse")
        st.image(str(RESULTS / "fig_propagation.png"), width="stretch")
        st.markdown((RESULTS / "summary.md").read_text(encoding="utf-8").split("\n", 1)[1])
        st.caption(f"{s['rows']} model calls · total cost ${s['cost_usd']:.2f} · parse failures {s['parse_failures']}")

with tab_explore:
    pts = pilot()
    labels = {r["patient_id"]: f"#{r['patient_id']} · {r['n_encounters']} visits · fake: {r['decoy']['name']}" for r in pts}
    col_a, col_b = st.columns([2, 2])
    ids = [r["patient_id"] for r in pts]
    pid = col_a.selectbox("Patient", ids, format_func=labels.get, key="pid",
                          index=ids.index(1992) if 1992 in ids else 0)  # showcase: coder fooled, auditor catches it
    version = col_b.radio("Chart version", list(VERSION_LABELS), format_func=VERSION_LABELS.get,
                          horizontal=True, index=2, key="version")
    p = patient(pid)
    encs, decoy = planted_encounters(pid, version)
    clean_lines = [set(problem_lines(e.sections)) for e in p.encounters]
    adj = adjudicate.load()

    st.markdown(f"**{'Man' if p.sex == 'M' else 'Woman'}, {p.age}** · planted fake: "
                f"<span class='planted'>{html.escape(decoy.name)} ({decoy.icd10})</span> · "
                f"answer key: {html.escape('; '.join(d['display_name'] for d in p.true_codes))}",
                unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("The chart the AI reads")
        for k, e in enumerate(encs):
            lines = problem_lines(e.sections)
            plist = "".join(
                f'<div class="{"planted" if ln not in clean_lines[k] else ""}">- {html.escape(ln)}</div>' for ln in lines
            ) or "<i>No problem list in this note</i>"
            hpi = next((t for s_, t in e.sections if s_ == "hpi"), "")
            m = re.search(r"Of note, .*? ruled out on further workup\.", hpi)
            note = f'<div class="note"><b>Added:</b> {html.escape(m.group())}</div>' if m else ""
            with st.container(border=True):
                st.markdown(f"**{e.date}** · {TYPE.get(e.type, e.type)} · {html.escape(e.chief_complaint)}"
                            f'<div class="plist"><b>Active Problem List:</b>{plist}</div>{note}',
                            unsafe_allow_html=True)
                with st.expander("Full note"):
                    for s_type, text in e.sections:
                        if s_type not in HIDDEN_SECTIONS:
                            st.markdown(f"**{s_type.upper().replace('_', ' ')}**  \n{text}")

    with right:
        R = runs()
        s1 = R.get((MODEL, "S1_direct", pid, version))
        s3 = R.get((MODEL, "S3_verify", pid, version))
        st.subheader("AI coder (S1)")
        if s1:
            hit, _ = adjudicate.fooled(s1["prediction"], decoy.icd10, decoy.name, adj)
            (st.error if hit else st.success)(
                f"{'Billed the planted fake' if hit else 'Did not bill the fake'} · accuracy (wF1n) {s1['wf1n']:.2f}")
            st.markdown(dx_block(s1["prediction"]["active_diagnoses"] + s1["prediction"]["chronic_conditions"],
                                 p, decoy, adj), unsafe_allow_html=True)
        else:
            st.info("No saved S1 result for this chart.")

        st.subheader("Evidence auditor (S3)")
        if s3:
            hit, _ = adjudicate.fooled(s3["prediction"], decoy.icd10, decoy.name, adj)
            (st.error if hit else st.success)(
                f"{'Fake still billed' if hit else 'Fake not billed'} after audit · accuracy (wF1n) {s3['wf1n']:.2f}")
            verdicts = {int(v["id"]): v for v in s3.get("audit_verdicts") or [] if str(v.get("id", "")).isdigit()}
            coder = s3["coder_prediction"]
            st.markdown(dx_block(coder["active_diagnoses"] + coder["chronic_conditions"], p, decoy, adj, verdicts),
                        unsafe_allow_html=True)
        else:
            st.info("The auditor was run on the clean, copied 3× and copied 3× + ruled out versions.")

with tab_how:
    st.markdown("""
1. **Start from Synthetic Hospital** (CMU, 2026): 1,268 synthetic patients with multi-visit charts and a verified answer key.
2. **Pick one believable wrong diagnosis per patient:** a tempting wrong answer from the exam question the visit was built
   from, with at least two matching findings in the chart, fitting the patient's age and sex.
3. **Plant it** as one line in the Active Problem List, in five versions: clean, copied once, copied 3×,
   copied 3× plus a note saying it was ruled out, and early-then-dropped. Nothing else in the chart changes.
4. **Ask the AI coder** for the patient's diagnoses with ICD-10 codes (S1: the benchmark's own prompt;
   S2: plus a warning that problem lists may be wrong).
5. **S3 adds an evidence auditor:** a second call checks each coded diagnosis against the visit notes and keeps it only if
   it can quote clinical evidence. Problem-list lines alone don't count.
6. **Score** each answer against the answer key and check whether the fake was billed. Near-matches are decided once per
   diagnosis pair in `data/adjudication.json`, independent of chart version.
""")
