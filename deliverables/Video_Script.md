# Video script: Diagnostic Momentum (target 4:45, limit 5:00)

**Speaker:** Lakshita Singh · **Setup:** camera on the whole time; PowerPoint in slideshow mode; the demo app already
open at http://localhost:8501 on patient #1992 in another window. The same lines are in each slide's speaker notes.

About 570 spoken words. At a relaxed 130–140 words per minute that is about 4:15 of speech, plus about 30 seconds of
clicking in the demo.

---

### Slide 1 · Title · 0:00–0:15
Hi, I'm Lakshita Singh. For Topic 2, clinical decision making and pattern recognition, I asked one question: do AI
medical coders copy a wrong diagnosis forward, and put it on the claim?

### Slide 2 · The problem · 0:15–0:40
Every visit note carries an Active Problem List that is copied from the previous note. Doctors call the resulting
failure *diagnostic momentum*: once a diagnosis is written down, it gets repeated without being re-checked. Today, AI
coders read these charts and assign the ICD-10 codes that claims are paid on. If the AI trusts the problem list, it
codes the error. The highlighted line here is one I planted.

### Slide 3 · Why now · 0:40–1:00
This matters now. After adopting AI scribes, hospitals billed twelve to twenty points more visits at the top levels,
and payers are answering with their own AI: a coding arms race. CMS started AI-assisted prior authorization this year.
And research shows language models accept false medical evidence at face value.

### Slide 4 · Dataset · 1:00–1:20
Real charts can't tell us whether a copied diagnosis is wrong. Synthetic Hospital, released by Carnegie Mellon this
month, can: 1,268 synthetic patients, charts physicians can't tell from real ones, and a verified answer key. Its
authors say it doesn't yet simulate documentation errors, so that's the layer I added.

### Slide 5 · Method · 1:20–1:45
For fifty patients, I picked one believable wrong diagnosis, a tempting wrong exam answer that matches at least two
findings in the chart, and planted it as a single problem-list line. The AI coder only sees the chart. The answer key,
and which diagnosis is fake, go straight to the scorer.

### Slide 6 · Five versions · 1:45–2:00
Each patient appears in five versions: clean, copied once, copied three times, three times plus a note saying it was
ruled out, and planted early then dropped. Only that one line changes.

### Slide 7 · Result 1 · 2:00–2:20
Result one. On clean charts the AI almost never codes the fake: two percent. Copy it in once, and it codes it ninety
percent of the time. Even when the chart explicitly says it was ruled out: forty-eight percent.

### Slide 8 · Result 2 · 2:20–2:45
Can we fix it? A warning in the prompt only brings ninety-two percent down to fifty-eight. A design change works much
better: an evidence auditor, a second step that keeps a code only if it can quote evidence from the visit notes. That
cuts it to twenty percent, with accuracy on the true diagnoses essentially unchanged, for about a fifth of a cent per
chart.

### Slide 9 · Across models · 2:45–3:00
And it isn't one model's quirk. Two Gemini models show the same effect at lower rates. Interestingly, they respect the
ruled-out note, which gpt-oss ignores half the time. So every AI tool needs its own stress test.

### Slide 10 · Live demo · 3:00–4:15 → switch to the app
Let me show it.
1. *(Results tab)* The Results tab has the headline numbers.
2. *(Patient explorer → #1992 → "Copied 3×")* Here is the fake, morbid obesity, in the problem list, highlighted.
3. *(Point at the right column)* The AI coder codes it, and it's tagged "planted fake".
4. *(Switch to "Copied 3× + ruled out")* The latest note says it was excluded, and the coder still codes it.
5. *(Scroll to "Evidence auditor")* The auditor drops the fake, keeps every true diagnosis with a quoted sentence as
   proof, and accuracy goes to one point zero.

→ switch back to the slides.

### Slide 11 · Opportunities and threats · 4:15–4:35
For Cotiviti, the opportunities are evidence-cited chart review at scale and cheap, verifiable model testing. The
threats are automated overpayment, and false confidence in prompt-level fixes.

### Slide 12 · Recommendations · 4:35–4:55
So, three recommendations: adopt an evidence-first standard for AI coding; make planted-error stress tests a release
gate for every model; and lead on documentation-evidence standards in the coding arms race. The whole study cost one
dollar fifteen. Thank you.

---

## Recording tips
- **Rehearse once with a timer.** If you're over 4:50, shorten the demo first (skip step 1).
- **Before recording:** start the app (`.venv\Scripts\streamlit run app.py`), select patient #1992 and "Copied 3×",
  and zoom the browser to about 110% so text reads well on video.
- **Recording tool:** PowerPoint's built-in *Record* (Slide Show → Record) captures slides, your camera and narration,
  and exports MP4 (File → Export → Create a Video). For the demo, share your screen with a recorder that also shows your
  camera (e.g. Microsoft Clipchamp or OBS), or record the demo separately and join the clips in Clipchamp.
- **If Gemini numbers change** after the final runs, update slide 9 and the "lower rates" sentence.
