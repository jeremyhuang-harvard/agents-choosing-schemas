"""Build TL;DR figures (HTML -> PNG via browser) from docs/tldr_data.json.

    PYTHONPATH=. uv run python scripts/build_tldr_figs.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "docs/tldr_data.json").read_text())
OUT = ROOT / "docs/tldr"
OUT.mkdir(parents=True, exist_ok=True)

MEM = {"A": "Wage $40k", "B": "Lyft wait", "C": "Disney pass", "D": "Toll", "E": "Circled parking",
       "F": "Valet on date", "G": "Declined $29/h shift", "H": "Cleaner", "I": "Cheap gas"}
RATE = {"A": "=$19", "B": "≤$30", "C": "≥$15", "D": "≥$36", "E": "≤$45", "F": "≥$210", "G": "≥$29", "H": "≥$20", "I": "≤$18"}
FLOOR, CEIL = set("CDFGH"), set("BEI")
QS = [("general", "General: what is an hour worth?"), ("nonstop_flight", "Nonstop flight (pay to save 3 h)"),
      ("priority_pickup", "Priority rideshare (pay to save 10 min)"), ("grocery_delivery", "Grocery delivery (save 1 h)"),
      ("furniture_assembly", "Bookshelf assembly (save 2 h)"), ("theme_park", "Theme-park line pass (save 2 h)"),
      ("train_delay", "Train delay compensation (5 h)"), ("volunteer_or_donate", "Donation = 2 h volunteering"),
      ("weekend_gig", "Weekend gig (accept to work 4 h)"), ("research_study", "Research study (accept 1 h)")]
HYP = {"general": "A", "weekend_gig": "AG", "research_study": "AG", "nonstop_flight": "BD", "priority_pickup": "BD",
       "grocery_delivery": "EIH", "furniture_assembly": "H", "theme_park": "C", "train_delay": "BD", "volunteer_or_donate": "A"}
ORDER = list("HCDBFAGIE")
CSS = """*{box-sizing:border-box}body{margin:0;background:#fff;color:#111827;font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.s{width:1600px;height:900px;padding:40px 54px;overflow:hidden}h1{font-size:36px;margin:0 0 4px}.sub{font-size:19px;color:#6b7280;margin:0 0 18px}
.t{color:#6b7280}.fl{color:#0f766e}.ce{color:#c2410c}.pt{color:#6d28d9}"""


def page(name, body):
    (OUT / f"{name}.html").write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="s">{body}</div></body></html>')


def mcls(f):
    return "fl" if f in FLOOR else "ce" if f in CEIL else "pt"


# ---------------- Fig 1: schema selection heatmap ----------------
def cellcol(p):
    return f"rgba(37,99,235,{min(1, p*1.15):.2f})"


rows = []
head = '<tr><th style="text-align:left">Question (each asked in its own call)</th>' + "".join(
    f'<th><span class="{mcls(f)}">{f}</span><br><span style="font-weight:500">{MEM[f]}</span><br><span class="t" style="font-weight:500">{RATE[f]}</span></th>' for f in ORDER) + "</tr>"
for q, lab in QS:
    cells = []
    for f in ORDER:
        w, n = D["sel"][f"{q}|{f}"]
        p = w / n
        hyp = f in HYP[q]
        top = D["top"][q] == f
        txt = "#fff" if p > .45 else "#111827"
        border = "outline:3px dashed #d97706;outline-offset:-4px;" if hyp else ""
        cells.append(f'<td style="background:{cellcol(p)};color:{txt};{border}{"font-weight:800" if top else ""}">{p:.0%}</td>')
    rows.append(f'<tr><td class="ql">{lab}</td>{"".join(cells)}</tr>')
page("fig1_schema_by_question", f"""
<style>table{{border-collapse:separate;border-spacing:3px;font-size:16px;width:100%}}th{{font-size:14px;font-weight:700;padding:4px}}
td{{text-align:center;padding:9px 4px;border-radius:5px}}td.ql{{text-align:left;font-size:16px;padding-right:10px;white-space:nowrap}}</style>
<h1>Which memory does each question pull in?</h1>
<p class="sub">% of calls where the answer equals that memory's $/hour, among calls where it was shown alongside other memories (2–9 memories, 1,140 calls).
<b>Bold</b> = most-used memory for that question · <span style="outline:3px dashed #d97706;padding:0 6px">dashed</span> = our prediction before the run.</p>
<table>{head}{"".join(rows)}</table>
<p class="sub" style="margin-top:14px">Two memories dominate almost every question: the <span class="fl"><b>cleaner</b></span> ($60 ÷ 3 h) and the <span class="fl"><b>Disney pass</b></span> ($30 ÷ 2 h).
Only priority pickup switches schema (to Lyft). The wage is used for one question: the charity donation.</p>""")

# ---------------- Fig 2: predictions scorecard ----------------
hw, hn, ow, on = D["hyp"]
dmw, dmn, dnw, dnn = D["dom"]
preds = [
    ("Each question will pull in its topically matching memory", "Partly",
     f"Predicted memory is the most-used one for 3/10 questions (priority pickup, bookshelf, theme park). Predicted memories are used 2× as often as others ({hw/hn:.0%} vs {ow/on:.0%}), but two easy-arithmetic memories win most questions."),
    ("The wage will anchor the general question", "No",
     "Wage wins 6% of general-question contests; the cleaner wins 71%. The wage is used mainly for the donation question (47%)."),
    ("The model will respect one-sided bounds (≥ vs ≤)", "No",
     "Floors are treated as exact prices and copied; ceilings are read as a “cost-conscious” trait, and answers fall below the ceiling. With one of each, 45% of answers fall below both."),
    ("Mixed-motive memories (date, vacation) will be discounted", "No",
     "The $210/h valet rate is applied at face value when alone (train delay = $1,050 in 5/5). The Disney pass is the single most-used memory overall."),
    ("Turning down a $29/h shift will raise the price for weekend work", "No",
     "Weekend-gig answers are mostly below $29/h; the model reads the refusal as ‘accept less’. Only 1/5 samples gets 4 × $29."),
    ("More memories will be integrated (averaged)", "No",
     "0/380 answers equal the mean of shown rates. With more memories, answers converge on copying one memory's rate (35% → 95%)."),
    ("Being paid to give up time > paying to save it (endowment-style gap)", "No",
     "No gap: median $/h is the same for ‘accept pay to work’ and ‘pay to save time’ questions (~$14–15/h)."),
    ("Wording mentions will track use", "No",
     "Traces mention the shown memory ~100% of the time; the wage is computed in 67% of traces where it's shown but used in 9%."),
]
col = {"Yes": "#16a34a", "Partly": "#d97706", "No": "#dc2626"}
items = "".join(f'<div class="row"><div class="v" style="background:{col[v]}">{v}</div><div><div class="p">{esc}</div><div class="e">{ev}</div></div></div>'
                for esc, v, ev in preds)
page("fig2_predictions", f"""
<style>.row{{display:grid;grid-template-columns:110px 1fr;gap:16px;align-items:start;padding:10px 0;border-bottom:1px solid #f3f4f6}}
.v{{color:#fff;font-weight:800;border-radius:8px;text-align:center;padding:8px 0;font-size:18px}}.p{{font-size:19px;font-weight:700}}.e{{font-size:15.5px;color:#4b5563;margin-top:3px;line-height:1.35}}</style>
<h1>Were our predictions right?</h1><p class="sub">Expectations set in the design before the run (hypothesized memory per question, bound types, design notes), versus what Qwen3-8B (thinking) did.</p>{items}""")

# ---------------- Fig 3: switching the question -> switching the schema? (pairs) ----------------
ex = {tuple(p): qa for p, qa in D["flip_examples"]}
QL = {q: l.split(" (")[0].split(":")[0] for q, l in QS}
chosen = [("D", "H"), ("B", "D"), ("C", "H"), ("A", "D"), ("B", "F"), ("A", "B")]
blocks = []
for a, b in chosen:
    qa = ex.get((a, b), {})
    left = [QL[q] for q, w in qa.items() if w == a]
    right = [QL[q] for q, w in qa.items() if w == b]
    chip = lambda f, qs: "".join(f'<span class="chip {mcls(f)}b">{x}</span>' for x in qs) or '<span class="t">—</span>'
    blocks.append(f'''<div class="pair"><div class="ph"><span class="{mcls(a)}"><b>{a}</b> {MEM[a]} <span class="t">{RATE[a]}</span></span>
<span class="vs">vs</span><span class="{mcls(b)}"><b>{b}</b> {MEM[b]} <span class="t">{RATE[b]}</span></span></div>
<div class="sides"><div>{chip(a, left)}</div><div>{chip(b, right)}</div></div></div>''')
fl = D["flip"]
page("fig3_question_switches_schema", f"""
<style>.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.pair{{border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px}}
.ph{{display:grid;grid-template-columns:1fr 40px 1fr;font-size:18px;margin-bottom:8px}}.vs{{text-align:center;color:#9ca3af}}
.sides{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.chip{{display:inline-block;font-size:14px;padding:3px 9px;border-radius:999px;margin:3px 4px 0 0;color:#fff}}
.flb{{background:#0f766e}}.ceb{{background:#c2410c}}.ptb{{background:#6d28d9}}.big{{font-size:20px;margin:0 0 16px}}</style>
<h1>Does changing the question change which memory is used?</h1>
<p class="big">Same two memories, ten different questions. In <b>{fl.get("both used (question decides)",0)}/36 pairs</b> the question decides which memory wins at least once; in
<b>{fl.get("one always",0)}/36</b> one memory wins every time. Within a pair, the dominant memory still takes a median <b>85%</b> of decided calls.</p>
<div class="grid">{"".join(blocks)}</div>
<p class="sub" style="margin-top:14px">Each chip = a question whose most common answer copied that memory's rate (2 samples per pair × question). Switches are mostly topical
(rideshare → Lyft, bookshelf → cleaner); the general and flight questions follow whichever memory has the easier division.</p>""")

# ---------------- Fig 4: what the traces show ----------------
mv = D["moves"]; mn = D["moves_n"]
G = ["No memory", "1 floor memory", "1 ceiling memory", "Wage only", "2 memories", "3–9 memories"]
MV = ["Computes an hourly rate", "Trait: cost-conscious / frugal", "Uses persona for income/status", "Appeals to what's 'common/typical'",
      "Mentions averaging", "Flags a conflict between memories", "Says the value depends on context", "Cites a nonexistent example / prior turn"]
hdr = "<tr><th></th>" + "".join(f"<th>{g}<br><span class='t' style='font-weight:500'>n={mn[g]}</span></th>" for g in G) + "</tr>"
trs = ""
for m in MV:
    trs += f"<tr><td class='ml'>{m}</td>" + "".join(
        f"<td><div class='bw'><div class='b' style='width:{mv[g][m]*70:.0f}px'></div><span>{mv[g][m]:.0%}</span></div></td>" for g in G) + "</tr>"
sa = D["stated_actual"]
sarows = "".join(
    f"<div class='sr'><span class='{mcls(f)}'><b>{f}</b> {MEM[f]}</span><div class='sb'><div class='b2' style='width:{sa[f]['computed']/sa[f]['n']*150:.0f}px'></div></div>"
    f"<span>{sa[f]['computed']/sa[f]['n']:.0%}</span><div class='sb'><div class='b3' style='width:{sa[f]['used']/sa[f]['n']*150:.0f}px'></div></div><span>{sa[f]['used']/sa[f]['n']:.0%}</span></div>"
    for f in sorted(sa, key=lambda f: -sa[f]["computed"] / sa[f]["n"]))
page("fig4_traces", f"""
<style>table{{border-collapse:collapse;font-size:14px}}th{{font-size:13.5px;padding:4px 6px;text-align:left}}td{{padding:4px 6px;border-top:1px solid #f3f4f6}}
td.ml{{font-weight:600;font-size:14px;width:210px}}.bw{{display:flex;align-items:center;gap:6px}}.b{{height:13px;background:#2563eb;border-radius:2px}}
.wrap{{display:grid;grid-template-columns:960px 1fr;gap:24px}}.sr{{display:grid;grid-template-columns:150px 1fr 40px 1fr 40px;gap:6px;align-items:center;font-size:14.5px;margin:5px 0}}
.sb{{background:#f3f4f6;height:13px;border-radius:2px}}.b2{{background:#9ca3af;height:13px;border-radius:2px}}.b3{{background:#111827;height:13px;border-radius:2px}}
h3{{font-size:19px;margin:0 0 8px}}</style>
<h1>What the thinking traces show</h1><p class="sub">Share of traces containing each reasoning move (keyword-coded; 1,640 traces).</p>
<div class="wrap"><div><table>{hdr}{trs}</table>
<p class="sub" style="margin-top:12px;font-size:16px">One-memory traces split by type: a floor memory triggers rate arithmetic (92%); a ceiling memory triggers the “cost-conscious” trait (93%).
Conflicts get noticed more as memories pile up (42%), but “it depends on the setting” almost never appears (≤12%).</p></div>
<div><h3>Computed in the trace vs. used in the answer</h3><div class="sr t" style="font-size:13px"><span></span><span>trace computes the memory's rate</span><span></span><span>answer equals that rate</span><span></span></div>{sarows}
<p class="sub" style="font-size:15px;margin-top:10px">The model computes the wage ($19.23/h) in 67% of traces where it's shown and uses it in 9%. Computing a rate is not the same as choosing it.
(Keyword-coded; the shift's “$29/h” also appears in the prompt, so its left bar is inflated by restatement.)</p></div></div>""")

# ---------------- Fig 5: convergence with more memories ----------------
L = D["length"]
ns = [k for k in sorted(L, key=int) if int(k) >= 1]
bars = "".join(f"<div class='c'><div class='cb' style='height:{L[n]['copy']*330:.0f}px'><span>{L[n]['copy']:.0%}</span></div><div class='cl'>{n}</div>"
               f"<div class='cw'>{L[n]['think_words']:.0f}w</div></div>" for n in ns)
page("fig5_more_memories", f"""
<style>.ch{{display:flex;align-items:flex-end;gap:26px;height:380px;border-bottom:2px solid #374151;padding:0 20px}}.c{{display:flex;flex-direction:column;align-items:center;width:90px}}
.cb{{width:70px;background:#2563eb;border-radius:6px 6px 0 0;position:relative}}.cb span{{position:absolute;top:-28px;left:0;right:0;text-align:center;font-weight:700;font-size:18px}}
.cl{{font-size:20px;font-weight:700;margin-top:8px}}.cw{{font-size:14px;color:#6b7280}}</style>
<h1>More memories → it picks one and copies it, rather than blending</h1>
<p class="sub">% of answers that exactly equal one of the shown memories' $/hour (x-axis = number of memories shown; grey = median trace length in words).</p>
<div class="ch">{bars}</div>
<p class="sub" style="margin-top:22px;font-size:20px">0 of 380 answers with 3+ memories equal the average of the shown rates, even though 28% of those traces say “average”.
Traces get 2.5× longer (≈510 → 1,300 words), but the extra reasoning ends in selection, not integration.</p>""")
print("wrote", sorted(p.name for p in OUT.glob("*.html")))
