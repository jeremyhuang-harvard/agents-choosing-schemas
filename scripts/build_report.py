"""Build docs/report.html (standalone write-up) and two slide graphics (docs/slides/*.html, 1600x900).

Every number in the report is computed here from runs/s1_single and runs/s2_combos.
    PYTHONPATH=. uv run python scripts/build_report.py
"""
from __future__ import annotations

import collections
import html
import json
import math
import re
import statistics as st
from pathlib import Path

from value_of_time.prompt import FACTS_HEADER, FORMAT, INTRO, SURVEY_HEADER
from value_of_time.stimuli import FACT_BY_ID, PERSONA, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
(DOCS / "slides").mkdir(parents=True, exist_ok=True)

FLOOR_C, CEIL_C, POINT_C = "#0f766e", "#c2410c", "#6d28d9"
V = {f.id: f.implied_hourly for f in FACT_BY_ID.values()}
FLOOR = {f for f, x in FACT_BY_ID.items() if x.bound == "lower"}
CEIL = {f for f, x in FACT_BY_ID.items() if x.bound == "upper"}

SHORT = {  # slide wording: memory, arithmetic, bound
    "A": ("Earns $40,000 a year, full-time", "$40,000 ÷ 2,080 h", "= $19/h"),
    "B": ("Waited 8 extra min on Lyft to save $4", "$4 ÷ 8 min", "≤ $30/h"),
    "C": ("Paid $30 for a Disneyland skip-the-line pass (saves ~2 h)", "$30 ÷ 2 h", "≥ $15/h"),
    "D": ("Pays a $9 toll to save 15 min on the commute", "$9 ÷ 15 min", "≥ $36/h"),
    "E": ("Circled 20 min for free parking instead of a $15 garage", "$15 ÷ 20 min", "≤ $45/h"),
    "F": ("Paid $35 for valet on a date (saves ~10 min)", "$35 ÷ 10 min", "≥ $210/h"),
    "G": ("Turned down an extra Saturday shift at $29/h", "refused $29/h", "≥ $29/h"),
    "H": ("Pays a cleaner $60 for a job that would take 3 h", "$60 ÷ 3 h", "≥ $20/h"),
    "I": ("Drove 10 extra min to save $3 on gas", "$3 ÷ 10 min", "≤ $18/h"),
}
MIXED = {"C": "also fun / vacation", "F": "also a date"}
QSHORT = {
    "general": ("General", "How much is one hour of your time worth?", "1 h"),
    "nonstop_flight": ("Nonstop flight", "Most extra you'd pay for a nonstop that saves 3 h", "3 h"),
    "priority_pickup": ("Priority pickup", "Most extra for a rideshare that arrives 10 min sooner", "10 min"),
    "grocery_delivery": ("Grocery delivery", "Most in fees + tip to skip a 1-h store trip", "1 h"),
    "furniture_assembly": ("Bookshelf", "Most you'd pay someone for a 2-h assembly", "2 h"),
    "theme_park": ("Theme park", "Most for a pass that skips 2 h of lines", "2 h"),
    "weekend_gig": ("Weekend gig", "Lowest pay you'd accept for a 4-h Saturday job", "4 h"),
    "research_study": ("Research study", "Lowest pay for a 1-h weekday-evening study", "1 h"),
    "train_delay": ("Train delay", "Compensation that makes up for a 5-h delay", "5 h"),
    "volunteer_or_donate": ("Donate vs. volunteer", "Donation equal to volunteering 2 h", "2 h"),
}
QGROUPS = [("Pay to save time", ["nonstop_flight", "priority_pickup", "grocery_delivery", "furniture_assembly", "theme_park"]),
           ("Be paid to give up time", ["weekend_gig", "research_study", "train_delay"]),
           ("Neutral", ["general", "volunteer_or_donate"])]
QORDER = ["general", "nonstop_flight", "priority_pickup", "grocery_delivery", "furniture_assembly", "theme_park",
          "train_delay", "volunteer_or_donate", "weekend_gig", "research_study"]


def load(p):
    out = {}
    for line in open(p):
        r = json.loads(line)
        if r["status"] == "ok":
            out[r["cell_id"]] = r
    return list(out.values())


S1 = load(ROOT / "runs/s1_single/records.jsonl")
S2 = load(ROOT / "runs/s2_combos/records.jsonl")
cond = lambda r: "-".join(r["fact_set"]) or "none"
hit = lambda h, f: h is not None and abs(h - V[f]) / V[f] <= 0.03
esc = html.escape


def med(rs, q):
    v = [r["implied_hourly"] for r in rs if r["question"] == q and r["implied_hourly"] is not None]
    return st.median(v) if v else float("nan")


def bcol(f):
    return FLOOR_C if f in FLOOR else CEIL_C if f in CEIL else POINT_C


def btxt(f):
    return "floor" if f in FLOOR else "ceiling" if f in CEIL else "exact"


# ---------------------------------------------------------------- numbers
s1_by = collections.defaultdict(list)
for r in S1:
    s1_by[cond(r)].append(r)
copy1 = {f: (sum(hit(r["implied_hourly"], f) for r in s1_by[f]), len(s1_by[f])) for f in V}
TRAIT = r"cost[- ]conscious|frugal|budget|thrifty|saving money"
trait = {k: (sum(bool(re.search(TRAIT, r["thinking"], re.I)) for r in rs), len(rs)) for k, rs in s1_by.items()}
flight_none = sorted(r["answer"] for r in s1_by["none"] if r["question"] == "nonstop_flight")
flight_B = sorted(r["answer"] for r in s1_by["B"] if r["question"] == "nonstop_flight")
gig_G = sorted(r["answer"] for r in s1_by["G"] if r["question"] == "weekend_gig")

pairs = [r for r in S2 if len(r["fact_set"]) == 2]
multi = [r for r in S2 if len(r["fact_set"]) >= 3]
fc = collections.Counter()
for r in pairs:
    fs = set(r["fact_set"])
    if len(fs & FLOOR) == 1 and len(fs & CEIL) == 1 and r["implied_hourly"] is not None:
        h = r["implied_hourly"]
        fl, ce = (fs & FLOOR).pop(), (fs & CEIL).pop()
        lo, hi = sorted([V[fl], V[ce]])
        fc["Equals the floor rate" if hit(h, fl) else "Equals the ceiling rate" if hit(h, ce) else
           "Between the two" if lo * .97 <= h <= hi * 1.03 else "Below both" if h < lo else "Above both"] += 1
fc_n = sum(fc.values())
avg_match = sum(1 for r in multi if r["implied_hourly"] and
                abs(r["implied_hourly"] - st.mean(V[f] for f in r["fact_set"])) / st.mean(V[f] for f in r["fact_set"]) <= .03)
avg_word = sum(bool(re.search(r"\baverage|\bmean\b", r["thinking"], re.I)) for r in multi)


def win(rs, f):
    sh = [r for r in rs if f in r["fact_set"]]
    w = sum(hit(r["implied_hourly"], f) and sum(hit(r["implied_hourly"], g) for g in r["fact_set"]) == 1 for r in sh)
    return w, len(sh)


wins = {f: win(multi, f) for f in V}
copy_by_n = []
for n in range(1, 10):
    rs = [r for r in (S1 if n == 1 else S2) if len(r["fact_set"]) == n]
    if rs:
        copy_by_n.append((n, sum(any(hit(r["implied_hourly"], f) for f in r["fact_set"]) for r in rs), len(rs)))
bd = [r for r in pairs if set(r["fact_set"]) == {"B", "D"}]
bd_flag = sum(bool(re.search(r"contradict|inconsisten|conflict|doesn.t add up|paradox|mixed signal", r["thinking"], re.I)) for r in bd)
pos = collections.Counter(); exp = collections.Counter()
for r in multi:
    hs = [f for f in r["fact_order"] if hit(r["implied_hourly"], f)]
    if len(hs) == 1:
        n = len(r["fact_order"]); i = r["fact_order"].index(hs[0])
        pos["first" if i == 0 else "last" if i == n - 1 else "middle"] += 1
        exp["first"] += 1 / n; exp["last"] += 1 / n; exp["middle"] += (n - 2) / n
f_multi = [r for r in S2 if "F" in r["fact_set"] and len(r["fact_set"]) >= 2]
f_win = sum(hit(r["implied_hourly"], "F") for r in f_multi)
nine_gig = sorted(r["answer"] for r in S2 if len(r["fact_set"]) == 9 and r["question"] == "weekend_gig")


# ---------------------------------------------------------------- figures (shared by report + slides)
def memory_svg(width=1500, row=74, label_w=640, font=20):
    lo, hi = 10, 300
    x0, x1 = label_w + 40, width - 40
    X = lambda v: x0 + (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * (x1 - x0)
    order = sorted(V, key=lambda f: V[f])
    top = 40
    H = top + row * len(order) + 70
    s = [f'<svg viewBox="0 0 {width} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
         '<defs>' + ''.join(f'<marker id="ar{c[1:]}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
                            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
                            for c in (FLOOR_C, CEIL_C)) + '</defs>']
    base = 20
    s.append(f'<line x1="{X(base):.0f}" y1="{top-14}" x2="{X(base):.0f}" y2="{top + row*len(order)}" stroke="#9ca3af" stroke-dasharray="5 5"/>')
    s.append(f'<text x="{X(base)+6:.0f}" y="{top-18}" font-size="{font-4}" fill="#6b7280">model\'s answer with no memory ≈ $20/h</text>')
    for i, f in enumerate(order):
        y = top + row * i + row / 2
        c = bcol(f)
        mem, arith, bound = SHORT[f]
        if i % 2 == 0:
            s.append(f'<rect x="0" y="{y-row/2}" width="{width}" height="{row}" fill="#f9fafb"/>')
        s.append(f'<text x="10" y="{y-4}" font-size="{font}" fill="#111827"><tspan font-weight="700">{f}</tspan>  {esc(mem)}</text>')
        note = f'  ·  {MIXED[f]}' if f in MIXED else ''
        s.append(f'<text x="34" y="{y+20}" font-size="{font-4}" fill="#6b7280">{esc(arith)}{esc(note)}</text>')
        xv = X(V[f])
        if f in FLOOR:
            s.append(f'<line x1="{xv:.0f}" y1="{y}" x2="{x1:.0f}" y2="{y}" stroke="{c}" stroke-width="5" stroke-opacity=".35" marker-end="url(#ar{c[1:]})"/>')
        elif f in CEIL:
            s.append(f'<line x1="{xv:.0f}" y1="{y}" x2="{x0:.0f}" y2="{y}" stroke="{c}" stroke-width="5" stroke-opacity=".35" marker-end="url(#ar{c[1:]})"/>')
        s.append(f'<circle cx="{xv:.0f}" cy="{y}" r="9" fill="{c}"/>')
        tx = xv + 14 if V[f] < 150 else xv - 14
        anchor = "start" if V[f] < 150 else "end"
        s.append(f'<text x="{tx:.0f}" y="{y-12}" font-size="{font}" font-weight="700" fill="{c}" text-anchor="{anchor}">{esc(bound)}</text>')
    ay = top + row * len(order) + 14
    s.append(f'<line x1="{x0}" y1="{ay}" x2="{x1}" y2="{ay}" stroke="#374151"/>')
    for t in (10, 15, 20, 30, 50, 100, 200, 300):
        s.append(f'<line x1="{X(t):.0f}" y1="{ay}" x2="{X(t):.0f}" y2="{ay+6}" stroke="#374151"/>'
                 f'<text x="{X(t):.0f}" y="{ay+26}" font-size="{font-4}" text-anchor="middle" fill="#374151">${t}</text>')
    s.append(f'<text x="{(x0+x1)/2:.0f}" y="{ay+52}" font-size="{font-4}" text-anchor="middle" fill="#6b7280">implied value of one hour (log scale)</text>')
    s.append('</svg>')
    return "".join(s)


def legend(font=16):
    item = lambda c, t: (f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:22px">'
                         f'<span style="width:14px;height:14px;border-radius:50%;background:{c};display:inline-block"></span>{t}</span>')
    return (f'<div style="font-size:{font}px;color:#374151">'
            + item(FLOOR_C, "<b>Floor</b>: paid money to save time → hour worth <i>at least</i> this")
            + item(CEIL_C, "<b>Ceiling</b>: spent time to save money → hour worth <i>at most</i> this")
            + item(POINT_C, "<b>Exact</b>: wage") + '</div>')


def heatmap():
    rows = ["none"] + sorted(V, key=lambda f: (f not in FLOOR, f not in {"A", "G"}, f))
    rows = ["none", "H", "C", "D", "F", "G", "A", "B", "E", "I"]
    col = lambda v: f"hsl({220-200*max(0,min(1,(math.log10(max(v,1))-.5)/2)):.0f} 70% {88-38*max(0,min(1,(math.log10(max(v,1))-.5)/2)):.0f}%)"
    h = ['<table class="hm"><tr><th>Memory shown</th><th>rate</th>' + "".join(f'<th>{QSHORT[q][0]}</th>' for q in QORDER) + "</tr>"]
    for k in rows:
        lab = "No memory" if k == "none" else f'<span style="color:{bcol(k)};font-weight:700">{k}</span> {esc(SHORT[k][0])}'
        rate = "" if k == "none" else SHORT[k][2]
        h.append(f'<tr><td class="l">{lab}</td><td class="t">{rate}</td>')
        for q in QORDER:
            m = med(s1_by[k], q)
            on = k != "none" and hit(m, k)
            h.append(f'<td class="c{" on" if on else ""}" style="background:{col(m)}">{m:.0f}</td>')
        h.append("</tr>")
    return "".join(h) + "</table>"


def bars(items, maxv=1.0, color="#2563eb", w=260):
    out = ['<div class="bars">']
    for lab, num, den, c in items:
        p = num / den if den else 0
        out.append(f'<div class="bl">{lab}</div><div class="bw"><div class="bb" style="width:{p/maxv*w:.0f}px;background:{c or color}"></div>'
                   f'<span class="bt">{p:.0%} <span class="t">({num}/{den})</span></span></div>')
    return "".join(out) + "</div>"


# ---------------------------------------------------------------- slide 1: methods
def methods_body(scale=1.0):
    q_html = "".join(
        f'<div class="qg"><div class="qh">{g}</div>' + "".join(
            f'<div class="q"><b>{QSHORT[q][0]}</b> <span class="hr">{QSHORT[q][2]}</span><br><span>{esc(QSHORT[q][1])}</span></div>' for q in qs) + '</div>'
        for g, qs in QGROUPS)
    return f"""
<div class="m-grid">
  <div class="card prompt">
    <div class="tag">The prompt (one call per question)</div>
    <p class="mono">{esc(INTRO)}</p>
    <div class="fixed"><div class="tag2">Persona · fixed</div>{esc(PERSONA)}</div>
    <div class="slot"><div class="tag2 acc">Memories · varied (0 to 9)</div>{esc(FACTS_HEADER)}<br>
      – Last night you chose Lyft's "Wait &amp; Save" option: you waited an extra 8 minutes to save $4.<br>
      – On your commute to work you take a toll road that costs $9 and saves you about 15 minutes…</div>
    <p class="mono">{esc(SURVEY_HEADER)}</p>
    <div class="slot q1"><div class="tag2 acc2">Question · 1 of 10</div>In general, how much is one hour of your time worth to you, in dollars?</div>
    <p class="mono">{esc(FORMAT)}</p>
  </div>
  <div class="col">
    <div class="card">
      <div class="tag">What was varied</div>
      <table class="st">
        <tr><th>Stage</th><th>Memory sets</th><th>Samples</th><th>Calls</th></tr>
        <tr><td>1</td><td>None, and each of the 9 alone</td><td>5</td><td>500</td></tr>
        <tr><td>2</td><td>All 36 pairs</td><td>2</td><td>720</td></tr>
        <tr><td>2</td><td>Add memories one at a time (3 random orders) → all 9</td><td>2</td><td>420</td></tr>
      </table>
      <div class="note">Memory order shuffled across samples. Prompt never says the memories are relevant.</div>
    </div>
    <div class="card">
      <div class="tag">The 10 survey questions</div>
      <div class="qs">{q_html}</div>
      <div class="note"><b>Outcome:</b> implied $/hour = dollar answer ÷ time at stake · plus the full thinking trace</div>
    </div>
    <div class="card model"><b>Model:</b> Qwen3-8B (4-bit, MLX), thinking mode on, temperature 0.6 · each question in a fresh call · 1,640 calls</div>
  </div>
</div>"""


SLIDE_CSS = """
*{box-sizing:border-box}body{margin:0;background:#fff;color:#111827;font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.slide{width:1600px;height:900px;padding:44px 56px;overflow:hidden}
h1{font-size:38px;margin:0 0 6px}.sub{font-size:20px;color:#6b7280;margin:0 0 22px}
.m-grid{display:grid;grid-template-columns:760px 1fr;gap:26px}
.card{border:1px solid #e5e7eb;border-radius:12px;padding:16px 18px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.col{display:flex;flex-direction:column;gap:14px}
.tag{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:#6b7280;font-weight:700;margin-bottom:10px}
.tag2{font-size:12px;letter-spacing:.06em;text-transform:uppercase;font-weight:700;color:#6b7280;margin-bottom:4px}
.acc{color:#2563eb}.acc2{color:#b45309}
.prompt{font-size:17px;line-height:1.45}.mono{color:#4b5563;margin:8px 0}
.fixed{background:#f3f4f6;border-radius:8px;padding:10px 12px}
.slot{border:2.5px dashed #2563eb;border-radius:8px;padding:10px 12px;margin:10px 0;background:#eff6ff}
.slot.q1{border-color:#d97706;background:#fffbeb}
table.st{border-collapse:collapse;width:100%;font-size:16px}table.st th{text-align:left;color:#6b7280;font-weight:600;border-bottom:1px solid #e5e7eb;padding:4px 6px}
table.st td{padding:5px 6px;border-bottom:1px solid #f3f4f6}table.st td:nth-child(3),table.st td:nth-child(4),table.st th:nth-child(3),table.st th:nth-child(4){text-align:right}
.note{font-size:14px;color:#6b7280;margin-top:8px}
.qs{display:grid;grid-template-columns:1.25fr 1fr;gap:6px 16px}.qg{display:flex;flex-direction:column;gap:5px}
.qg:nth-child(3){grid-column:2}.qg:nth-child(2){grid-column:2;grid-row:1}.qg:nth-child(1){grid-row:1/3}
.qh{font-size:13px;font-weight:700;color:#b45309;text-transform:uppercase;letter-spacing:.05em}
.q{font-size:14.5px;line-height:1.3}.q span{color:#4b5563}.hr{font-size:12px;background:#fef3c7;color:#92400e!important;border-radius:4px;padding:0 5px}
.model{font-size:15.5px;background:#f9fafb}
"""


def page(title, body, css, extra=""):
    return f'<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title><style>{css}{extra}</style></head><body>{body}</body></html>'


slide1 = page("Methods", f'<div class="slide"><h1>Design: one persona, varied memories, one question per call</h1>'
              f'<p class="sub">Which remembered choices does the model use to answer “what is your time worth?”</p>{methods_body()}</div>', SLIDE_CSS)
slide2 = page("Memories", f'<div class="slide"><h1>Each memory implies a different value of an hour</h1>'
              f'<p class="sub">Most memories are one-sided bounds: a choice reveals that an hour is worth <i>at least</i> or <i>at most</i> some amount.</p>'
              f'{legend(17)}<div style="margin-top:6px">{memory_svg(width=1490, row=64, label_w=650, font=19)}</div></div>', SLIDE_CSS)
(DOCS / "slides/methods.html").write_text(slide1)
(DOCS / "slides/memories.html").write_text(slide2)

# ---------------------------------------------------------------- report
REPORT_CSS = SLIDE_CSS.replace(".slide{width:1600px;height:900px;padding:44px 56px;overflow:hidden}", "") + """
body{background:#fafafa}.wrap{max-width:1120px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:34px}h2{font-size:24px;margin:44px 0 10px;padding-top:10px;border-top:1px solid #e5e7eb}h3{font-size:18px;margin:26px 0 6px}
p,li{font-size:16px;line-height:1.6}.lede{font-size:18px;color:#374151}
.tldr{background:#fff;border:1px solid #e5e7eb;border-left:5px solid #2563eb;border-radius:10px;padding:14px 22px;margin:18px 0}
.fig{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin:14px 0;overflow-x:auto}
.cap{font-size:13.5px;color:#6b7280;margin-top:8px}
blockquote{margin:10px 0;padding:8px 14px;border-left:3px solid #d1d5db;color:#374151;background:#fff;font-size:15px;border-radius:0 8px 8px 0}
table.hm{border-collapse:collapse;font-size:13px}table.hm td,table.hm th{border:1px solid #fff;padding:5px 6px;text-align:center}
table.hm th{font-size:12px;color:#374151;background:#f3f4f6}table.hm td.l{text-align:left;white-space:nowrap;background:#fff;font-size:13px}
table.hm td.t{color:#6b7280;background:#fff;font-size:12px;white-space:nowrap}table.hm td.c{color:#111;min-width:52px}
table.hm td.on{outline:2.5px solid #111;outline-offset:-3px;font-weight:800}
table.tb{border-collapse:collapse;font-size:15px;margin:8px 0}table.tb td,table.tb th{padding:6px 12px;border-bottom:1px solid #e5e7eb;text-align:left}
table.tb th{color:#6b7280;font-weight:600}table.tb td.n{text-align:right;font-variant-numeric:tabular-nums}
.bars{display:grid;grid-template-columns:330px 1fr;gap:6px 12px;align-items:center;font-size:14.5px}
.bw{display:flex;align-items:center;gap:8px}.bb{height:16px;border-radius:3px}.bt{font-size:13.5px}.t{color:#6b7280}
.scaled{width:1024px;height:440px;overflow:hidden}.scaled>.inner{transform:scale(.64);transform-origin:0 0;width:1600px;padding:0 56px}
.files td{font-family:ui-monospace,Menlo,monospace;font-size:13px}
"""

fcol = {"Below both": "#9ca3af", "Equals the floor rate": FLOOR_C, "Equals the ceiling rate": CEIL_C,
        "Between the two": "#2563eb", "Above both": "#6b7280"}
fc_bars = bars([(k, fc[k], fc_n, fcol[k]) for k in ["Below both", "Equals the floor rate", "Equals the ceiling rate", "Between the two", "Above both"]], maxv=.6)
win_bars = bars([(f'<b style="color:{bcol(f)}">{f}</b> {esc(SHORT[f][0])} <span class="t">{SHORT[f][2]}</span>', *wins[f], bcol(f))
                 for f in sorted(V, key=lambda f: -wins[f][0] / max(1, wins[f][1]))], maxv=.5)
copyn_bars = bars([(f"{n} memor{'y' if n == 1 else 'ies'}", a, b, "#2563eb") for n, a, b in copy_by_n], maxv=1.0)
floor_bars = bars([(f'<b style="color:{FLOOR_C}">{f}</b> {esc(SHORT[f][0])} <span class="t">{SHORT[f][2]}</span>', *copy1[f], FLOOR_C)
                   for f in ["H", "C", "D", "F", "G"]], maxv=.9)
ceil_rows = "".join(f'<tr><td><b style="color:{CEIL_C}">{f}</b> {esc(SHORT[f][0])}</td><td>{SHORT[f][2]}</td>'
                    f'<td class="n">{copy1[f][0]}/{copy1[f][1]}</td><td class="n">{trait[f][0]}/{trait[f][1]}</td></tr>' for f in ["B", "E", "I"])
ceil_rows += f'<tr><td class="t">No memory</td><td></td><td class="n">–</td><td class="n">{trait["none"][0]}/{trait["none"][1]}</td></tr>'
fmt = lambda xs: ", ".join(f"${x:g}" for x in xs)
m_none = {q: med(s1_by["none"], q) for q in QORDER}

body = f"""<div class="wrap">
<h1>Which memories does an LLM use to value its time?</h1>
<p class="lede">A thinking model answers “what is an hour of your time worth?” from a persona plus remembered choices,
each of which implies a different dollar value. We vary which memories it sees and ask ten differently framed questions,
each in its own call, and read both the dollar answers and the thinking traces.</p>
<p class="t">Qwen3-8B (4-bit, MLX), thinking on · {len(S1)+len(S2):,} calls · repo <code>agentic-norms-learning</code> · draws from one model configuration, not independent people.</p>

<div class="tldr"><b>Summary</b><ol>
<li><b>“Paid to save time” memories become an exchange rate.</b> The model divides, gets $/hour, and multiplies it into unrelated questions (cleaner: {copy1['H'][0]}/{copy1['H'][1]} answers at exactly $20/h).</li>
<li><b>“Spent time to save money” memories become a personality trait.</b> The trace calls Sam “cost-conscious” in ~95% of calls, and every answer drops, usually below the memory's own number.</li>
<li><b>With several memories it picks one, it doesn't average.</b> 0/{len(multi)} answers equal the mean of the shown rates. The Disney pass ($15) and the cleaner ($20) win most contests; the wage almost never does ({wins['A'][0]}/{wins['A'][1]}).</li>
<li><b>Contradictions are noticed but not resolved.</b> No trace says time might be worth different amounts in different settings.</li>
<li><b>Work is undervalued.</b> Turning down a $29/h shift lowers the price Sam asks for weekend work, and being paid to give up time is priced below paying to save it.</li>
</ol></div>

<h2>1. Design</h2>
<div class="fig"><div class="scaled"><div class="inner">{methods_body()}</div></div></div>
<h3>Each memory implies a value of an hour</h3>
<div class="fig">{legend(14)}{memory_svg(width=1300, row=58, label_w=560, font=17)}
<div class="cap">The memory wording was chosen so every memory implies a different $/hour; a numeric answer can therefore be traced to the memory it came from (±3%). Two memories also carry non-time motives (fun, a date).</div></div>

<h2>2. One memory at a time</h2>
<p>Stage 1: no memory, or exactly one of the nine; 5 samples per memory × question (500 calls).</p>
<div class="fig">{heatmap()}
<div class="cap">Median implied $/hour (answer ÷ time at stake), 5 samples per cell. <b>Boxed</b> = equals the shown memory's rate (±3%). Blue = low, orange = high.</div></div>

<h3>2a. Floor memories turn into a fixed exchange rate</h3>
<p>Share of all 50 answers (10 questions × 5) that equal the memory's rate:</p>
<div class="fig">{floor_bars}</div>
<blockquote>Cleaner, nonstop flight: “$60 divided by 3 hours is $20 per hour. If the nonstop flight saves 3 hours… 3 hours times…” → <b>$60</b></blockquote>
<blockquote>Valet on a date, train delay: “…$210 per hour. If he values his time that high, 5 hours would be 5×210 = $1050. But that seems high…” → <b>$1,050</b> (5 of 5 samples)</blockquote>
<p>The valet memory is used at face value even though it happened on a date; the trace rarely treats the date as a reason to discount it.</p>

<h3>2b. Ceiling memories turn into a trait</h3>
<table class="tb"><tr><th>Memory</th><th>Rate</th><th>Answer = rate</th><th>Trace says “cost-conscious / frugal / budget”</th></tr>{ceil_rows}</table>
<p>Nonstop flight that saves 3 hours: with no memory {fmt(flight_none)}; with the Lyft memory {fmt(flight_B)}.</p>
<blockquote>“The key is that he's shown to be cost-conscious, so he's not going to pay a lot… the answer is $15.”</blockquote>
<p>Both kinds of memory bound the same quantity, yet one is used as a price and the other as a character description.</p>

<h3>2c. Turning down paid work is read backwards</h3>
<p>Sam turned down a Saturday shift at $29/h, so his free Saturday is worth more than $29/h. Lowest pay for a 4-hour Saturday job: {fmt(gig_G)}. Only one sample reaches 4 × $29.</p>
<blockquote>“Since he turned down the higher rate, maybe he would accept something lower, like $50.”</blockquote>

<h3>2d. Being paid to give up time is valued below paying to save time</h3>
<p>With no memory: weekend gig ${m_none['weekend_gig']:.1f}/h and research study ${m_none['research_study']:.0f}/h, versus the general question ${m_none['general']:.0f}/h and the nonstop flight ${m_none['nonstop_flight']:.0f}/h. People usually show the opposite gap (they demand more to give time up).</p>

<h2>3. Several memories at once</h2>
<p>Stage 2: all 36 pairs and three one-at-a-time sequences up to all nine; 2 samples per set × question (1,140 calls).</p>
<h3>3a. It picks one memory and copies its rate</h3>
<p>Share of answers that equal <i>some</i> shown memory's rate, by number of memories:</p>
<div class="fig">{copyn_bars}<div class="cap">0/{len(multi)} answers with 3+ memories equal the average of the shown rates, although {avg_word}/{len(multi)} traces use the word “average”.</div></div>
<h3>3b. Which memory wins</h3>
<p>With 3+ memories: how often the answer equals this memory's rate (and no other), out of the calls where it was shown:</p>
<div class="fig">{win_bars}
<div class="cap">Position doesn't matter: the winner was first / middle / last {pos['first']}/{pos['middle']}/{pos['last']} times versus {exp['first']:.0f}/{exp['middle']:.0f}/{exp['last']:.0f} expected by chance.</div></div>
<p>The two winners are stated in whole hours with easy division ($60 ÷ 3, $30 ÷ 2), and both sit near the model's no-memory default (~$15–20/h). <b>This design can't separate “easiest arithmetic” from “closest to my prior.”</b></p>
<blockquote>All nine memories, general question: “…the answer is $20, based on the cleaner example… the cleaner example is a direct calculation, so that's a strong indicator.”</blockquote>

<h3>3c. Floor + ceiling usually lands below both</h3>
<p>{fc_n} answers had one floor and one ceiling memory:</p>
<div class="fig">{fc_bars}</div>
<p>The ceiling memory's “cost-conscious” reading pulls the answer down past its own number, and also suppresses copying of the floor rate.</p>

<h3>3d. Contradictions are noticed, not resolved</h3>
<p>Lyft (worth ≤ $30/h) and the toll (worth ≥ $36/h) can't both hold for a single hourly value. {bd_flag}/{len(bd)} traces with both flag it, then pick one:</p>
<blockquote>“…$36 per hour… the Lyft example… that's $30. Hmm, conflicting numbers. But maybe he's more like the toll road.”</blockquote>
<p>No trace suggests the standard resolution: commute time and leisure time can be worth different amounts.</p>

<h3>3e. Other carry-overs</h3>
<ul><li>The $210/h valet rate wins only {f_win}/{len(f_multi)} times when other memories are present: it is outvoted, not discounted.</li>
<li>With all nine memories, the weekend gig is {fmt(nine_gig)} for 4 hours ($20/h, the cleaner rate), still below the $29/h shift already refused.</li></ul>

<h2>4. Caveats and next steps</h2>
<ul>
<li>One model (Qwen3-8B, 4-bit), one persona, one wording per memory; 5 samples per cell in stage 1, 2 in stage 2.</li>
<li>Floor vs. ceiling is confounded with topic: every ceiling memory is a small errand. Next: flip direction within one scenario (paid the toll vs. skipped it).</li>
<li>Easy arithmetic vs. closeness to the default: add an easy-arithmetic memory with an unusual rate (e.g. $120 for 2 hours).</li>
<li>Keyword “mentions” are uninformative: nearly every trace restates the memories, so use is measured from the dollar answers.</li>
<li>12/500 stage-1 traces cite an “example answer” or “previous interaction” that doesn't exist.</li>
<li>No human comparison yet; the same prompts can run on Prolific.</li>
</ul>

<h2>Files</h2>
<table class="tb files"><tr><td>runs/s1_single/, runs/s2_combos/</td><td>raw records, answers.csv, summary.md, traces.md</td></tr>
<tr><td>docs/findings_s1_single.md, docs/findings_s2_combos.md</td><td>text findings with quotes</td></tr>
<tr><td>docs/slides/methods.png, docs/slides/memories.png</td><td>slide graphics (1600×900)</td></tr>
<tr><td>scripts/build_report.py</td><td>builds this page; all numbers computed from the run records</td></tr></table>
</div>"""
(DOCS / "report.html").write_text(page("Value of time: findings", body, REPORT_CSS))
print("wrote docs/report.html, docs/slides/methods.html, docs/slides/memories.html")
print("check:", copy1["H"], wins["A"], fc_n, len(multi), avg_match, bd_flag, len(bd), f_win, len(f_multi))
