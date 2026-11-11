"""Build a one-page appendix table for all nine memories.

    PYTHONPATH=. uv run python scripts/build_all_memory_appendix.py
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from value_of_time.stimuli import FACT_BY_ID, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/figures/all_memory_selection_appendix.html"
OUT.parent.mkdir(parents=True, exist_ok=True)
V = {f.id: f.implied_hourly for f in FACT_BY_ID.values()}
NAMES = {
    "A": "Wage", "B": "Lyft Wait & Save", "C": "Disney pass", "D": "Toll road",
    "E": "Free-parking search", "F": "Valet on a date", "G": "Declined Saturday shift",
    "H": "Apartment cleaner", "I": "Cheaper gas station",
}
RATES = {"A":"$19/h", "B":"≤$30/h", "C":"≥$15/h", "D":"≥$36/h", "E":"≤$45/h", "F":"≥$210/h", "G":"≥$29/h", "H":"≥$20/h", "I":"≤$18/h"}
QSHORT = {
    "general":"General", "weekend_gig":"Saturday job", "research_study":"Study",
    "nonstop_flight":"Flight", "priority_pickup":"Rideshare", "grocery_delivery":"Groceries",
    "furniture_assembly":"Bookshelf", "theme_park":"Theme park", "train_delay":"Train delay",
    "volunteer_or_donate":"Donation",
}
QORDER = [q.id for q in QUESTIONS]

def load(path):
    out = {}
    for line in open(path):
        r = json.loads(line)
        if r["status"] == "ok":
            out[r["cell_id"]] = r
    return list(out.values())

S2 = load(ROOT / "runs/s2_combos/records.jsonl")

def hit(hourly, fact):
    return hourly is not None and abs(hourly - V[fact]) / V[fact] <= .03

def winner(r):
    matches = [f for f in r["fact_set"] if hit(r["implied_hourly"], f)]
    return matches[0] if len(matches) == 1 else None

def shade(p):
    t = max(0, min(1, p / 100))
    low, high = (249,246,239), (26,94,77)
    rgb = tuple(round(low[i] + (high[i]-low[i])*t) for i in range(3))
    return f"rgb{rgb}"

rows_html=[]
overall=[]
for f in "ABCDEFGHI":
    cells=[]
    total_w=total_n=0
    for q in QORDER:
        rs=[r for r in S2 if f in r["fact_set"] and r["question"]==q]
        w=sum(winner(r)==f for r in rs); n=len(rs); p=100*w/n
        total_w+=w; total_n+=n
        topical = ((f=="A" and q in {"general","weekend_gig","research_study","volunteer_or_donate"}) or
                   (f=="B" and q=="priority_pickup") or (f=="C" and q=="theme_park") or
                   (f=="D" and q in {"nonstop_flight","priority_pickup","train_delay"}) or
                   (f=="E" and q=="grocery_delivery") or (f=="F" and q=="theme_park") or
                   (f=="G" and q in {"weekend_gig","research_study"}) or
                   (f=="H" and q in {"grocery_delivery","furniture_assembly"}) or
                   (f=="I" and q=="grocery_delivery"))
        cells.append(f'<td class="heat {"topical" if topical else ""}" style="background:{shade(p)};color:{"white" if p>=48 else "#17211f"}"><b>{p:.0f}%</b><small>{w}/{n}</small></td>')
    op=100*total_w/total_n
    overall.append((f,total_w,total_n,op))
    rows_html.append(f'<tr><td class="memory"><span>{f}</span><b>{html.escape(NAMES[f])}</b><small>{RATES[f]}</small></td>{"".join(cells)}<td class="overall" style="background:{shade(op)};color:{"white" if op>=48 else "#17211f"}"><b>{op:.0f}%</b><small>{total_w}/{total_n}</small></td></tr>')

ranked=sorted(overall,key=lambda x:-x[3])
rank_html="".join(f'<span><b>{f}</b> {NAMES[f]}: {p:.0f}%</span>' for f,w,n,p in ranked)

DOC=f"""<!doctype html><html><head><meta charset="utf-8"><title>Appendix: all-memory selection table</title><style>
@page{{size:Letter landscape;margin:.28in}}*{{box-sizing:border-box}}body{{margin:0;background:#f2eee6;color:#17211f;font-family:Arial,Helvetica,sans-serif}}.page{{width:10.44in;height:7.94in;margin:0 auto;padding:.15in .18in;background:#fffdf8;overflow:hidden}}
.kicker{{font-size:7.5pt;text-transform:uppercase;letter-spacing:.12em;color:#a8492f;font-weight:800}}h1{{font-family:Georgia,serif;font-size:20pt;line-height:1.05;margin:4px 0 4px}}.dek{{font-family:Georgia,serif;font-size:9.5pt;color:#4f5a56;margin:0 0 8px}}
table{{width:100%;border-collapse:separate;border-spacing:2px;table-layout:fixed}}th{{font-size:6.7pt;color:#52605b;height:31px;vertical-align:bottom;line-height:1.05;padding:1px}}th:first-child{{width:1.31in;text-align:left}}th:last-child{{width:.61in}}td{{height:39px;text-align:center;padding:2px}}.memory{{text-align:left;background:#eee8dd;padding:4px 5px}}.memory span{{display:inline-grid;place-items:center;float:left;width:20px;height:20px;border-radius:50%;background:#17211f;color:white;font-size:7pt;font-weight:800;margin:2px 5px 9px 0}}.memory b{{display:block;font-size:7.4pt;line-height:1.05}}.memory small{{display:block;font-size:6.4pt;color:#63706b;margin-top:2px}}.heat,.overall{{border:1.5px solid transparent}}.heat.topical{{border-color:#bc7920}}.heat b,.overall b{{display:block;font-size:8.5pt}}.heat small,.overall small{{display:block;font-size:5.8pt;opacity:.82}}.overall{{border-left:3px solid #17211f}}
.legend{{display:flex;gap:15px;align-items:center;margin:7px 0 5px;font-size:6.8pt;color:#59645f}}.grad{{width:90px;height:9px;background:linear-gradient(90deg,rgb(249,246,239),rgb(26,94,77));border:1px solid #d8d1c5}}.box{{width:10px;height:10px;border:2px solid #bc7920}}.summary{{display:grid;grid-template-columns:1.28fr .72fr;gap:12px;margin-top:6px}}.finding{{background:#17211f;color:white;padding:8px 10px;font-family:Georgia,serif;font-size:9.2pt;line-height:1.3}}.finding b{{color:#e4b65c}}.rank{{background:#eee8dd;padding:7px 9px;font-size:6.7pt;line-height:1.35}}.rank strong{{display:block;font-family:Georgia,serif;font-size:8.5pt;margin-bottom:2px}}.rank span{{display:block}}.foot{{border-top:1px solid #cfc7b9;margin-top:6px;padding-top:4px;font-size:6.2pt;color:#5c6762;line-height:1.25}}
@media screen{{body{{padding:18px}}.page{{box-shadow:0 4px 25px rgba(0,0,0,.14)}}}}
</style></head><body><div class="page"><div class="kicker">Appendix · all 1,140 multi-memory calls</div><h1>How often is each displayed memory selected, by question?</h1><p class="dek">Each cell conditions on that memory being present. “Selected” means the final implied $/hour uniquely matches that memory’s rate within ±3%. The fraction beneath the percentage is selected calls / calls where shown.</p>
<table><thead><tr><th>Memory shown</th>{''.join(f'<th>{QSHORT[q]}</th>' for q in QORDER)}<th>All questions</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table>
<div class="legend"><span class="grad"></span><span>Darker = selected more often</span><span class="box"></span><span>Gold outline = pre-run domain/topic match</span><span>Denominator per question: A 32 · B 36 · C 52 · D 30 · E 48 · F 34 · G 36 · H 48 · I 48</span></div>
<div class="summary"><div class="finding"><b>Yes, most omitted memories are being crushed—but not all in the same way.</b> C (Disney) and H (cleaner) dominate overall. B (Lyft) and D (toll) are weaker globally but activate in matching contexts. A (wage), E (parking search), G (declined shift), and I (gas) almost never control the final number; F (valet) is uncommon overall but activates strongly for rideshare.</div><div class="rank"><strong>Overall selection when shown</strong>{rank_html}</div></div>
<div class="foot">Source: <code>runs/s2_combos/records.jsonl</code>. The design includes all 36 exact pairs plus three memory-addition ladders, so memories appear with different frequencies. Overall percentages therefore summarize this experimental mix, not a population frequency. Rows use all calls in which the named memory was present; exact pair-question cells alone have two repetitions.</div></div></body></html>"""
OUT.write_text(DOC,encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
print("overall",ranked)
