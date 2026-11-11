"""Build a presentation-ready HTML around the three-stage argument.

    PYTHONPATH=. uv run python scripts/build_presentation_progression.py
"""
from __future__ import annotations

import collections
import html
import json
import re
import statistics as st
from pathlib import Path

from value_of_time.stimuli import FACT_BY_ID, QUESTION_BY_ID, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/presentation_progression.html"
V = {f.id: f.implied_hourly for f in FACT_BY_ID.values()}
FLOOR = {f.id for f in FACT_BY_ID.values() if f.bound == "lower"}
CEILING = {f.id for f in FACT_BY_ID.values() if f.bound == "upper"}

MEM = {
    "A": ("Wage", "$19/h", "work"),
    "B": ("Lyft Wait & Save", "≤ $30/h", "rideshare"),
    "C": ("Disney pass", "≥ $15/h", "theme park"),
    "D": ("Toll road", "≥ $36/h", "commute"),
    "E": ("Free parking search", "≤ $45/h", "parking"),
    "F": ("Valet on a date", "≥ $210/h", "parking / date"),
    "G": ("Declined Saturday shift", "≥ $29/h", "work / leisure"),
    "H": ("Apartment cleaner", "≥ $20/h", "chores"),
    "I": ("Cheaper gas station", "≤ $18/h", "errand"),
}
QNAME = {
    "general": "General value",
    "weekend_gig": "Saturday job",
    "research_study": "Research study",
    "nonstop_flight": "Nonstop flight",
    "priority_pickup": "Priority rideshare",
    "grocery_delivery": "Grocery delivery",
    "furniture_assembly": "Bookshelf assembly",
    "theme_park": "Theme-park pass",
    "train_delay": "Train delay",
    "volunteer_or_donate": "Volunteer vs donate",
}
QORDER = [q.id for q in QUESTIONS]
PAIR_ORDER = [("B", "C"), ("C", "H"), ("A", "H"), ("B", "H"), ("B", "D")]
PAIR_TITLES = {
    ("B", "C"): "A clean topical switch — then a Disney fallback",
    ("C", "H"): "Two reusable anchors; the question sometimes breaks the tie",
    ("A", "H"): "A domain match loses to a convenient episodic rate",
    ("B", "H"): "One close match, then one memory captures almost everything",
    ("B", "D"): "Two travel memories do not produce a stable travel rule",
}
PAIR_NOTES = {
    ("B", "C"): "The rideshare question retrieves Lyft and the theme-park question retrieves Disney. But outside rideshare, Disney often becomes the general-purpose answer—even for work, groceries, and train delay.",
    ("C", "H"): "Theme park cleanly retrieves Disney; groceries and train delay retrieve the cleaner. When neither is similar (priority rideshare), neither rate is used and the answer returns to $30/h.",
    ("A", "H"): "The cleaner defeats the wage on the general question, the Saturday job, the flight, the bookshelf, and the donation question. Semantic domain alone cannot explain selection.",
    ("B", "H"): "Lyft wins the close rideshare match. The cleaner wins eight of the other nine questions; the surprising exception is theme park, where Lyft’s $30/h is copied.",
    ("B", "D"): "Both memories are travel-related. Lyft reliably wins rideshare, but the flight and train questions are split or unresolved. Category-level similarity is too coarse to predict the choice.",
}


def load(path: Path):
    rows = {}
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            if r["status"] == "ok":
                rows[r["cell_id"]] = r
    return list(rows.values())


S1 = load(ROOT / "runs/s1_single/records.jsonl")
S2 = load(ROOT / "runs/s2_combos/records.jsonl")
ALL = S1 + S2
PAIRS = [r for r in S2 if len(r["fact_set"]) == 2]
MULTI = [r for r in S2 if len(r["fact_set"]) >= 3]


def hit(hourly, fact):
    return hourly is not None and abs(hourly - V[fact]) / V[fact] <= 0.03


def winner(r):
    matches = [f for f in r["fact_set"] if hit(r["implied_hourly"], f)]
    return matches[0] if len(matches) == 1 else ("tie" if matches else "none")


def pct(a, b):
    return f"{a / b:.0%}" if b else "—"


def esc(x):
    return html.escape(str(x))


# Stage 1: direct copying plus qualitative trait use.
s1_by = collections.defaultdict(list)
for r in S1:
    key = r["fact_set"][0] if r["fact_set"] else "none"
    s1_by[key].append(r)
copy1 = {f: sum(hit(r["implied_hourly"], f) for r in s1_by[f]) for f in V}
TRAIT = re.compile(r"cost[- ]conscious|frugal|budget|thrifty|saving money", re.I)
trait1 = {f: sum(bool(TRAIT.search(r["thinking"])) for r in s1_by[f]) for f in V}

# Stage 2: pair-level outcomes.
def pair_cell(pair, q):
    rows = sorted(
        [r for r in PAIRS if set(r["fact_set"]) == set(pair) and r["question"] == q],
        key=lambda r: r["rep"],
    )
    wins = collections.Counter(winner(r) for r in rows)
    vals = [r["implied_hourly"] for r in rows if r["implied_hourly"] is not None]
    return rows, wins, vals


def outcome_label(pair, q):
    rows, wins, vals = pair_cell(pair, q)
    a, b = pair
    pieces = []
    for r in rows:
        w = winner(r)
        value = r["implied_hourly"]
        value_text = "—" if value is None else f"${value:g}/h"
        pieces.append(f"{w.upper() if w in pair else 'neither'} {value_text}")
    detail = " · ".join(pieces)
    if wins[a] == 2:
        return a, detail
    if wins[b] == 2:
        return b, detail
    if wins[a] == 1 and wins[b] == 1:
        return "split", detail
    if wins[a] == 1:
        return "mixed", detail
    if wins[b] == 1:
        return "mixed", detail
    if vals:
        return "none", detail
    return "none", "neither"


def pair_summary(pair):
    rows = [r for r in PAIRS if set(r["fact_set"]) == set(pair)]
    counts = collections.Counter(winner(r) for r in rows)
    a, b = pair
    decided = counts[a] + counts[b]
    total_line = (
        f'<span><b>{a}</b> {counts[a]}/20 ({pct(counts[a], 20)})</span>'
        f'<span><b>{b}</b> {counts[b]}/20 ({pct(counts[b], 20)})</span>'
        f'<span><b>Neither</b> {counts["none"]}/20 ({pct(counts["none"], 20)})</span>'
    )
    decided_line = (
        f'Among the {decided} calls that matched one displayed rate: '
        f'<b>{a} {pct(counts[a], decided)}</b> versus <b>{b} {pct(counts[b], decided)}</b>.'
    )
    return total_line, decided_line


def pair_table(pair):
    a, b = pair
    rows = []
    for q in QORDER:
        cls, label = outcome_label(pair, q)
        fit_a = FACT_BY_ID[a].domain == QUESTION_BY_ID[q].domain
        fit_b = FACT_BY_ID[b].domain == QUESTION_BY_ID[q].domain
        fit = []
        if fit_a:
            fit.append(a)
        if fit_b:
            fit.append(b)
        fit_text = "/".join(fit) if fit else "—"
        rows.append(
            f'<tr><td class="qname">{esc(QNAME[q])}</td>'
            f'<td class="fit">{fit_text}</td>'
            f'<td><span class="outcome {cls}">{esc(label)}</span></td></tr>'
        )
    return "".join(rows)


# Aggregate facts used only to orient the audience, not as the Stage 2 result.
pair_flip = 0
pair_one = 0
for pair in {tuple(r["fact_set"]) for r in PAIRS}:
    used = {winner(r) for r in PAIRS if tuple(r["fact_set"]) == pair}
    used &= set(pair)
    if len(used) == 2:
        pair_flip += 1
    elif len(used) == 1:
        pair_one += 1

copy_by_n = {}
for n in range(1, 10):
    rows = [r for r in ALL if len(r["fact_set"]) == n]
    if rows:
        copy_by_n[n] = sum(any(hit(r["implied_hourly"], f) for f in r["fact_set"]) for r in rows) / len(rows)

# Trace analysis.
RATE_PAT = {
    "A": r"19\.2|19 (per|an|/) ?h", "B": r"\$?30(\.0+)? ?(per|an|/|a) ?h",
    "C": r"\$?15(\.0+)? ?(per|an|/|a) ?h", "D": r"\$?36(\.0+)? ?(per|an|/|a) ?h",
    "E": r"\$?45(\.0+)? ?(per|an|/|a) ?h", "F": r"\$?210(\.0+)? ?(per|an|/|a) ?h",
    "G": r"\$?29(\.0+)? ?(per|an|/|a) ?h|28\.8", "H": r"\$?20(\.0+)? ?(per|an|/|a) ?h",
    "I": r"\$?18(\.0+)? ?(per|an|/|a) ?h",
}
trace_stats = {}
for f in ("A", "C", "H"):
    rows = [r for r in ALL if f in r["fact_set"]]
    computed = sum(bool(re.search(RATE_PAT[f], r["thinking"], re.I)) for r in rows)
    used = sum(hit(r["implied_hourly"], f) for r in rows)
    trace_stats[f] = (computed, used, len(rows))

conflict_pat = re.compile(r"contradict|inconsisten|conflict|doesn.t add up|mixed signal", re.I)
context_pat = re.compile(r"depends on (the )?(context|situation|activity)|different (contexts|situations)|varies (by|with|depending)", re.I)
avg_pat = re.compile(r"\baverag(e|ing)\b", re.I)
conflicts = sum(bool(conflict_pat.search(r["thinking"])) for r in MULTI)
contexts = sum(bool(context_pat.search(r["thinking"])) for r in MULTI)
avg_words = sum(bool(avg_pat.search(r["thinking"])) for r in MULTI)
avg_answers = sum(
    r["implied_hourly"] is not None
    and abs(r["implied_hourly"] - st.mean(V[f] for f in r["fact_set"])) / st.mean(V[f] for f in r["fact_set"]) <= .03
    for r in MULTI
)
words_0 = st.median(len(r["thinking"].split()) for r in S1 if not r["fact_set"])
words_many = st.median(len(r["thinking"].split()) for r in MULTI)

stage1_rows = []
for f in ["H", "C", "D", "F", "A", "B", "E", "I", "G"]:
    typ = "exchange-rate" if f in FLOOR and f != "G" else "trait" if f in CEILING else "mixed"
    use = f"{copy1[f]}/50 copy rate" if typ == "exchange-rate" else (
        f"{trait1[f]}/50 infer trait" if typ == "trait" else f"{copy1[f]}/50 copy rate"
    )
    stage1_rows.append(
        f'<tr><td><span class="mem {f}">{f}</span> <b>{esc(MEM[f][0])}</b><br><small>{esc(MEM[f][1])}</small></td>'
        f'<td><span class="mechanism {typ}">{esc(typ.replace("-", " "))}</span></td><td>{esc(use)}</td></tr>'
    )

pair_cards = []
for pair in PAIR_ORDER:
    a, b = pair
    total_line, decided_line = pair_summary(pair)
    pair_cards.append(f"""
    <article class="pair-card" id="pair-{a.lower()}{b.lower()}">
      <div class="pair-head">
        <div><span class="eyebrow">Specific combination {a}+{b}</span><h3>{esc(PAIR_TITLES[pair])}</h3></div>
        <div class="pair-mems"><span class="mem {a}">{a}</span> {esc(MEM[a][0])} <span class="versus">vs</span> <span class="mem {b}">{b}</span> {esc(MEM[b][0])}</div>
      </div>
      <p>{esc(PAIR_NOTES[pair])}</p>
      <div class="pair-summary"><div>{total_line}</div><small>{decided_line}</small></div>
      <div class="table-wrap"><table class="pair-table"><thead><tr><th>Question</th><th>Same domain?</th><th>Selected rate in two calls</th></tr></thead><tbody>{pair_table(pair)}</tbody></table></div>
    </article>""")

trace_rows = []
for f in ("A", "C", "H"):
    comp, used, n = trace_stats[f]
    trace_rows.append(
        f'<tr><td><span class="mem {f}">{f}</span> {esc(MEM[f][0])}</td>'
        f'<td>{comp}/{n} <small>({pct(comp,n)})</small></td>'
        f'<td>{used}/{n} <small>({pct(used,n)})</small></td></tr>'
    )

html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>How does an agent choose a value-of-time memory?</title>
<style>
:root{{--paper:#f4f0e8;--surface:#fffdf8;--ink:#17211f;--muted:#5d6965;--line:#d8d1c4;--green:#1d6654;--rust:#a8492f;--gold:#b47b1d;--blue:#2e6177;--soft:#ece6db}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif;line-height:1.48}}
.wrap{{max-width:1180px;margin:auto;padding:28px 30px 90px}}nav{{position:sticky;top:0;z-index:10;background:rgba(244,240,232,.94);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
nav .inner{{max-width:1180px;margin:auto;padding:10px 30px;display:flex;gap:18px;align-items:center;overflow:auto}}nav b{{font-family:Georgia,serif;white-space:nowrap}}nav a{{color:var(--muted);text-decoration:none;font-size:14px;white-space:nowrap}}nav a:hover{{color:var(--ink)}}
.hero{{min-height:75vh;display:grid;grid-template-columns:1.25fr .75fr;gap:58px;align-items:center;border-bottom:1px solid var(--line);padding:58px 0}}
.kicker,.eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:.13em;font-weight:800;color:var(--rust)}}h1,h2,h3{{font-family:Georgia,"Times New Roman",serif;line-height:1.08}}h1{{font-size:clamp(45px,6vw,78px);margin:12px 0 22px;max-width:850px}}h2{{font-size:clamp(34px,4vw,50px);margin:0 0 16px}}h3{{font-size:25px;margin:5px 0 8px}}.lede{{font-family:Georgia,serif;font-size:22px;color:#3f4b47;max-width:760px}}
.question{{background:var(--ink);color:#fff;padding:30px;border-radius:2px;box-shadow:12px 12px 0 #cabb9d}}.question .eyebrow{{color:#e3b865}}.question p{{font-family:Georgia,serif;font-size:27px;line-height:1.25;margin:12px 0 0}}
.progression{{counter-reset:stage;display:grid;gap:12px;margin-top:30px}}.step{{display:grid;grid-template-columns:54px 1fr;gap:14px;align-items:start;padding:13px 0;border-top:1px solid var(--line)}}.step .n{{font-family:Georgia,serif;font-size:35px;color:var(--rust)}}.step b{{font-size:17px}}.step span{{color:var(--muted)}}
section{{padding:72px 0;border-bottom:1px solid var(--line)}}.section-head{{display:grid;grid-template-columns:1fr 1fr;gap:50px;align-items:end;margin-bottom:28px}}.section-head p{{font-size:18px;color:var(--muted);margin:0}}
.verdict{{background:var(--surface);border:1px solid var(--line);padding:24px 28px;margin:22px 0 30px;display:grid;grid-template-columns:220px 1fr;gap:25px;align-items:center}}.verdict strong{{font-family:Georgia,serif;font-size:36px;color:var(--green)}}.verdict p{{font-size:18px;margin:0}}
table{{border-collapse:collapse;width:100%}}th{{text-align:left;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em;border-bottom:2px solid var(--ink);padding:9px 10px}}td{{padding:10px;border-bottom:1px solid var(--line);vertical-align:top}}small{{color:var(--muted)}}
.mem{{display:inline-grid;place-items:center;width:27px;height:27px;border-radius:50%;background:var(--ink);color:white;font-weight:800;font-size:13px;margin-right:4px}}.mem.B,.mem.E,.mem.I{{background:var(--rust)}}.mem.C,.mem.D,.mem.F,.mem.G,.mem.H{{background:var(--green)}}.mem.A{{background:var(--blue)}}
.mechanism{{display:inline-block;padding:3px 8px;background:var(--soft);font-size:12px;text-transform:uppercase;letter-spacing:.06em;font-weight:700}}.mechanism.trait{{color:var(--rust)}}.mechanism.exchange-rate{{color:var(--green)}}
.stage1-grid{{display:grid;grid-template-columns:1.2fr .8fr;gap:24px}}.callout{{background:#e8dfcd;padding:25px 28px;align-self:start}}.callout h3{{font-size:28px}}.callout li{{margin-bottom:9px}}
.stage2-intro{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:30px}}.claim{{background:var(--ink);color:white;padding:26px}}.claim b{{display:block;font-family:Georgia,serif;font-size:44px;color:#e3b865}}.claim p{{font-size:17px;margin:4px 0 0}}.caution{{background:var(--surface);border:1px solid var(--line);padding:26px}}.caution b{{font-family:Georgia,serif;font-size:25px}}.caution p{{margin-bottom:0}}
.pair-list{{display:grid;gap:28px}}.pair-card{{background:var(--surface);border:1px solid var(--line);padding:26px 28px;box-shadow:0 2px 0 rgba(23,33,31,.05)}}.pair-head{{display:grid;grid-template-columns:1fr auto;gap:25px;align-items:start}}.pair-mems{{font-size:14px;white-space:nowrap;background:var(--soft);padding:9px 12px}}.versus{{color:var(--muted);padding:0 7px}}.pair-card>p{{font-size:17px;max-width:920px}}.pair-summary{{background:#eee8dc;padding:12px 15px;margin:14px 0 17px}}.pair-summary>div{{display:flex;gap:22px;flex-wrap:wrap;margin-bottom:3px}}.pair-summary small{{font-size:13px}}.pair-table{{font-size:14px}}.pair-table td{{padding:7px 9px}}.qname{{font-weight:700}}.fit{{color:var(--muted);width:110px}}.outcome{{display:inline-block;min-width:210px;padding:3px 8px;font-weight:700;background:#eee}}.outcome.A{{background:#dbe8ee;color:#173e50}}.outcome.B{{background:#f2dcd5;color:#78301f}}.outcome.C,.outcome.D,.outcome.H{{background:#dbe9e4;color:#174d40}}.outcome.split{{background:#eadfc7;color:#654b17}}.outcome.mixed,.outcome.none{{background:#ece9e2;color:#65615a}}
.reading{{margin-top:30px;background:#e8dfcd;padding:26px 30px}}.reading h3{{margin-top:0}}.reading-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:25px}}.reading b{{display:block;font-family:Georgia,serif;font-size:22px;margin-bottom:6px}}
.trace-grid{{display:grid;grid-template-columns:1fr 1fr;gap:25px}}.trace-card{{background:var(--surface);border:1px solid var(--line);padding:26px}}.trace-card h3{{margin-top:0}}.big{{font-family:Georgia,serif;font-size:52px;color:var(--rust);line-height:1}}blockquote{{font-family:Georgia,serif;font-size:20px;line-height:1.45;margin:18px 0 0;padding:20px 0 0;border-top:1px solid var(--line)}}
.end{{display:grid;grid-template-columns:1fr .8fr;gap:45px;align-items:start}}.takeaway{{font-family:Georgia,serif;font-size:32px;line-height:1.25;margin-top:0}}.limits{{background:var(--surface);border:1px solid var(--line);padding:25px}}.limits h3{{margin-top:0}}.limits li{{margin-bottom:8px}}
.footer{{color:var(--muted);font-size:13px;padding-top:24px}}code{{background:#e7e1d5;padding:2px 5px}}
@media(max-width:850px){{.hero,.section-head,.stage1-grid,.stage2-intro,.pair-head,.trace-grid,.end{{grid-template-columns:1fr}}.hero{{min-height:auto}}.question{{box-shadow:7px 7px 0 #cabb9d}}.verdict{{grid-template-columns:1fr}}.reading-grid{{grid-template-columns:1fr}}.pair-mems{{white-space:normal}}.table-wrap{{overflow-x:auto}}.wrap{{padding-left:18px;padding-right:18px}}nav .inner{{padding-left:18px}}}}
@media print{{nav{{display:none}}body{{background:white}}.wrap{{max-width:none;padding:0 26px}}section,.hero{{break-before:page;min-height:auto;padding:35px 0}}.hero{{break-before:auto}}.pair-card,.trace-card,.verdict{{break-inside:avoid}}}}
</style></head><body>
<nav><div class="inner"><b>Value of time</b><a href="#stage1">1 · One memory</a><a href="#stage2">2 · Competing memories</a><a href="#traces">3 · Thinking traces</a><a href="#takeaway">Takeaway</a></div></nav>
<main class="wrap">
<header class="hero">
  <div><div class="kicker">Presentation narrative · Qwen3-8B · 1,640 calls</div><h1>How does an agent choose how to solve a problem?</h1>
  <p class="lede">The value-of-time task gives the agent several defensible ways to answer. The central object is not its average dollar value—it is the association it forms between a new question and a remembered episode.</p>
  <div class="progression">
    <div class="step"><div class="n">1</div><div><b>Can one memory enter the answer?</b><br><span>Establish that the manipulation works, and see how different kinds of memories are represented.</span></div></div>
    <div class="step"><div class="n">2</div><div><b>Which memory wins when several are available?</b><br><span>Hold the memory pair fixed and change the question; inspect the specific question–memory associations.</span></div></div>
    <div class="step"><div class="n">3</div><div><b>What do the traces reveal about selection?</b><br><span>Separate information the model computes or mentions from information that actually determines the answer.</span></div></div>
  </div></div>
  <aside class="question"><div class="eyebrow">The main question</div><p>Does the agent retrieve the closest episode, default to an easy plausible rate, or construct a different representation of the person?</p></aside>
</header>

<section id="stage1"><div class="section-head"><div><div class="kicker">Stage 1</div><h2>One memory is enough to move the solution</h2></div><p>The stage succeeds—but “use” does not always mean copying the memory’s implied hourly rate. The direction of the remembered choice changes the representation.</p></div>
<div class="verdict"><strong>Yes, with a qualification.</strong><p>Paid-to-save-time memories are often turned into a reusable exchange rate. Spent-time-to-save-money memories are usually turned into a trait such as “cost-conscious,” which lowers answers without copying the memory’s own rate.</p></div>
<div class="stage1-grid"><div><table><thead><tr><th>Memory shown alone</th><th>Representation</th><th>Observed use across 50 calls</th></tr></thead><tbody>{''.join(stage1_rows)}</tbody></table></div>
<aside class="callout"><h3>What Stage 1 establishes</h3><ul><li>The agent can use a single autobiographical memory far outside its original context.</li><li>The same mathematical object—a bound on $/hour—can be encoded as a <b>price</b> or as a <b>personality trait</b>.</li><li>Therefore Stage 2 is not only a contest among numbers. It is a contest among <b>problem representations</b>.</li></ul></aside></div>
</section>

<section id="stage2"><div class="section-head"><div><div class="kicker">Stage 2 · the center of the presentation</div><h2>Keep the memory bank fixed; change the question</h2></div><p>Aggregate winner rates hide the phenomenon. The informative unit is a particular pair of memories observed across the ten questions.</p></div>
<div class="stage2-intro"><div class="claim"><b>{pair_flip}/36 pairs</b><p>used both memories at least once as the question changed. The question can redirect retrieval.</p></div><div class="caution"><b>Important: only two calls per question.</b><p>Each exact pair has 20 calls total: ten questions × two repetitions. A “split” cell is literally one call for each memory, so question-level differences are suggestive rather than stable estimates. The larger memory ladders contain additional calls where the pair co-occurs, but other competing memories also change, so those are not clean replications of the two-memory contest.</p></div></div>
<div class="pair-list">{''.join(pair_cards)}</div>
<div class="reading"><h3>The pattern across these combinations</h3><div class="reading-grid"><div><b>Exact episodic matches are real.</b>Rideshare retrieves Lyft; theme park retrieves Disney; bookshelf assembly often retrieves the cleaner.</div><div><b>When there is no close match, the agent does not abstain.</b>It often exports whichever memory offers a simple, plausible hourly rate—especially Disney’s $15/h or the cleaner’s $20/h.</div><div><b>Similarity is not a single distance.</b>Two “travel” memories can behave differently across rideshare, flight, and train questions; a chores memory can beat a wage on a work question.</div></div></div>
</section>

<section id="traces"><div class="section-head"><div><div class="kicker">Stage 3</div><h2>Thinking traces show the candidates, not necessarily the cause</h2></div><p>The traces are most useful when compared with the final numerical choice. Mentioning or computing a memory is not the same as selecting it.</p></div>
<div class="trace-grid"><article class="trace-card"><h3>Computed versus used</h3><table><thead><tr><th>Memory</th><th>Rate appears in trace</th><th>Answer uses rate</th></tr></thead><tbody>{''.join(trace_rows)}</tbody></table><blockquote>“The cleaner example is a direct calculation, so that’s a strong indicator.”</blockquote></article>
<article class="trace-card"><div class="big">{words_0:.0f} → {words_many:.0f}</div><h3>median trace words</h3><p>More memories produce much longer deliberation. But the extra thought usually ends in selecting one source rather than integrating the evidence.</p><ul><li>{conflicts}/{len(MULTI)} ({pct(conflicts,len(MULTI))}) flag a conflict.</li><li>{contexts}/{len(MULTI)} ({pct(contexts,len(MULTI))}) say value depends on context.</li><li>{avg_words}/{len(MULTI)} ({pct(avg_words,len(MULTI))}) mention averaging.</li><li><b>{avg_answers}/{len(MULTI)} final answers equal the memories’ mean.</b></li></ul></article></div>
<div class="verdict"><strong>Trace lesson</strong><p>Use traces to identify the candidate representations and the story the model tells about them. Use changes in the final answer—and fixed-pair comparisons—to infer which representation actually controlled the solution.</p></div>
</section>

<section id="takeaway"><div class="end"><div><div class="kicker">Presentation takeaway</div><h2>The agent is selecting a way to think, not estimating one stable parameter</h2><p class="takeaway">A new question activates one remembered episode, and that episode supplies either an exchange rate, a character trait, or a default anchor. The closest context sometimes wins—but simple, plausible memories can become general-purpose schemas.</p><p>This is why the strongest evidence is the specific combination: with the same two memories available, which question retrieves which one, and where does the association fail?</p></div>
<aside class="limits"><h3>What we can and cannot claim</h3><ul><li><b>Can:</b> show that a single memory changes the solution; identify question-specific retrieval in several pairs; show systematic fallback to reusable memories.</li><li><b>Cannot yet:</b> separate semantic similarity from easy arithmetic and proximity to the model’s prior.</li><li><b>Small cells:</b> five draws per single-memory question and two per pair-question cell.</li><li><b>One system:</b> one persona and one Qwen3-8B configuration; no human comparison yet.</li><li><b>Trace coding:</b> keyword-based and descriptive, not a causal readout.</li></ul></aside></div>
<div class="footer">Generated from <code>runs/s1_single/records.jsonl</code> and <code>runs/s2_combos/records.jsonl</code>. “Selected” means the answer’s implied $/hour matches exactly one displayed memory within ±3%. Neither means the final rate matched neither memory.</div></section>
</main></body></html>"""

OUT.write_text(html_doc, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
print("checks", len(S1), len(S2), pair_flip, pair_one, avg_answers, len(MULTI))
