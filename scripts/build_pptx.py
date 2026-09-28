"""Build the PowerPoint deck in the same design as docs/slides.html, with the video script as speaker notes.

  python deliverables/build_pptx.py
Charts, tables and the pipeline diagram are native PowerPoint objects, so they stay editable.
Fonts: Georgia (headings), Segoe UI (body), Consolas (chart text in the problem-list mock-up); all ship with Windows.
"""
from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
AUTHOR = "Lakshita Singh"
import sys  # noqa: E402

# Speaker notes are added only with --notes and a local scripts/script_notes.json (kept out of the repo).
_notes = ROOT / "scripts" / "script_notes.json"
SCRIPT = (json.loads(_notes.read_text(encoding="utf-8"))
          if "--notes" in sys.argv and _notes.exists() else {})

HEX = lambda h: RGBColor.from_string(h)  # noqa: E731
BG, INK, MUTED, LINE = HEX("FFFFFF"), HEX("16232A"), HEX("56666D"), HEX("D3DBDA")
ACCENT, ACCENT_SOFT = HEX("1D5C74"), HEX("E3EEF2")
PLANT_BG, PLANT_INK, PLANT_STROKE = HEX("F8E08E"), HEX("4F3B00"), HEX("B88A00")
S1, S2, S3 = HEX("2A78D6"), HEX("EB6834"), HEX("1BAF7A")
BAD, BAD_SOFT, GRID = HEX("A8322A"), HEX("F8E1DE"), HEX("E1E0D9")
SERIF, SANS, MONO = "Georgia", "Segoe UI", "Consolas"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
LEFT, TOP, WIDTH = Inches(0.8), Inches(0.55), Inches(11.73)
TOTAL = 12


# ---------------- helpers ----------------
def text(slide, x, y, w, h, paras, size=18, font=SANS, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.1, after=6):
    """paras: list of paragraphs; each paragraph is a str or a list of (text, {bold, italic, color, font, size, hl})."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(after)
        runs = [para] if isinstance(para, str) else para
        for item in runs:
            t, st = (item, {}) if isinstance(item, str) else item
            r = p.add_run()
            r.text = t
            f = r.font
            f.name, f.size = st.get("font", font), Pt(st.get("size", size))
            f.bold, f.italic = st.get("bold", bold), st.get("italic", False)
            f.color.rgb = st.get("color", color)
            if st.get("hl"):
                highlight(r, st["hl"])
    return tb


def highlight(run, hex_fill: str) -> None:
    rpr = run._r.get_or_add_rPr()
    hl = OxmlElement("a:highlight")
    clr = OxmlElement("a:srgbClr")
    clr.set("val", hex_fill)
    hl.append(clr)
    rpr.append(hl)


def spacing(run, hundredths_pt: int) -> None:
    run._r.get_or_add_rPr().set("spc", str(hundredths_pt))


def box(slide, x, y, w, h, fill=None, line=LINE, width=1.0, radius=True, dash=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE, x, y, w, h)
    if radius:
        s.adjustments[0] = 0.06
    s.shadow.inherit = False
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(width)
        if dash:
            s.line.dash_style = dash
    return s


def arrow(slide, x1, y1, x2, y2, color=INK, width=1.5, dash=None, head=True):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = dash
    if head:
        ln = c.line._get_or_add_ln()
        tail = OxmlElement("a:tailEnd")
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
        ln.append(tail)
    return c


def new_slide(eyebrow: str, headline: str | None, n: int, notes_key: str, head_size=30):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    tb = text(s, LEFT, TOP, Inches(9.5), Inches(0.3), [[(eyebrow.upper(), {"size": 11, "color": MUTED})]])
    spacing(tb.text_frame.paragraphs[0].runs[0], 150)
    text(s, Inches(11.3), TOP, Inches(1.23), Inches(0.3), [[(f"{n} / {TOTAL}", {"size": 11, "color": MUTED, "font": MONO})]],
         align=PP_ALIGN.RIGHT)
    if headline:
        text(s, LEFT, Inches(0.95), Inches(11.0), Inches(1.3), [headline], size=head_size, font=SERIF, bold=True,
             spacing=1.0)
    if notes_key in SCRIPT:
        s.notes_slide.notes_text_frame.text = SCRIPT[notes_key]
    return s


def card(slide, x, y, w, h, big, desc, src=None, big_size=34):
    box(slide, x, y, w, h)
    paras = [[(big, {"font": SERIF, "bold": True, "size": big_size})], [(desc, {"size": 14, "color": MUTED})]]
    if src:
        paras.append([(src, {"size": 10.5, "color": MUTED, "font": MONO})])
    text(slide, x + Inches(0.22), y + Inches(0.2), w - Inches(0.44), h - Inches(0.3), paras, after=8)


def table(slide, x, y, w, rows, col_w, size=16, header_size=11, row_h=0.52):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, Inches(row_h * len(rows)))
    tbl = shape.table
    tbl.first_row = True
    tblpr = shape._element.graphic.graphicData.tbl.tblPr
    style = tblpr.find(qn("a:tableStyleId"))
    if style is not None:
        style.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # "No Style, No Grid"; row rules added per cell
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.fill.background()
            cell.margin_left = cell.margin_right = Inches(0.12)
            cell.margin_top = cell.margin_bottom = Inches(0.06)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            runs = val if isinstance(val, list) else [(val, {})]
            p = tf.paragraphs[0]
            for t, st in runs:
                r = p.add_run()
                r.text = t
                f = r.font
                f.name = st.get("font", SANS)
                f.size = Pt(header_size if i == 0 else st.get("size", size))
                f.bold = st.get("bold", False)
                f.color.rgb = MUTED if i == 0 else st.get("color", INK)
                if st.get("hl"):
                    highlight(r, st["hl"])
                if i == 0:
                    spacing(r, 120)
            _cell_borders(cell, top=i > 0)
    return tbl


def _cell_borders(cell, top: bool) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        ln = OxmlElement(tag)
        if tag == "a:lnT" and top:
            ln.set("w", "9525")
            fill = OxmlElement("a:solidFill")
            clr = OxmlElement("a:srgbClr")
            clr.set("val", "D3DBDA")
            fill.append(clr)
            ln.append(fill)
        else:
            ln.set("w", "0")
            ln.append(OxmlElement("a:noFill"))
        tcpr.append(ln)


def bar_chart(slide, x, y, w, h, categories, series, legend=False):
    data = CategoryChartData()
    data.categories = categories
    for name, values, _ in series:
        data.add_series(name, [v / 100 for v in values])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, w, h, data)
    ch = gf.chart
    ch.font.name, ch.font.size, ch.font.color.rgb = SANS, Pt(13), INK
    ch.has_title = False
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(13)
        ch.legend.font.color.rgb = MUTED
    va = ch.value_axis
    va.minimum_scale, va.maximum_scale, va.major_unit = 0, 1, 0.25
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = GRID
    va.format.line.fill.background()
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = "0%", False
    va.tick_labels.font.color.rgb = MUTED
    va.tick_labels.font.size = Pt(12)
    ca = ch.category_axis
    ca.format.line.color.rgb = HEX("C3C2B7")
    ca.tick_labels.font.size = Pt(14)
    plot = ch.plots[0]
    plot.gap_width = 60 if len(series) > 1 else 110
    plot.overlap = -8 if len(series) > 1 else 0
    for s, (_, _, color) in zip(plot.series, series):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = color
        s.invert_if_negative = False
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = "0%", False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.bold, dl.font.color.rgb = Pt(15), True, INK
    return ch


# ---------------- slides ----------------
# 1 title
s = new_slide("Cotiviti intern assessment · Topic 2: Clinical decision making & pattern recognition", None, 1, "1")
text(s, LEFT, Inches(2.2), Inches(11), Inches(1.2), ["Diagnostic Momentum"], size=58, font=SERIF, bold=True)
text(s, LEFT, Inches(3.45), Inches(9.5), Inches(1.2),
     ["Do AI medical coders copy a wrong diagnosis forward, and put it on the claim?"], size=26, color=MUTED)
text(s, LEFT, Inches(5.1), Inches(11), Inches(0.5),
     [f"{AUTHOR} · September 2026 · Data: Synthetic Hospital v1.3 (Carnegie Mellon, 2026)"], size=15, color=MUTED)
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, LEFT, Inches(4.75), Inches(1.2), Inches(0.06))
bar.fill.solid(); bar.fill.fore_color.rgb = PLANT_STROKE; bar.line.fill.background()

# 2 problem
s = new_slide("The problem", "Charts copy their problem lists forward. Errors travel with them.", 2, "2")
text(s, LEFT, Inches(2.2), Inches(5.6), Inches(4.5), [
    [("Diagnostic momentum: ", {"bold": True}), ("once a diagnosis is written into the chart, it gets repeated and "
                                                  "trusted without being re-checked (Croskerry, 2003).", {})],
    ["Copy-forward documentation spreads outdated or wrong entries from note to note (Hirschtick, 2006; Weis & Levy, 2014)."],
    [("AI medical coders ", {"bold": True}), ("now read these charts and assign the ICD-10 codes that claims are paid on.", {})],
    [("If the AI trusts the problem list, it codes the error.", {"bold": True, "color": ACCENT})],
], size=17, after=14)
box(s, Inches(6.9), Inches(2.2), Inches(5.6), Inches(2.45))
text(s, Inches(7.15), Inches(2.4), Inches(5.2), Inches(2.2), [
    [("Active Problem List:", {"bold": True})],
    ["- Obesity (diagnosed 2020-01-15)"],
    ["- Hyperlipidemia (diagnosed 2020-07-15)"],
    [("- Type 2 diabetes mellitus (diagnosed 2021-07-15)", {"hl": "F8E08E", "color": PLANT_INK})],
    ["- Hypertension"],
], size=13.5, font=MONO, after=3)
text(s, Inches(6.9), Inches(4.85), Inches(5.6), Inches(0.8),
     ["A real pilot patient. The highlighted line was planted: nothing else in the chart diagnoses diabetes."],
     size=13, color=MUTED)

# 3 why now
s = new_slide("Why now", "AI is entering coding from both sides of the claim", 3, "3")
cw, gap = Inches(2.78), Inches(0.2)
for k, (big, desc, src) in enumerate([
    ("+12–20", "percentage points more new-patient visits billed at the top levels after hospitals adopted AI scribes",
     "Patton et al., 2026"),
    ("Arms race", "Provider-side AI raises coding intensity; payers answer with their own AI",
     "Dai et al., 2025; Nong & Neprash, 2026"),
    ("Jan 2026", "CMS WISeR: AI-assisted prior authorization, with human review of denials", "CMS"),
    ("Accept it", "LLMs take false medical evidence at face value and struggle to spot errors in paired notes",
     "Mo et al., 2026; Zhang & Beheshti, 2026"),
]):
    card(s, LEFT + k * (cw + gap), Inches(2.3), cw, Inches(3.3), big, desc, src)

# 4 dataset
s = new_slide("The dataset", "Synthetic Hospital: realistic charts with a verified answer key", 4, "4")
for k, (big, desc) in enumerate([("1,268", "synthetic patients"), ("5,602", "visits, ~4.4 per patient"),
                                 ("53%", "physicians' accuracy telling synthetic charts from real ones (chance is 50%)"),
                                 ("0", "real patients: shareable, and every diagnosis is verified")]):
    card(s, LEFT + (k % 2) * Inches(2.85), Inches(2.3) + (k // 2) * Inches(2.05), Inches(2.7), Inches(1.9), big, desc)
text(s, Inches(6.8), Inches(2.3), Inches(5.7), Inches(4.2), [
    [("Released September 2026 ", {"bold": True}), ("by Carnegie Mellon (Park, Chen & Dettmers). Each diagnosis is "
                                                     "grounded in ICD-10-CM, SNOMED CT and LOINC, with a knowledge graph of findings.", {})],
    ["Real charts can't show whether a copied diagnosis is wrong. Here we know, so we can plant an error and measure "
     "what the AI does with it."],
], size=17, after=14)
note_bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.8), Inches(4.75), Inches(0.05), Inches(0.9))
note_bar.fill.solid(); note_bar.fill.fore_color.rgb = PLANT_STROKE; note_bar.line.fill.background()
text(s, Inches(7.0), Inches(4.75), Inches(5.5), Inches(0.9),
     ["The authors' stated gap: the benchmark “does not explicitly simulate documentation errors.” This project "
      "adds that layer."], size=15)

# 5 pipeline
s = new_slide("Method", "Plant one believable fake per patient, then watch the AI", 5, "5")
bw, bh = Inches(3.45), Inches(1.55)
xs = [LEFT, LEFT + Inches(4.14), LEFT + Inches(8.28)]
y1, y2 = Inches(2.15), Inches(4.85)
nodes = [
    (xs[0], y1, "Synthetic Hospital", ["50 patients with 5+ visits", "Knowledge graph of findings", "Answer key: true diagnoses"], ACCENT, 1.5),
    (xs[1], y1, "Pick a fake diagnosis", ["A tempting wrong exam answer", "≥ 2 matching findings in chart", "Fits the patient's age and sex"], PLANT_STROKE, 2.25),
    (xs[2], y1, "Plant it", ["One line in the problem list", "5 versions of every chart", "Nothing else changes"], PLANT_STROKE, 2.25),
    (xs[2], y2, "AI coder", ["S1: the benchmark's prompt", "S2: + “lists may be wrong”", "S3: + evidence auditor"], LINE, 1.25),
    (xs[1], y2, "Scorer", ["Accuracy vs the answer key", "Did the fake get coded?", "Paired tests, same patients"], LINE, 1.25),
    (xs[0], y2, "Results", ["gpt-oss-120b: 500 calls", "Gemini Flash-Lite × 2", "Total cost: $1.15"], LINE, 1.25),
]
for x, y, title, lines, color, wdt in nodes:
    box(s, x, y, bw, bh, fill=BG, line=color, width=wdt)
    text(s, x + Inches(0.2), y + Inches(0.15), bw - Inches(0.4), bh - Inches(0.2),
         [[(title, {"bold": True, "size": 16})]] + [[(ln, {"size": 13, "color": MUTED})] for ln in lines], after=3)
mid1 = y1 + bh // 2
arrow(s, xs[0] + bw, mid1, xs[1], mid1)
arrow(s, xs[1] + bw, mid1, xs[2], mid1, color=PLANT_STROKE, width=2.25)
text(s, xs[1] + bw - Inches(0.3), mid1 - Inches(0.36), Inches(1.29), Inches(0.3),
     [[("1 fake each", {"size": 11, "color": PLANT_STROKE})]], align=PP_ALIGN.CENTER)
cx = xs[2] + bw // 2
arrow(s, cx, y1 + bh, cx, y2)
text(s, cx + Inches(0.1), y1 + bh + Inches(0.4), Inches(1.4), Inches(0.3), [[("250 charts", {"size": 12, "color": MUTED})]])
mid2 = y2 + bh // 2
arrow(s, xs[2], mid2, xs[1] + bw, mid2)
arrow(s, xs[1], mid2, xs[0] + bw, mid2)
# answer key bypass (dashed, blue) and fake identity bypass (dashed, yellow)
ax, bxk = xs[0] + bw // 2, xs[1] + Inches(0.9)
ymid = y1 + bh + Inches(0.55)
arrow(s, ax, y1 + bh, ax, ymid, color=ACCENT, dash=MSO_LINE_DASH_STYLE.DASH, head=False)
arrow(s, ax, ymid, bxk, ymid, color=ACCENT, dash=MSO_LINE_DASH_STYLE.DASH, head=False)
arrow(s, bxk, ymid, bxk, y2, color=ACCENT, dash=MSO_LINE_DASH_STYLE.DASH)
text(s, ax + Inches(0.4), ymid - Inches(0.32), Inches(1.6), Inches(0.3), [[("answer key", {"size": 12, "color": ACCENT})]])
fx = xs[1] + Inches(2.4)
arrow(s, fx, y1 + bh, fx, y2, color=PLANT_STROKE, dash=MSO_LINE_DASH_STYLE.DASH, width=2)
text(s, fx + Inches(0.1), ymid - Inches(0.32), Inches(1.5), Inches(0.3), [[("which one is fake", {"size": 12, "color": PLANT_STROKE})]])
text(s, LEFT, Inches(6.6), Inches(11.7), Inches(0.4),
     ["The AI coder only ever sees the chart. The answer key and the identity of the fake go straight to the scorer."],
     size=13, color=MUTED)

# 6 versions
s = new_slide("Design", "Every patient, five versions. Only the fake line moves.", 6, "6")
fake = lambda t: [(t, {"hl": "F8E08E", "color": PLANT_INK})]  # noqa: E731
table(s, LEFT, Inches(2.15), WIDTH, [
    ["Version", "What changes in the chart", "Question it answers"],
    [[("Clean", {"bold": True})], "Nothing planted", "Does the AI produce the fake on its own?"],
    [[("Copied once", {"bold": True})], fake("Fake") + [(" in the latest note's problem list", {})], "Is one copy enough to fool it?"],
    [[("Copied 3×", {"bold": True})], fake("Fake") + [(" in the last three notes", {})], "Does repetition make it more convincing?"],
    [[("3× + ruled out", {"bold": True})], "Same, plus “…has since been ruled out on further workup”",
     "Does the AI notice a direct contradiction?"],
    [[("Early, then dropped", {"bold": True})], fake("Fake") + [(" in three early notes, then gone", {})],
     "Does an old, dropped entry still get coded?"],
], col_w=[2.4, 4.9, 4.43], row_h=0.66)

# 7 result 1
s = new_slide("Result 1 · gpt-oss-120b · 50 patients", "One copied line is enough: the AI codes the fake 90% of the time", 7, "7")
bar_chart(s, LEFT, Inches(2.15), WIDTH, Inches(4.35),
          ["Clean", "Copied once", "Copied 3×", "3× + ruled out", "Early, then dropped"],
          [("S1 · benchmark prompt", [2, 90, 92, 48, 80], S1)])
text(s, LEFT, Inches(6.6), WIDTH, Inches(0.5),
     ["Share of charts where the AI coded the planted fake (S1, the benchmark's own prompt). Clean vs planted: paired "
      "McNemar p < 0.001. 95% confidence intervals are in the written report."], size=13, color=MUTED)

# 8 result 2
s = new_slide("Result 2 · the fixes", "A warning helps a little. An evidence auditor cuts errors from 92% to 20%.", 8, "8")
bar_chart(s, LEFT, Inches(2.15), Inches(7.1), Inches(4.6), ["Copied 3×", "3× + ruled out"],
          [("S1 · benchmark prompt", [92, 48], S1), ("S2 · + “lists may be wrong”", [58, 22], S2),
           ("S3 · + evidence auditor", [20, 12], S3)], legend=True)
text(s, Inches(8.3), Inches(2.4), Inches(4.2), Inches(4.3), [
    [("S3 adds one step: ", {"bold": True}), ("a second call checks every code and keeps it only if it can quote "
                                              "evidence from the visit notes. Problem-list lines alone don't count.", {})],
    ["Accuracy on the true diagnoses is unchanged on planted charts (0.53 → 0.55) and dips slightly on clean ones "
     "(0.59 → 0.57)."],
    [("Cost of the auditor: ", {}), ("about $0.002 per chart.", {"bold": True})],
], size=16, after=14)

# 9 across models
s = new_slide("Result 3 · across model families", "Every model is fooled. They differ on contradictions.", 9, "9")
b = lambda t: [(t, {"bold": True, "font": MONO})]  # noqa: E731
m = lambda t: [(t, {"font": MONO})]  # noqa: E731
table(s, LEFT, Inches(2.15), Inches(7.3), [
    ["Version (S1)", "gpt-oss-120b", "Gemini 3.1 Flash-Lite", "Gemini 3.5 Flash-Lite"],
    ["Clean", m("2%"), m("2%"), m("0%")],
    ["Copied once", m("90%"), m("46%"), m("54%")],
    ["Copied 3×", m("92%"), m("48%"), m("61%")],
    ["3× + ruled out", b("48%"), b("2%"), b("4%")],
    ["Early, then dropped", m("80%"), m("37%"), m("51%")],
], col_w=[2.2, 1.6, 1.75, 1.75], size=16, row_h=0.62)
tag = box(s, Inches(8.5), Inches(2.2), Inches(2.7), Inches(0.38), fill=PLANT_BG, line=None)
tag.adjustments[0] = 0.5
text(s, Inches(8.5), Inches(2.24), Inches(2.7), Inches(0.32), [[("GEMINI NUMBERS PROVISIONAL", {"size": 10.5, "bold": True,
                                                                                         "color": PLANT_INK})]],
     align=PP_ALIGN.CENTER)
text(s, Inches(8.5), Inches(2.85), Inches(4.0), Inches(3.8), [
    ["The effect appears in models from two companies: near zero on clean charts, roughly half to nine in ten once the "
     "fake is copied in."],
    [("Gemini respects “ruled out”; gpt-oss ignores it half the time. ", {}),
     ("Each AI tool has its own blind spots, so each needs its own stress test.", {"bold": True})],
], size=16, after=14)

# 10 demo
s = new_slide("Live demo", "See it on one patient", 10, "10")
steps = ["Results tab: the headline numbers",
         "Patient #1992, “Copied 3×”: the fake in the problem list",
         "The AI coder codes it, tagged Planted fake",
         "“3× + ruled out”: it still codes it",
         "The evidence auditor drops the fake, keeps every true diagnosis with a quote, accuracy 1.00"]
text(s, LEFT, Inches(2.3), Inches(6.6), Inches(4.2),
     [[(f"{k}   ", {"font": MONO, "color": ACCENT, "bold": True}), (t, {})] for k, t in enumerate(steps, 1)],
     size=18, after=14)
box(s, Inches(8.0), Inches(2.3), Inches(4.5), Inches(1.9))
text(s, Inches(8.25), Inches(2.5), Inches(4.1), Inches(1.6), [
    [("Run locally", {"size": 14, "color": MUTED})], [("streamlit run app.py", {"font": MONO, "size": 17})],
    [("Reads saved results only. No API calls, no cost.", {"size": 14, "color": MUTED})]], after=8)

# 11 opportunities / threats
s = new_slide("For Cotiviti", "Opportunities and threats", 11, "11")
for k, (title, color, items) in enumerate([
    ("OPPORTUNITIES", ACCENT, [("Evidence-cited chart review at scale: ", "every code backed by a quote"),
                               ("Cheap, verifiable model testing: ", "this whole study cost $1.15"),
                               ("Operations triage: ", "route problem-list-only codes to human reviewers first")]),
    ("THREATS", BAD, [("Automated overpayment: ", "copy-forward errors become coded claims"),
                      ("False confidence: ", "prompt warnings leave most errors in place"),
                      ("Provider abrasion: ", "over-strict auditors could deny true diagnoses"),
                      ("Synthetic-to-real gap: ", "results need confirming on real records")]),
]):
    x = LEFT + k * Inches(5.97)
    box(s, x, Inches(2.2), Inches(5.76), Inches(4.3))
    text(s, x + Inches(0.3), Inches(2.45), Inches(5.2), Inches(3.9),
         [[(title, {"bold": True, "size": 13, "color": color})]] +
         [[("•  " + lead, {"bold": True}), (rest, {})] for lead, rest in items], size=16, after=12)

# 12 recommendations
s = new_slide("Recommendations", "Three moves for Cotiviti", 12, "12")
for k, (lead, rest) in enumerate([
    ("Adopt an evidence-first standard for AI coding and review",
     "Every AI-generated or AI-reviewed code cites encounter-level evidence; problem-list-only codes go to a human. "
     "Pilot in clinical chart validation."),
    ("Make planted-error stress tests a release gate",
     "Test every coding or audit model, vendor or in-house, on paired clean and planted charts. Report propagation, "
     "not just accuracy."),
    ("Take a position in the coding arms race",
     "Publish a payer-side documentation-evidence standard and partner with benchmark groups to extend tests to "
     "documentation errors."),
]):
    y = Inches(2.15) + k * Inches(1.35)
    text(s, LEFT, y, Inches(0.7), Inches(0.8), [[(str(k + 1), {"font": SERIF, "bold": True, "size": 34, "color": ACCENT})]])
    text(s, LEFT + Inches(0.85), y, Inches(10.8), Inches(1.25),
         [[(lead, {"bold": True, "size": 19})], [(rest, {"size": 15, "color": MUTED})]], after=4)
text(s, LEFT, Inches(6.55), WIDTH, Inches(0.4),
     ["Code, data and full results in the GitHub repository. References in the written report."], size=13, color=MUTED)

out = ROOT / "deliverables" / "Diagnostic_Momentum_Slides.pptx"
prs.save(out)
print("saved", out)
