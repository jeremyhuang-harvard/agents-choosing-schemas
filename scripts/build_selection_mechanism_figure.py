"""Build a data-derived figure on contextual retrieval and exchange-rate selection.

Uses all 500 s1_single calls and all 1,140 s2_combos calls.

    PYTHONPATH=. uv run python scripts/build_selection_mechanism_figure.py
"""
from __future__ import annotations

import collections
import html
import json
import re
from pathlib import Path

from value_of_time.stimuli import FACT_BY_ID, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "docs/figures"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "selection_mechanism.html"

V = {f.id: f.implied_hourly for f in FACT_BY_ID.values()}
PORTABLE = {"C", "D", "F", "H"}  # Stage-1 memories copied in >=36% of calls; G is handled differently.
MEM_NAMES = {
    "B": "Lyft Wait & Save",
    "C": "Disney pass",
    "D": "Toll road",
    "F": "Valet",
    "H": "Cleaner",
}
MEM_RATE = {"B": "$30/h", "C": "$15/h", "D": "$36/h", "F": "$210/h", "H": "$20/h"}
MEM_COLOR = {"B": "#b84c32", "C": "#1d6b57", "D": "#32775f", "F": "#7c5b1c", "H": "#235f79"}
QORDER = [q.id for q in QUESTIONS]
QSHORT = {
    "general": "General",
    "weekend_gig": "Saturday job",
    "research_study": "Study",
    "nonstop_flight": "Flight",
    "priority_pickup": "Rideshare",
    "grocery_delivery": "Groceries",
    "furniture_assembly": "Bookshelf",
    "theme_park": "Theme park",
    "train_delay": "Train delay",
    "volunteer_or_donate": "Donation",
}

def load(path: Path):
    out = {}
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            if r["status"] == "ok":
                out[r["cell_id"]] = r
    return list(out.values())

S1 = load(ROOT / "runs/s1_single/records.jsonl")
S2 = load(ROOT / "runs/s2_combos/records.jsonl")


def hit(hourly, fact):
    return hourly is not None and abs(hourly - V[fact]) / V[fact] <= 0.03


def winner(r):
    matches = [f for f in r["fact_set"] if hit(r["implied_hourly"], f)]
    return matches[0] if len(matches) == 1 else None


def pct(n, d):
    return 100 * n / d if d else 0

# Panel A: all multi-memory calls in which each memory is present.
sel = {}
for f in MEM_NAMES:
    for q in QORDER:
        rows = [r for r in S2 if len(r["fact_set"]) >= 2 and f in r["fact_set"] and r["question"] == q]
        n = sum(winner(r) == f for r in rows)
        sel[(f, q)] = (n, len(rows))

# Stage-1 Lyft mechanism.
trait_pat = re.compile(r"cost[- ]conscious|frugal|budget[- ]conscious|thrifty|careful with money|money[- ]conscious|saving money", re.I)
lyft_s1 = [r for r in S1 if r["fact_set"] == ["B"]]
lyft_trait = sum(bool(trait_pat.search(r["thinking"])) for r in lyft_s1)
lyft_copy = sum(hit(r["implied_hourly"], "B") for r in lyft_s1)
lyft_ride = [r for r in S1 if r["fact_set"] == ["B"] and r["question"] == "priority_pickup"]
lyft_ride_copy = sum(hit(r["implied_hourly"], "B") for r in lyft_ride)

# Panel B: all s2 calls, grouped by number of portable numerical memories shown.
by_k = []
for k in range(5):
    rows = [r for r in S2 if len(set(r["fact_set"]) & PORTABLE) == k]
    portable_selected = sum(winner(r) in PORTABLE for r in rows)
    any_selected = sum(bool([f for f in r["fact_set"] if hit(r["implied_hourly"], f)]) for r in rows)
    by_k.append((k, portable_selected, any_selected, len(rows)))

# Stage-1 evidence defining the portable memories.
s1_copy = {}
for f in V:
    rows = [r for r in S1 if r["fact_set"] == [f]]
    s1_copy[f] = (sum(hit(r["implied_hourly"], f) for r in rows), len(rows))


def color(value):
    # white -> dark green for 0..100
    t = max(0, min(1, value / 100))
    a = (247, 244, 237)
    b = (29, 102, 84)
    rgb = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"rgb{rgb}"

heat_rows = []
for f in ["B", "C", "D", "F", "H"]:
    cells = []
    for q in QORDER:
        n, d = sel[(f, q)]
        p = pct(n, d)
        topical = (f == "B" and q == "priority_pickup") or (f == "C" and q == "theme_park") or (f == "H" and q == "furniture_assembly")
        cells.append(
            f'<td class="heat {"topical" if topical else ""}" style="background:{color(p)};color:{"white" if p >= 48 else "#17211f"}">'
            f'<b>{p:.0f}%</b><small>{n}/{d}</small></td>'
        )
    heat_rows.append(
        f'<tr><td class="memlab"><span style="background:{MEM_COLOR[f]}">{f}</span><b>{html.escape(MEM_NAMES[f])}</b><small>{MEM_RATE[f]}</small></td>{"".join(cells)}</tr>'
    )

bar_rows = []
for k, portable, any_selected, total in by_k:
    pp = pct(portable, total)
    ap = pct(any_selected, total)
    bar_rows.append(f"""
    <div class="barrow">
      <div class="k"><b>{k}</b><span>portable rate{'s' if k != 1 else ''}</span><small>n={total}</small></div>
      <div class="tracks">
        <div class="metric"><span class="mlabel">Portable selected</span><div class="track"><div class="fill portable" style="width:{pp}%"></div></div><span class="mvalue"><b>{pp:.0f}%</b><small>{portable}/{total}</small></span></div>
        <div class="metric"><span class="mlabel">Any rate copied</span><div class="track"><div class="fill any" style="width:{ap}%"></div></div><span class="mvalue"><b>{ap:.0f}%</b><small>{any_selected}/{total}</small></span></div>
      </div>
    </div>""")

portable_definition = " · ".join(f"{f} {s1_copy[f][0]}/50" for f in ["C", "D", "F", "H"])

DOC = f"""<!doctype html><html><head><meta charset="utf-8"><title>Context retrieves memories; portable rates dominate</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1ede4;color:#17211f;font-family:Arial,Helvetica,sans-serif}}.figure{{width:1600px;height:1200px;padding:42px 52px 34px;overflow:hidden}}
.kicker{{font-size:14px;text-transform:uppercase;letter-spacing:.14em;color:#a8492f;font-weight:800}}h1{{font-family:Georgia,serif;font-size:43px;line-height:1.08;margin:7px 0 8px}}.dek{{font-family:Georgia,serif;font-size:20px;color:#4c5954;margin:0 0 22px}}
.grid{{display:grid;grid-template-columns:990px 1fr;gap:25px}}.panel{{background:#fffdf8;border:1px solid #d7d0c3;padding:22px 24px}}.panel h2{{font-family:Georgia,serif;font-size:25px;margin:0 0 5px}}.sub{{color:#5d6965;font-size:14px;margin:0 0 15px}}
table{{border-collapse:separate;border-spacing:3px;width:100%;table-layout:fixed}}th{{font-size:11px;color:#52605b;height:65px;vertical-align:bottom;line-height:1.1}}th:first-child{{width:168px;text-align:left}}.memlab{{background:#f0ebe1;padding:7px 8px;vertical-align:middle}}.memlab span{{display:inline-grid;place-items:center;color:white;border-radius:50%;width:25px;height:25px;font-weight:800;float:left;margin:4px 7px 12px 0}}.memlab b{{display:block;font-size:13px}}.memlab small{{display:block;color:#66706c;margin-top:2px}}.heat{{height:61px;text-align:center;border:2px solid transparent}}.heat b{{display:block;font-size:17px}}.heat small{{display:block;font-size:10px;opacity:.8;margin-top:2px}}.heat.topical{{border-color:#bd7a1d;box-shadow:inset 0 0 0 1px white}}
.lyft{{margin-top:15px;background:#ece3d3;padding:13px 16px;display:grid;grid-template-columns:145px 1fr;gap:15px;align-items:center}}.lyft strong{{font-family:Georgia,serif;font-size:22px;color:#8f3d28}}.lyft p{{font-size:14px;margin:0;line-height:1.42}}.lyft b{{color:#8f3d28}}
.barbox{{display:flex;flex-direction:column;gap:15px;margin-top:19px}}.barrow{{display:grid;grid-template-columns:76px 1fr;gap:10px;align-items:center}}.k{{text-align:center;border-right:1px solid #d7d0c3;padding-right:8px}}.k b{{display:block;font-family:Georgia,serif;font-size:29px;color:#1d6654}}.k span{{display:block;font-size:10px;font-weight:700}}.k small{{font-size:9px;color:#68736f}}.tracks{{display:flex;flex-direction:column;gap:5px}}.metric{{display:grid;grid-template-columns:91px 1fr 58px;gap:6px;align-items:center}}.mlabel{{font-size:10px;color:#53605b;text-align:right}}.track{{height:19px;background:#eee9df;overflow:hidden}}.fill{{height:100%}}.fill.portable{{background:#1d6654}}.fill.any{{background:#b7a47c}}.mvalue{{font-size:12px;white-space:nowrap}}.mvalue b{{font-size:13px}}.mvalue small{{display:block;font-size:8px;color:#68736f}}
.legend{{display:flex;gap:17px;margin-top:15px;font-size:12px;color:#5d6965}}.legend i{{display:inline-block;width:13px;height:13px;margin-right:5px;vertical-align:-2px}}.conclusion{{margin-top:17px;border-top:1px solid #d7d0c3;padding-top:14px}}.conclusion h3{{font-family:Georgia,serif;font-size:21px;margin:0 0 7px}}.conclusion p{{font-size:14px;line-height:1.42;margin:0 0 8px}}.definition{{font-size:11px!important;color:#68736f}}
.bottom{{display:grid;grid-template-columns:1fr 1fr;gap:25px;margin-top:19px}}.take{{background:#17211f;color:#fff;padding:17px 21px;font-family:Georgia,serif;font-size:20px;line-height:1.3}}.take b{{color:#e4b65c}}.note{{padding:15px 19px;border-top:2px solid #17211f;font-size:12px;color:#55615d;line-height:1.42}}
</style></head><body><div class="figure">
<div class="kicker">All 1,640 simulation calls · not reconstructed from a prior figure</div>
<h1>Context retrieves a specific memory; several portable rates turn the task into selection</h1>
<p class="dek">The Lyft episode is usually represented as a personality trait—but a rideshare question activates its exact $30/hour rate. More broadly, once the bank contains several memories that can serve as exchange rates, the model usually chooses one.</p>
<div class="grid">
<section class="panel"><h2>A. Which memory rate is selected when that memory is available?</h2><p class="sub">All multi-memory calls (n = 1,140). Each cell conditions on the named memory being shown; denominators differ because the ladder design shows memories with different frequencies.</p>
<table><thead><tr><th>Memory available</th>{''.join(f'<th>{QSHORT[q]}</th>' for q in QORDER)}</tr></thead><tbody>{''.join(heat_rows)}</tbody></table>
<div class="lyft"><strong>Lyft changes role</strong><p><b>Alone:</b> the trace says “cost-conscious” in {lyft_trait}/50 calls, while only {lyft_copy}/50 final answers copy $30/h. <b>On the rideshare question:</b> $30/h appears in {lyft_ride_copy}/5 calls when Lyft is alone and <b>{sel[("B","priority_pickup")][0]}/{sel[("B","priority_pickup")][1]} (81%)</b> when other memories compete.</p></div>
</section>
<section class="panel"><h2>B. Does an available exchange rate become the default move?</h2><p class="sub">All combination calls, grouped by how many “portable numerical memories” are in the bank.</p>
<div class="barbox">{''.join(bar_rows)}</div>
<div class="legend"><span><i style="background:#1d6654"></i>one of C/D/F/H selected</span><span><i style="background:#b7a47c"></i>any displayed rate copied</span></div>
<div class="conclusion"><h3>Not always—but dominant once there are several.</h3><p>With one portable rate present, it is selected in 46% of calls. With two to four, a portable rate is selected in <b>73–76%</b>, and some displayed rate is copied in <b>81–89%</b>.</p><p class="definition">Portable rates are defined from Stage 1: memories repeatedly copied across questions when shown alone—{portable_definition}. The declined shift G is excluded because it is usually interpreted backwards rather than as a portable rate.</p></div>
</section></div>
<div class="bottom"><div class="take"><b>Specificity:</b> a close contextual cue can retrieve a memory that otherwise enters reasoning only as a trait. <b>Default operation:</b> when several usable numerical memories are available, the model usually solves the problem by selecting one exchange rate rather than integrating the evidence.</div><div class="note"><b>Reading limits.</b> “Selected” means the final implied $/hour matches exactly one displayed memory within ±3%. This is behavioral matching, not proof that the trace is causally faithful. The Lyft heatmap uses 36 calls per question; C, D, F, and H use 52, 30, 34, and 48 respectively. The portable-rate classification is empirical and post hoc, so the next experiment should preregister the class and repeat targeted question–memory contrasts.</div></div>
</div></body></html>"""

OUT.write_text(DOC, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
print("lyft", lyft_trait, lyft_copy, lyft_ride_copy, sel[("B", "priority_pickup")])
print("by_k", by_k)
