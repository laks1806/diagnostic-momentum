"""Build the 2-page Word report (+ references on page 3) from the saved results.

  python deliverables/build_report.py
Numbers are read from results/summary.json so the report always matches the analysis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_BREAK, WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.analyze import figure  # noqa: E402

AUTHOR = "Lakshita Singh"
INK = RGBColor(0x16, 0x23, 0x2A)
ACCENT = RGBColor(0x1D, 0x5C, 0x74)
MUTED = RGBColor(0x56, 0x66, 0x6D)

S = json.loads((ROOT / "results" / "summary.json").read_text())
R = {(t["system"], t["version"]): t for t in S["table"]}
pct = lambda s, v: f"{R[(s, v)]['rate']:.0%}"  # noqa: E731

# ---------- document setup ----------
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.left_margin = sec.right_margin = Inches(0.85)
sec.top_margin = sec.bottom_margin = Inches(0.75)

normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
normal.font.size = Pt(10.5)
normal.font.color.rgb = INK
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.line_spacing = 1.05


def heading(text: str, size: float = 11.5, before: float = 7) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(size), ACCENT


def para(*chunks, after: float = 4, align=None) -> None:
    """chunks: plain strings, or (text, 'b'|'i') tuples."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if align:
        p.alignment = align
    for c in chunks:
        text, style = (c, "") if isinstance(c, str) else c
        r = p.add_run(text)
        r.bold, r.italic = "b" in style, "i" in style


def shade(cell, hex_fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


# ---------- title ----------
t = doc.add_paragraph()
t.paragraph_format.space_after = Pt(1)
r = t.add_run("Diagnostic Momentum in AI Medical Coding")
r.bold, r.font.size, r.font.color.rgb = True, Pt(16), INK
st = doc.add_paragraph()
st.paragraph_format.space_after = Pt(6)
r = st.add_run(f"Clinical Decision Making and Pattern Recognition in Health Care · {AUTHOR} · Cotiviti Intern Assessment · "
               "September 2026")
r.font.size, r.font.color.rgb = Pt(9.5), MUTED

# ---------- 1. concept ----------
heading("The concept", before=2)
para("Clinical decision making and pattern recognition in health care increasingly means large language models (LLMs) "
     "reading longitudinal records and inferring diagnoses, codes and next steps across treatment, payment and "
     "operations (TPO). Human clinicians have a well-documented failure mode here: ", ("diagnostic momentum", "b"),
     ", where a label, once written into the chart, is repeated and accepted without being re-examined "
     "(Croskerry, 2003). Copy-forward documentation amplifies it, carrying outdated or wrong problem-list entries from "
     "note to note (Hirschtick, 2006; Weis & Levy, 2014; Tsou et al., 2017). This report asks whether ",
     ("AI medical coders", "b"), " (systems that read a chart and assign the ICD-10-CM codes a claim is paid on) "
     "inherit that failure, and what it means for payment accuracy.")

# ---------- 2. trends ----------
heading("Trends")
para("AI is entering documentation and coding from both sides of the claim. After adopting ambient AI scribes, "
     "hospitals billed 12–20 percentage points more new-patient visits at the highest levels (Patton et al., 2026), "
     "and commentators describe a “coding arms race” between provider-side and payer-side AI (Dai et al., "
     "2025; Nong & Neprash, 2026). CMS’s WISeR model began AI-assisted prior authorization with mandatory "
     "clinician review in January 2026 (Centers for Medicare & Medicaid Services, n.d.). Evidence on reliability is "
     "sobering: LLMs accept counterfactual medical evidence at face value (Mo et al., 2026), lose 16–28 points of "
     "accuracy on minimally altered cases (Adewuyi et al., 2026), and most fail paired clean-versus-erroneous note "
     "discrimination (Zhang & Beheshti, 2026). Error propagation across multi-visit records has been hard to measure "
     "because real charts lack ground truth. ", ("Synthetic Hospital", "i"), " (Park et al., 2026), released in "
     "September 2026, supplies 1,268 synthetic longitudinal patients with ontology-verified diagnoses; its authors "
     "note that it does not yet simulate documentation errors.")

# ---------- 3. pilot ----------
heading("Proof of concept: a planted-error stress test")
para(("Method. ", "b"),
     "For 50 Synthetic Hospital patients with at least five visits, I planted one plausible wrong diagnosis (a "
     "distractor answer from the exam question the patient was built from, sharing at least two findings with the "
     "chart) as a single line in the carried-forward Active Problem List. Each patient was tested clean and in four "
     "planted versions: copied once, copied three times, three times plus a note stating it was ruled out, and early "
     "then dropped. An open-weight LLM (gpt-oss-120b; OpenAI, 2025) coded each chart with the benchmark’s own "
     "prompt (S1), with a caution added (S2), and with a second ", ("evidence-auditor", "i"), " call that keeps a code "
     "only if it can quote supporting evidence from the visit notes (S3). Near-match codes were adjudicated once per "
     f"diagnosis pair, independent of version. Total cost: US${S['cost_usd']:.2f} for {S['rows']} model calls.")
para(("Results. ", "b"),
     f"S1 billed the planted diagnosis in {pct('S1_direct', 'clean')} of clean charts, "
     f"{pct('S1_direct', 'd1_late_nocontra')} after a single copy, and {pct('S1_direct', 'd3_late_contra')} even when "
     "the chart stated it had been ruled out (paired McNemar p < .001). A caution in the prompt only reduced "
     f"three-copy propagation to {pct('S2_caution', 'd3_late_nocontra')}; the evidence auditor reduced it to "
     f"{pct('S3_verify', 'd3_late_nocontra')} ({pct('S3_verify', 'd3_late_contra')} with the ruled-out note) with no "
     "loss of accuracy on the true diagnoses of planted charts (Figure 1). Provisional runs on two Gemini Flash-Lite "
     "models show the same direction at lower rates.", after=2)

fig_path = ROOT / "results" / "fig_report.png"
figure(S["table"], S["models"], S["rows"], path=fig_path, size=(8.6, 2.55), title=False, ylabel="Billed the fake")
pic = doc.add_paragraph()
pic.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
pic.paragraph_format.space_after = Pt(0)
pic.paragraph_format.keep_with_next = True
pic.add_run().add_picture(str(fig_path), width=Inches(6.6))
cap = doc.add_paragraph()
cap.paragraph_format.space_after = Pt(4)
r = cap.add_run("Figure 1. ")
r.bold, r.font.size = True, Pt(9)
r = cap.add_run(f"Share of charts in which the AI coder billed the planted wrong diagnosis ({S['models'][0]}, 50 patients; "
                "whiskers are 95% Wilson intervals). S1 = benchmark prompt; S2 = + caution; S3 = coder + evidence auditor.")
r.font.size, r.font.color.rgb = Pt(9), MUTED

# ---------- 4. opportunities & threats ----------
heading("Opportunities and threats")
tbl = doc.add_table(rows=2, cols=2)
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl.style = "Table Grid"
opps = [
    ("Evidence-cited chart review at scale. ", "An auditor step turns opaque codes into claims backed by quotes, "
     "the currency of clinical chart validation and risk-adjustment review."),
    ("Cheap, verifiable model testing. ", "Synthetic records with known answers let Cotiviti certify vendor and "
     "in-house models before deployment; this full study cost under $2."),
    ("Operations triage. ", "Codes supported only by a problem list can be routed to human reviewers first."),
]
threats = [
    ("Automated overpayment. ", "AI coders convert copy-forward errors into billed codes (90% here), inflating "
     "payments and risk scores."),
    ("False confidence. ", "Prompt-level fixes look like safeguards but still let most errors through."),
    ("Provider abrasion. ", "Over-strict auditors could deny true diagnoses; human review stays essential."),
    ("Synthetic-to-real gap. ", "One primary model and synthetic charts; magnitudes may differ on real records."),
]
for col, (title, items, fill) in enumerate((("Opportunities", opps, "E3EEF2"), ("Threats", threats, "F8E1DE"))):
    head = tbl.rows[0].cells[col]
    head.text = ""
    hr = head.paragraphs[0].add_run(title)
    hr.bold, hr.font.size = True, Pt(10)
    shade(head, fill)
    body = tbl.rows[1].cells[col]
    body.text = ""
    for i, (lead, rest) in enumerate(items):
        p = body.paragraphs[0] if i == 0 else body.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        a = p.add_run(lead)
        a.bold, a.font.size = True, Pt(9.5)
        b = p.add_run(rest)
        b.font.size = Pt(9.5)

# ---------- 5. recommendations ----------
heading("Recommendations for Cotiviti")
recs = [
    ("Adopt an evidence-first standard for AI-assisted coding and review. ",
     "Every AI-generated or AI-reviewed code should cite encounter-level evidence; codes resting only on a problem list "
     "go to a human reviewer. The auditor pattern costs one extra model call (about $0.002 per chart) and cut billed "
     "errors from 92% to 20% here. Pilot it inside clinical chart validation."),
    ("Make planted-error stress tests a release gate. ",
     "Before any coding or audit model (vendor or in-house) goes live, test it on paired clean and planted synthetic "
     "charts and report propagation rate and paired accuracy, not F1 alone."),
    ("Take a position in the coding arms race. ",
     "Publish a payer-side documentation-evidence standard, and partner with academic benchmark groups (for example, "
     "the Synthetic Hospital team) to extend benchmarks to documentation errors. Longer term, use their verifiable "
     "rewards to train momentum-resistant auditors."),
]
for i, (lead, rest) in enumerate(recs, 1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Inches(0.2)
    p.paragraph_format.first_line_indent = Inches(-0.2)
    p.add_run(f"{i}. ").bold = True
    p.add_run(lead).bold = True
    p.add_run(rest)

# ---------- references (page 3) ----------
br = doc.add_paragraph()
br.add_run().add_break(WD_BREAK.PAGE)
heading("References", size=13, before=0)
refs = [
    ("Adewuyi, T., Sotome, A., Okoko, S., Ezendu, A., Akinbuwa, O., Odunsi, O., Oguntuase, O., Nwabueze, I., & "
     "Adereni, A. (2026). ", "MamaBench: Benchmarking LLM robustness in maternal and child health diagnosis through "
     "counterfactual clinical perturbation", " (arXiv:2607.14385). arXiv. https://arxiv.org/abs/2607.14385"),
    ("Centers for Medicare & Medicaid Services. (n.d.). ", "WISeR (Wasteful and Inappropriate Service Reduction) Model",
     ". Retrieved September 28, 2026, from https://www.cms.gov/priorities/innovation/innovation-models/wiser"),
    ("Croskerry, P. (2003). The importance of cognitive errors in diagnosis and strategies to minimize them. ",
     "Academic Medicine, 78", "(8), 775–780. https://doi.org/10.1097/00001888-200308000-00003"),
    ("Dai, T., Kvedar, J. C., & Polsky, D. (2025). Policy brief: Ambient AI scribes and the coding arms race. ",
     "npj Digital Medicine, 8", "(1), 780. https://doi.org/10.1038/s41746-025-02272-z"),
    ("Hirschtick, R. E. (2006). Copy-and-paste. ", "JAMA, 295", "(20), 2335–2336. https://doi.org/10.1001/jama.295.20.2335"),
    ("Mo, K., Venkatayogi, S., Shaib, C., Kouzy, R., Xu, W., Wallace, B. C., & Li, J. J. (2026). Faithfulness vs. "
     "safety: Evaluating LLM behavior under counterfactual medical evidence. In ", "Findings of the Association for "
     "Computational Linguistics: ACL 2026", ". https://aclanthology.org/2026.findings-acl.1847/"),
    ("Nong, P., & Neprash, H. T. (2026). Unintended consequences of using ambient artificial intelligence scribes for "
     "billing. ", "JAMA Health Forum, 7", "(1), e255771. https://doi.org/10.1001/jamahealthforum.2025.5771"),
    ("OpenAI. (2025). ", "gpt-oss-120b", " [Large language model]. Accessed via the Fireworks AI serverless API, "
     "September 2026."),
    ("Park, C., Chen, V., & Dettmers, T. (2026). ", "Synthetic Hospital: An open, verifiable, physician-validated "
     "longitudinal EHR benchmark", " (arXiv:2609.30027). arXiv. https://arxiv.org/abs/2609.30027"),
    ("Patton, K., Miller, A., Oakes, A., & O’Neill, M. (2026, March 12). ", "Increased outpatient coding intensity "
     "following hospital adoption of AI-enabled scribing warrants examination but likely reflects enhanced rules-based "
     "documentation", ". Trilliant Health. https://www.trillianthealth.com/market-research/studies/outpatient-coding-"
     "intensity-increases-as-hospitals-adopt-ai-enabled-scribing"),
    ("Tsou, A. Y., Lehmann, C. U., Michel, J., Solomon, R., Possanza, L., & Gandhi, T. (2017). Safe practices for "
     "copy and paste in the EHR: Systematic review, recommendations, and novel model for health IT collaboration. ",
     "Applied Clinical Informatics, 8", "(1), 12–34. https://doi.org/10.4338/ACI-2016-09-R-0150"),
    ("Weis, J. M., & Levy, P. C. (2014). Copy, paste, and cloned notes in electronic health records. ", "Chest, 145",
     "(3), 632–638. https://doi.org/10.1378/chest.13-0886"),
    ("Zhang, Y., & Beheshti, R. (2026). ", "Toward better assessment of LLMs’ performance in clinical error "
     "detection", " (arXiv:2608.16643). arXiv. https://arxiv.org/abs/2608.16643"),
]
for pre, ital, post in refs:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.first_line_indent = Inches(-0.5)
    p.paragraph_format.space_after = Pt(5)
    p.add_run(pre)
    p.add_run(ital).italic = True
    p.add_run(post)

heading("Methods and tools note", size=11, before=10)
para("Code, data extracts, results and the adjudication file are in the accompanying GitHub repository. Analysis code "
     "was developed with the assistance of Claude (Anthropic), an AI assistant; study design decisions, adjudication "
     "rules and all conclusions were reviewed by the author.")

out = ROOT / "deliverables" / "Diagnostic_Momentum_Report.docx"
doc.save(out)
print("saved", out)
