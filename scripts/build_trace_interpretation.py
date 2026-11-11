"""Build a presentation-ready HTML interpreting the thinking traces.

    PYTHONPATH=. uv run python scripts/build_trace_interpretation.py
"""
from __future__ import annotations

import html
import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/trace_interpretation.html"
V = {"A":19.23,"B":30.0,"C":15.0,"D":36.0,"E":45.0,"F":210.0,"G":28.85,"H":20.0,"I":18.0}
NAMES = {"A":"Wage","B":"Lyft","C":"Disney","D":"Toll","E":"Free parking","F":"Valet","G":"Declined shift","H":"Cleaner","I":"Gas station"}
RATE_PAT = {
    "A": r"19\.2|19 (per|an|/) ?h", "B": r"\$?30(\.0+)? ?(per|an|/|a) ?h",
    "C": r"\$?15(\.0+)? ?(per|an|/|a) ?h", "D": r"\$?36(\.0+)? ?(per|an|/|a) ?h",
    "E": r"\$?45(\.0+)? ?(per|an|/|a) ?h", "F": r"\$?210(\.0+)? ?(per|an|/|a) ?h",
    "G": r"\$?29(\.0+)? ?(per|an|/|a) ?h|28\.8", "H": r"\$?20(\.0+)? ?(per|an|/|a) ?h",
    "I": r"\$?18(\.0+)? ?(per|an|/|a) ?h",
}
TRAIT = re.compile(r"cost[- ]conscious|frugal|budget[- ]conscious|thrifty|careful with money|money[- ]conscious|saving money", re.I)
MOVES = {
    "Calls Sam cost-conscious / frugal": TRAIT.pattern,
    "Flags conflicting memories": r"contradict|inconsisten|conflict|doesn.t add up|mixed signal",
    "Mentions averaging": r"\baverag(e|ing)\b",
    "Says value depends on context": r"depends on (the )?(context|situation|activity)|different (contexts|situations)|varies (by|with|depending)",
}

def load(path):
    out={}
    for line in open(path):
        r=json.loads(line)
        if r["status"]=="ok": out[r["cell_id"]]=r
    return list(out.values())

S1=load(ROOT/"runs/s1_single/records.jsonl")
S2=load(ROOT/"runs/s2_combos/records.jsonl")
ALL=S1+S2
BY_ID={r["cell_id"]:r for r in ALL}

def hit(hourly,f): return hourly is not None and abs(hourly-V[f])/V[f] <= .03

def clean(text): return re.sub(r"\s+"," ",text).strip()

def median_answer(fact_set,q):
    return st.median(r["answer"] for r in S1 if r["fact_set"]==fact_set and r["question"]==q)

# Example 1: trait inference.
baseline_flight=median_answer([],"nonstop_flight")
lyft_flight=median_answer(["B"],"nonstop_flight")
reduction=1-lyft_flight/baseline_flight
lyft_rows=[r for r in S1 if r["fact_set"]==["B"]]
lyft_trait=sum(bool(TRAIT.search(r["thinking"])) for r in lyft_rows)
lyft_compute=sum(bool(re.search(RATE_PAT["B"],r["thinking"],re.I)) for r in lyft_rows)
lyft_select=sum(hit(r["implied_hourly"],"B") for r in lyft_rows)
lyft_flight_values=[r["answer"] for r in S1 if r["fact_set"]==["B"] and r["question"]=="nonstop_flight"]

# Example 2: direct copy.
cleaner_rows=[r for r in S1 if r["fact_set"]==["H"]]
cleaner_compute=sum(bool(re.search(RATE_PAT["H"],r["thinking"],re.I)) for r in cleaner_rows)
cleaner_select=sum(hit(r["implied_hourly"],"H") for r in cleaner_rows)
cleaner_flight=[r for r in cleaner_rows if r["question"]=="nonstop_flight"]
cleaner_flight_select=sum(hit(r["implied_hourly"],"H") for r in cleaner_flight)

# All calls: rate computed in trace versus used in final answer.
comp_use=[]
for f in V:
    rs=[r for r in ALL if f in r["fact_set"]]
    comp=sum(bool(re.search(RATE_PAT[f],r["thinking"],re.I)) for r in rs)
    used=sum(hit(r["implied_hourly"],f) for r in rs)
    both=sum(bool(re.search(RATE_PAT[f],r["thinking"],re.I)) and hit(r["implied_hourly"],f) for r in rs)
    comp_use.append((f,comp,len(rs),used,both))

# Trace length and final copying by memory count.
by_n=[]
for n in range(10):
    rs=[r for r in ALL if len(r["fact_set"])==n]
    if not rs: continue
    words=st.median(len(r["thinking"].split()) for r in rs)
    copied=sum(any(hit(r["implied_hourly"],f) for f in r["fact_set"]) for r in rs)/len(rs) if n else 0
    by_n.append((n,len(rs),words,copied))

many=[r for r in S2 if len(r["fact_set"])>=3]
move_stats=[]
for label,pat in MOVES.items():
    k=sum(bool(re.search(pat,r["thinking"],re.I)) for r in many)
    move_stats.append((label,k,len(many)))
avg_final=sum(
    r["implied_hourly"] is not None and abs(r["implied_hourly"]-st.mean(V[f] for f in r["fact_set"]))/st.mean(V[f] for f in r["fact_set"])<=.03
    for r in many
)

# Quote excerpts are fixed to verified records, shortened with ellipses for presentation.
trait_quote=("The key is that he's shown to be cost-conscious, so he's not going to pay a lot. "
             "But 3 hours is significant. Maybe he would pay up to $15. So the answer is 15.")
direct_quote=("He pays a cleaner $60 for a job that would take 3 hours… $60 divided by 3 hours is $20 per hour. "
              "If the nonstop flight saves 3 hours… 3 hours would be $60.")
match_quote=("He saved $4 by waiting 8 minutes… the value of 10 minutes is (4/8) × 10 = $5. "
             "Therefore, he would pay up to $5 extra.")
choice_quote=("The numbers vary… I think the answer is $20, based on the cleaner example… "
              "the cleaner example is a direct calculation, so that's a strong indicator.")

# SVG dumbbell: compute versus use.
W,H=930,400; left=185; right=885; top=34; row=39
x=lambda p:left+(right-left)*p/100
svg=[f'<svg viewBox="0 0 {W} {H}" width="100%" aria-label="Rate computed versus used">']
for tick in range(0,101,20):
    svg.append(f'<line x1="{x(tick):.1f}" y1="22" x2="{x(tick):.1f}" y2="374" stroke="#ded8cc"/><text x="{x(tick):.1f}" y="15" text-anchor="middle" font-size="11" fill="#66716d">{tick}%</text>')
for i,(f,comp,n,used,both) in enumerate(sorted(comp_use,key=lambda z:-(z[3]/z[2]))):
    y=top+i*row
    cp=100*comp/n; up=100*used/n
    svg.append(f'<text x="5" y="{y+5}" font-size="13" fill="#17211f"><tspan font-weight="700">{f}</tspan> {html.escape(NAMES[f])}</text>')
    svg.append(f'<line x1="{x(min(cp,up)):.1f}" y1="{y}" x2="{x(max(cp,up)):.1f}" y2="{y}" stroke="#bdb4a5" stroke-width="3"/>')
    svg.append(f'<circle cx="{x(cp):.1f}" cy="{y}" r="7" fill="#b47b1d"/><text x="{x(cp):.1f}" y="{y-10}" text-anchor="middle" font-size="10" fill="#76500e">{cp:.0f}%</text>')
    svg.append(f'<circle cx="{x(up):.1f}" cy="{y}" r="7" fill="#1d6654"/><text x="{x(up):.1f}" y="{y+17}" text-anchor="middle" font-size="10" fill="#174d40">{up:.0f}%</text>')
svg.append('</svg>')
dumbbell=''.join(svg)

# SVG lines: trace length and copying by number of memories.
CW,CH=920,310; pl=55; pr=25; pt=28; pb=45
xx=lambda n:pl+(CW-pl-pr)*n/9
ywords=lambda v:pt+(CH-pt-pb)*(1450-v)/(1450-450)
ycopy=lambda v:pt+(CH-pt-pb)*(1-v)
line=[f'<svg viewBox="0 0 {CW} {CH}" width="100%">']
for p in [0,.25,.5,.75,1]:
    yy=ycopy(p); line.append(f'<line x1="{pl}" y1="{yy:.1f}" x2="{CW-pr}" y2="{yy:.1f}" stroke="#e1dbd0"/><text x="{pl-8}" y="{yy+4:.1f}" text-anchor="end" font-size="10" fill="#69736f">{p:.0%}</text>')
pts_copy=' '.join(f'{xx(n):.1f},{ycopy(c):.1f}' for n,_,_,c in by_n)
pts_words=' '.join(f'{xx(n):.1f},{ywords(w):.1f}' for n,_,w,_ in by_n)
line.append(f'<polyline points="{pts_copy}" fill="none" stroke="#1d6654" stroke-width="4"/>')
line.append(f'<polyline points="{pts_words}" fill="none" stroke="#b47b1d" stroke-width="4"/>')
for n,nn,w,c in by_n:
    line.append(f'<circle cx="{xx(n):.1f}" cy="{ycopy(c):.1f}" r="5" fill="#1d6654"/><text x="{xx(n):.1f}" y="{ycopy(c)-9:.1f}" text-anchor="middle" font-size="10" fill="#174d40">{c:.0%}</text>')
    line.append(f'<circle cx="{xx(n):.1f}" cy="{ywords(w):.1f}" r="5" fill="#b47b1d"/><text x="{xx(n):.1f}" y="{ywords(w)+17:.1f}" text-anchor="middle" font-size="10" fill="#76500e">{w:.0f}</text>')
    line.append(f'<text x="{xx(n):.1f}" y="{CH-14}" text-anchor="middle" font-size="11" fill="#59645f">{n}</text>')
line.append(f'<text x="{CW/2}" y="{CH-1}" text-anchor="middle" font-size="11" fill="#59645f">number of memories shown</text></svg>')
line_svg=''.join(line)

move_html=''.join(f'<div class="move"><span>{html.escape(label)}</span><div><i style="width:{100*k/n:.1f}%"></i></div><b>{100*k/n:.0f}%</b><small>{k}/{n}</small></div>' for label,k,n in move_stats)

DOC=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>How the model chooses a value-of-time solution</title><style>
:root{{--paper:#f2eee5;--surface:#fffdf8;--ink:#17211f;--muted:#5d6965;--line:#d8d0c3;--green:#1d6654;--gold:#b47b1d;--rust:#a8492f;--blue:#2c647b}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif;line-height:1.48}}nav{{position:sticky;top:0;z-index:5;background:rgba(242,238,229,.95);border-bottom:1px solid var(--line)}}nav div{{max-width:1160px;margin:auto;padding:10px 24px;display:flex;gap:18px}}nav a{{color:var(--muted);text-decoration:none;font-size:13px}}.wrap{{max-width:1160px;margin:auto;padding:42px 24px 90px}}.kicker{{font-size:12px;text-transform:uppercase;letter-spacing:.13em;color:var(--rust);font-weight:800}}h1,h2,h3{{font-family:Georgia,serif;line-height:1.1}}h1{{font-size:55px;max-width:950px;margin:10px 0 16px}}h2{{font-size:38px;margin:0 0 12px}}h3{{font-size:24px;margin:0 0 8px}}.lede{{font-family:Georgia,serif;font-size:22px;color:#45514d;max-width:880px}}section{{padding:65px 0;border-bottom:1px solid var(--line)}}.thesis{{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-top:28px}}.thesis div{{background:var(--surface);border-top:4px solid var(--ink);padding:20px}}.thesis b{{display:block;font-family:Georgia,serif;font-size:21px;margin-bottom:6px}}.thesis span{{color:var(--muted)}}
.mode-grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}.mode{{background:var(--surface);border:1px solid var(--line);padding:25px}}.mode.trait{{border-top:6px solid var(--rust)}}.mode.rate{{border-top:6px solid var(--green)}}.path{{display:flex;align-items:center;gap:8px;margin:17px 0;flex-wrap:wrap}}.node{{padding:8px 10px;background:#eee8dd;font-weight:700;font-size:13px}}.arrow{{color:var(--muted)}}.statline{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:17px 0}}.stat{{background:#eee8dd;padding:10px;text-align:center}}.stat b{{display:block;font-family:Georgia,serif;font-size:25px;color:var(--rust)}}.rate .stat b{{color:var(--green)}}.stat small{{color:var(--muted)}}blockquote{{font-family:Georgia,serif;font-size:18px;line-height:1.45;margin:17px 0 0;padding:16px 0 0;border-top:1px solid var(--line)}}.answers{{font-size:13px;color:var(--muted);margin-top:9px}}.warning{{background:#e9dfcc;padding:18px 22px;margin-top:20px;font-size:17px}}.warning b{{font-family:Georgia,serif;font-size:21px}}
.chart{{background:var(--surface);border:1px solid var(--line);padding:22px;margin-top:18px}}.legend{{display:flex;gap:20px;color:var(--muted);font-size:13px}}.legend i{{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:5px}}.chart-note{{font-size:13px;color:var(--muted);margin:7px 0 0}}.split{{display:grid;grid-template-columns:1.15fr .85fr;gap:22px}}.quote-card{{background:#17211f;color:white;padding:25px}}.quote-card .kicker{{color:#e4b65c}}.quote-card blockquote{{border-color:#5a6461;font-size:20px}}.quote-card p{{color:#d1d7d4}}.callout{{background:var(--surface);border:1px solid var(--line);padding:25px}}.callout h3{{color:var(--green)}}
.move-list{{display:grid;gap:10px;margin-top:20px}}.move{{display:grid;grid-template-columns:220px 1fr 46px 55px;gap:9px;align-items:center;font-size:13px}}.move>div{{height:17px;background:#e8e2d8}}.move i{{display:block;height:100%;background:var(--blue)}}.move b{{font-size:14px}}.move small{{color:var(--muted)}}.conclusions{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:25px}}.conclusions article{{background:var(--surface);padding:22px;border:1px solid var(--line)}}.conclusions strong{{font-family:Georgia,serif;font-size:24px;display:block;margin-bottom:7px}}.caveat{{margin-top:22px;padding-top:14px;border-top:2px solid var(--ink);color:var(--muted);font-size:14px}}code{{background:#e6e0d5;padding:2px 4px}}@media(max-width:820px){{h1{{font-size:42px}}.thesis,.mode-grid,.split,.conclusions{{grid-template-columns:1fr}}.move{{grid-template-columns:150px 1fr 40px}}.move small{{display:none}}}}@media print{{nav{{display:none}}body{{background:white}}section{{break-before:page}}section:first-of-type{{break-before:auto}}.chart,.mode,.quote-card{{break-inside:avoid}}}}
</style></head><body><nav><div><a href="#modes">Two solution modes</a><a href="#dominance">Computed vs used</a><a href="#competition">Multiple memories</a><a href="#conclusions">Conclusions</a></div></nav><main class="wrap"><header><div class="kicker">Thinking-trace interpretation · all 1,640 calls</div><h1>How does the model decide how to solve the value-of-time problem?</h1><p class="lede">The traces suggest a representation-selection process. A memory is first translated into either a description of the person or a portable numerical rule. The model then answers using that representation—often without combining the other evidence.</p><div class="thesis"><div><b>Episode → personality</b><span>“Sam waited to save money” becomes “Sam is frugal,” producing an ordinal downward adjustment rather than a calculation.</span></div><div><b>Episode → exchange rate</b><span>“Sam paid $60 to save three hours” becomes $20/hour, which is multiplied into a new problem.</span></div><div><b>Several memories → selection</b><span>The trace considers multiple candidates, but usually ends by choosing one convenient rate rather than integrating them.</span></div></div></header>
<section id="modes"><div class="kicker">1 · Two solution modes</div><h2>Trait inference and direct copy look very different inside the trace</h2><div class="mode-grid"><article class="mode trait"><h3>Personality inference: Lyft → “cost-conscious”</h3><div class="path"><span class="node">Wait 8 min to save $4</span><span class="arrow">→</span><span class="node">Sam is frugal</span><span class="arrow">→</span><span class="node">Choose a low amount</span></div><div class="statline"><div class="stat"><b>{lyft_trait}/50</b><small>traces infer the trait</small></div><div class="stat"><b>{lyft_compute}/50</b><small>compute $30/hour</small></div><div class="stat"><b>{lyft_select}/50</b><small>final answers copy it</small></div></div><blockquote>“{html.escape(trait_quote)}”</blockquote><p class="answers">Nonstop-flight answers with no memory: median <b>${baseline_flight:g}</b>. With Lyft alone: <b>${lyft_flight:g}</b> ({reduction:.0%} lower); five answers were {', '.join(f'${x:g}' for x in lyft_flight_values)}.</p></article>
<article class="mode rate"><h3>Direct copy: cleaner → $20/hour</h3><div class="path"><span class="node">Pay $60 to save 3 h</span><span class="arrow">→</span><span class="node">$60 ÷ 3 = $20/h</span><span class="arrow">→</span><span class="node">New hours × $20</span></div><div class="statline"><div class="stat"><b>{cleaner_compute}/50</b><small>traces compute $20/hour</small></div><div class="stat"><b>{cleaner_select}/50</b><small>all final answers copy it</small></div><div class="stat"><b>{cleaner_flight_select}/5</b><small>flights equal $60</small></div></div><blockquote>“{html.escape(direct_quote)}”</blockquote><p class="answers">The five nonstop-flight answers are all <b>$60</b>: three hours saved × $20/hour. The memory's original context—cleaning—drops out once the rate is constructed.</p></article></div><div class="warning"><b>The personality mode is not a numerical discount rule.</b> The trace does not say “start at $150 and reduce it by 90%.” It uses qualitative language—“not pay a lot,” “practical,” “cost-conscious”—and then settles on a plausible low number. The observed 90% median reduction is our comparison, not an explicit model calculation.</div></section>
<section id="dominance"><div class="kicker">2 · Which memories dominate thought and action?</div><h2>Computing a rate is not the same as using it</h2><p>The gold point is how often a memory’s hourly rate appears in the trace when that memory is shown. The green point is how often the final answer actually matches that rate.</p><div class="chart"><div class="legend"><span><i style="background:#b47b1d"></i>rate computed in trace</span><span><i style="background:#1d6654"></i>rate used in final answer</span></div>{dumbbell}<p class="chart-note">All single- and multi-memory calls. Regex-coded computation; final use is a ±3% match to the displayed memory's implied $/hour.</p></div><div class="split"><div class="callout"><h3>The dominant memories are C and H—not the most frequently calculated ones.</h3><ul><li><b>Cleaner H:</b> computed in 83% of calls where shown; used in 45%.</li><li><b>Disney C:</b> computed in 66%; used in 50%.</li><li><b>Wage A:</b> computed in 67%; used in only 9%.</li><li><b>Declined shift G:</b> its $29 figure appears in 87%; used in only 6%.</li></ul><p>The trace can carry a number for hundreds of words without allowing it to determine the answer. H and C are distinctive because computation frequently converts into selection.</p></div><div class="quote-card"><div class="kicker">Exact contextual activation</div><h3>Lyft becomes a direct-copy rate on a rideshare question</h3><blockquote>“{html.escape(match_quote)}”</blockquote><p>With Lyft and the cleaner both available, both rideshare calls choose Lyft: $5 for 10 minutes = $30/hour. The close context changes Lyft from a personality cue into an exchange rate.</p></div></div></section>
<section id="competition"><div class="kicker">3 · What happens with several memories?</div><h2>More thinking produces more selection, not more integration</h2><div class="chart"><div class="legend"><span><i style="background:#1d6654"></i>share copying a displayed rate</span><span><i style="background:#b47b1d"></i>median trace words (number labels)</span></div>{line_svg}<p class="chart-note">The two series use separate visual scales: green uses the percentage grid; gold is scaled from 450–1,450 words. Labels provide the exact values.</p></div><div class="split"><div><h3>What appears in traces with 3–9 memories</h3><div class="move-list">{move_html}<div class="move"><span><b>Final answer equals the mean</b></span><div><i style="width:0%"></i></div><b>0%</b><small>{avg_final}/{len(many)}</small></div></div></div><div class="quote-card"><div class="kicker">All nine memories · general question</div><blockquote>“{html.escape(choice_quote)}”</blockquote><p>The trace notices dispersion, mentions averaging, and considers the declined shift. It nevertheless ends by privileging the cleaner because it offers a “direct calculation.”</p></div></div></section>
<section id="conclusions"><div class="kicker">Conclusions</div><h2>What the traces add to the behavioral results</h2><div class="conclusions"><article><strong>1. The model first chooses a representation.</strong>A remembered choice can become a trait, a numerical exchange rate, or occasionally a context-specific exception. That representational choice determines the subsequent calculation.</article><article><strong>2. Portable rates dominate by conversion, not mention.</strong>Nearly every memory is discussed. H and C dominate because their computed rates are repeatedly carried into the final answer; wages and the declined shift are often computed but discarded.</article><article><strong>3. Deliberation is mostly competitive selection.</strong>As the bank grows, traces become roughly 2.5× longer and conflicts are noticed. Yet the modal endpoint is still one selected rate, not a context-weighted synthesis.</article></div><p class="caveat"><b>Caution:</b> thinking traces are generated explanations, not privileged access to the model’s causal mechanism. The strongest evidence comes from pairing the trace with interventions on the memory bank and observing which final answer changes. Trace coding is keyword-based, and a rate match can occasionally occur by coincidence—especially around the model’s default $15–20/hour range.</p><p class="caveat">Generated from <code>runs/s1_single/records.jsonl</code> and <code>runs/s2_combos/records.jsonl</code>. Examples come from verified records B__nonstop_flight__r0, H__nonstop_flight__r0/r3, B-H__priority_pickup__r1, and A-B-C-D-E-F-G-H-I__general__r1.</p></section></main></body></html>"""

OUT.write_text(DOC,encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
print("trait",baseline_flight,lyft_flight,reduction,lyft_trait,lyft_compute,lyft_select)
print("direct",cleaner_compute,cleaner_select,cleaner_flight_select)
print("many",len(many),move_stats,avg_final)
