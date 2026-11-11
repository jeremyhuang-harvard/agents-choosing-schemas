"""Rebuild every results table in `results/` from the saved run records.

No model, no network, standard library only:

    python analysis/make_results.py

Inputs: `runs/s1_single/` (500 calls: no memory, or one memory) and `runs/s2_combos/` (1,140 calls:
pairs and one-at-a-time ladders up to all nine memories). The memories, their implied $/hour and the
questions are read from each run's `manifest.json`, so this script does not import the experiment code.

Definitions (the same ones our original analysis scripts in `scripts/` use):

- implied $/hour = dollar answer / hours at stake in the question (stored as `implied_hourly`).
- an answer "copies" a memory when its implied $/hour is within 3% of that memory's implied $/hour.
- a memory is "selected" in a call when the answer copies exactly one of the memories shown.
"""

from __future__ import annotations

import csv
import html
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = ROOT / "results"

TOL = 0.03
MEMORY_IDS = list("ABCDEFGHI")
SHORT = {"A": "wage $40k/yr", "B": "Lyft wait & save", "C": "Disney line pass", "D": "commute toll",
         "E": "circled for free parking", "F": "valet on a date", "G": "declined $29/h shift",
         "H": "pays a cleaner", "I": "drove to cheaper gas"}
QSHORT = {"general": "General: what is an hour worth?", "weekend_gig": "Weekend gig (accept, 4 h)",
          "research_study": "Research study (accept, 1 h)", "nonstop_flight": "Nonstop flight (pay, saves 3 h)",
          "priority_pickup": "Priority rideshare (pay, saves 10 min)",
          "grocery_delivery": "Grocery delivery (pay, saves 1 h)",
          "furniture_assembly": "Bookshelf assembly (pay, saves 2 h)",
          "theme_park": "Theme-park line pass (pay, saves 2 h)",
          "train_delay": "Train delay compensation (5 h)", "volunteer_or_donate": "Donation = 2 h volunteering"}

# Trace keyword patterns, copied from our original scripts (named next to each).
TRAIT = re.compile(r"cost[- ]conscious|frugal|budget|thrifty|saving money", re.I)  # build_report.py (stage 1)
TRAIT_MOVES = re.compile(r"cost[- ]conscious|frugal|budget[- ]conscious|thrifty|careful with money|"
                         r"money[- ]conscious|saving money", re.I)  # build_trace_interpretation.py (3+ memories)
MOVES = {  # build_trace_interpretation.py / build_presentation_progression.py
    "flags a conflict between memories": r"contradict|inconsisten|conflict|doesn.t add up|mixed signal",
    "mentions averaging": r"\baverag(e|ing)\b",
    "says the value depends on context": r"depends on (the )?(context|situation|activity)|different (contexts|situations)|varies (by|with|depending)",
}
RATE_PAT = {  # analyze_schema.py: the memory's own rate written out in the trace
    "A": r"19\.2|19 (per|an|/) ?h", "B": r"\$?30(\.0+)? ?(per|an|/|a) ?h", "C": r"\$?15(\.0+)? ?(per|an|/|a) ?h",
    "D": r"\$?36(\.0+)? ?(per|an|/|a) ?h", "E": r"\$?45(\.0+)? ?(per|an|/|a) ?h", "F": r"\$?210(\.0+)? ?(per|an|/|a) ?h",
    "G": r"\$?29(\.0+)? ?(per|an|/|a) ?h|28\.8", "H": r"\$?20(\.0+)? ?(per|an|/|a) ?h", "I": r"\$?18(\.0+)? ?(per|an|/|a) ?h",
}


# ----------------------------------------------------------------------------- loading
def load(run: str) -> list[dict]:
    """Completed calls of a run; if a cell was attempted more than once, keep its last ok attempt."""
    latest: dict[str, dict] = {}
    for line in (RUNS / run / "records.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r["status"] == "ok":
                latest[r["cell_id"]] = r
    return list(latest.values())


MANIFEST = json.loads((RUNS / "s1_single" / "manifest.json").read_text())
FACTS = {f["id"]: f for f in MANIFEST["facts"]}
QUESTIONS = [q["id"] for q in MANIFEST["questions"]]
QUESTION = {q["id"]: q for q in MANIFEST["questions"]}
RATE = {f: FACTS[f]["implied_hourly"] for f in MEMORY_IDS}
BOUND = {f: {"lower": "floor", "upper": "ceiling", "point": "exact"}[FACTS[f]["bound"]] for f in MEMORY_IDS}
FLOOR = {f for f in MEMORY_IDS if BOUND[f] == "floor"}
CEIL = {f for f in MEMORY_IDS if BOUND[f] == "ceiling"}

S1 = load("s1_single")
S2 = load("s2_combos")
ALL = S1 + S2


def copies(r: dict, f: str) -> bool:
    h = r["implied_hourly"]
    return h is not None and abs(h - RATE[f]) / RATE[f] <= TOL


def selected(r: dict) -> str | None:
    hits = [f for f in r["fact_set"] if copies(r, f)]
    return hits[0] if len(hits) == 1 else None


def share(k: int, n: int) -> float:
    return round(k / n, 3) if n else 0.0


def has(pattern, text: str) -> bool:
    return bool(re.search(pattern, re.sub(r"\s+", " ", text), re.I))


def fmt_money(x: float) -> str:
    return f"{x:g}"


# ----------------------------------------------------------------------------- tables
def table_runs() -> list[dict]:
    rows = []
    for run in ["pilot01", "timing_probe", "timing_batch", "s1_single", "s2_combos"]:
        lines = [json.loads(x) for x in (RUNS / run / "records.jsonl").read_text().splitlines() if x.strip()]
        stamps = sorted(r["timestamp"] for r in lines)
        sizes = Counter(len(r["fact_set"]) for r in lines)
        rows.append({"run": run, "records": len(lines), "ok": sum(r["status"] == "ok" for r in lines),
                     "memories_shown": " ".join(f"{k}:{sizes[k]}" for k in sorted(sizes)),
                     "first_call": stamps[0], "last_call": stamps[-1]})
    return rows


def table_selection() -> list[dict]:
    """Headline: among calls showing 2+ memories, how often each question selects each memory."""
    multi = [r for r in S2 if len(r["fact_set"]) >= 2]
    rows = []
    for q in QUESTIONS:
        row = {"question": q}
        for f in MEMORY_IDS:
            shown = [r for r in multi if r["question"] == q and f in r["fact_set"]]
            row[f"{f}_selected"] = sum(selected(r) == f for r in shown)
            row[f"{f}_shown"] = len(shown)
        rates = {f: row[f"{f}_selected"] / row[f"{f}_shown"] for f in MEMORY_IDS}
        top = max(MEMORY_IDS, key=lambda f: (rates[f], -MEMORY_IDS.index(f)))
        row["top_memory"] = top
        row["top_share"] = round(rates[top], 3)
        row["predicted"] = "".join(QUESTION[q]["hypothesized_facts"])
        row["top_was_predicted"] = top in QUESTION[q]["hypothesized_facts"]
        rows.append(row)
    return rows


def selection_summary(sel: list[dict]) -> dict:
    hw = hn = ow = on = 0
    for row in sel:
        for f in MEMORY_IDS:
            w, n = row[f"{f}_selected"], row[f"{f}_shown"]
            if f in row["predicted"]:
                hw, hn = hw + w, hn + n
            else:
                ow, on = ow + w, on + n
    pairs = [r for r in S2 if len(r["fact_set"]) == 2]
    by_pair: dict[tuple, list[str]] = defaultdict(list)
    for r in pairs:
        w = selected(r)
        if w:
            by_pair[tuple(r["fact_set"])].append(w)
    all_pairs = sorted({tuple(r["fact_set"]) for r in pairs})
    both_used = sum(len(set(by_pair[p])) == 2 for p in all_pairs)
    dominance = [max(Counter(by_pair[p]).values()) / len(by_pair[p]) for p in all_pairs if by_pair[p]]
    return {"calls": sum(1 for r in S2 if len(r["fact_set"]) >= 2),
            "predicted_selected": hw, "predicted_shown": hn, "other_selected": ow, "other_shown": on,
            "top_was_predicted": sum(r["top_was_predicted"] for r in sel),
            "pairs": len(all_pairs), "pairs_both_used": both_used,
            "pairs_one_always": sum(len(set(by_pair[p])) == 1 for p in all_pairs),
            "median_pair_dominance": round(st.median(dominance), 3)}


def table_single() -> list[dict]:
    """Stage 1: one memory shown, 50 calls each (10 questions x 5 samples)."""
    rows = []
    for f in [None] + MEMORY_IDS:
        rs = [r for r in S1 if r["fact_set"] == ([f] if f else [])]
        rows.append({"memory": f or "none", "label": SHORT[f] if f else "(no memory)",
                     "bound": BOUND[f] if f else "", "rate": RATE[f] if f else "", "calls": len(rs),
                     "answers_copy_rate": sum(copies(r, f) for r in rs) if f else "",
                     "trace_calls_sam_cost_conscious": sum(bool(TRAIT.search(r["thinking"])) for r in rs)})
    return rows


def table_single_medians() -> list[dict]:
    rows = []
    for f in [None] + MEMORY_IDS:
        row = {"memory": f or "none"}
        for q in QUESTIONS:
            v = [r["implied_hourly"] for r in S1 if r["fact_set"] == ([f] if f else []) and r["question"] == q]
            row[q] = round(st.median(v), 2)
        rows.append(row)
    return rows


def table_by_count() -> list[dict]:
    """All 1,640 calls, by number of memories shown."""
    rows = []
    for n in range(10):
        rs = [r for r in ALL if len(r["fact_set"]) == n]
        means = [st.mean(RATE[f] for f in r["fact_set"]) for r in rs] if n else []
        at_mean = [r for r, m in zip(rs, means)
                   if n >= 2 and r["implied_hourly"] is not None and abs(r["implied_hourly"] - m) / m <= TOL]
        rows.append({
            "memories_shown": n, "calls": len(rs),
            "answer_copies_a_shown_rate": sum(any(copies(r, f) for f in r["fact_set"]) for r in rs) if n else "",
            "answer_equals_mean_of_shown_rates": len(at_mean) if n >= 2 else "",
            "of_which_also_copy_a_shown_rate": (sum(any(copies(r, f) for f in r["fact_set"]) for r in at_mean)
                                                if n >= 2 else ""),
            "median_trace_words": st.median(len(r["thinking"].split()) for r in rs),
            "median_general_question": st.median(r["implied_hourly"] for r in rs if r["question"] == "general"),
        })
    return rows


def table_wins() -> list[dict]:
    """With 3+ memories shown: how often each memory is the one selected, out of calls showing it."""
    multi = [r for r in S2 if len(r["fact_set"]) >= 3]
    rows = []
    for f in MEMORY_IDS:
        shown = [r for r in multi if f in r["fact_set"]]
        rows.append({"memory": f, "label": SHORT[f], "rate": RATE[f], "bound": BOUND[f],
                     "selected": sum(selected(r) == f for r in shown), "shown": len(shown)})
    return sorted(rows, key=lambda r: (-r["selected"] / r["shown"], r["memory"]))


def position_check() -> dict:
    obs: Counter = Counter()
    exp: dict[str, float] = defaultdict(float)
    for r in S2:
        if len(r["fact_order"]) < 3:
            continue
        hits = [f for f in r["fact_order"] if copies(r, f)]
        if len(hits) != 1:
            continue
        n, i = len(r["fact_order"]), r["fact_order"].index(hits[0])
        obs["first" if i == 0 else "last" if i == n - 1 else "middle"] += 1
        exp["first"] += 1 / n
        exp["last"] += 1 / n
        exp["middle"] += (n - 2) / n
    return {k: (obs[k], round(exp[k])) for k in ["first", "middle", "last"]}


def table_floor_ceiling() -> list[dict]:
    """Pairs with one floor and one ceiling memory: where does the answer land?"""
    c: Counter = Counter()
    for r in S2:
        fs = set(r["fact_set"])
        if len(fs) != 2 or len(fs & FLOOR) != 1 or len(fs & CEIL) != 1 or r["implied_hourly"] is None:
            continue
        h, fl, ce = r["implied_hourly"], (fs & FLOOR).pop(), (fs & CEIL).pop()
        lo, hi = sorted([RATE[fl], RATE[ce]])
        if copies(r, fl):
            c["equals the floor rate"] += 1
        elif copies(r, ce):
            c["equals the ceiling rate"] += 1
        elif lo * 0.97 <= h <= hi * 1.03:
            c["between the two"] += 1
        elif h < lo:
            c["below both"] += 1
        else:
            c["above both"] += 1
    order = ["below both", "equals the floor rate", "equals the ceiling rate", "between the two", "above both"]
    total = sum(c.values())
    return [{"outcome": k, "answers": c[k], "of": total} for k in order]


def table_computed_vs_used() -> list[dict]:
    rows = []
    for f in MEMORY_IDS:
        rs = [r for r in ALL if f in r["fact_set"]]
        rows.append({"memory": f, "label": SHORT[f], "calls_shown": len(rs),
                     "trace_writes_its_rate": sum(has(RATE_PAT[f], r["thinking"]) for r in rs),
                     "answer_copies_its_rate": sum(copies(r, f) for r in rs)})
    return rows


def table_trace_moves() -> list[dict]:
    multi = [r for r in S2 if len(r["fact_set"]) >= 3]
    rows = [{"move": "calls Sam cost-conscious / frugal",
             "traces": sum(bool(TRAIT_MOVES.search(r["thinking"])) for r in multi), "of": len(multi)}]
    rows += [{"move": k, "traces": sum(has(p, r["thinking"]) for r in multi), "of": len(multi)} for k, p in MOVES.items()]
    return rows


def table_wta_wtp() -> list[dict]:
    wta = ["weekend_gig", "research_study"]
    wtp = ["nonstop_flight", "grocery_delivery", "furniture_assembly", "theme_park"]
    rows = []
    for label, rs in [("no memory", [r for r in S1 if not r["fact_set"]]),
                      ("wage memory only", [r for r in S1 if r["fact_set"] == ["A"]]), ("all 1,640 calls", ALL)]:
        rows.append({"calls": label,
                     "median_accept_pay_to_give_up_time": st.median(r["implied_hourly"] for r in rs if r["question"] in wta),
                     "median_pay_to_save_time": st.median(r["implied_hourly"] for r in rs if r["question"] in wtp)})
    return rows


def table_examples() -> list[dict]:
    """Raw dollar answers behind specific examples in my-takeaways.md."""
    def answers(rs, q):
        return sorted(r["answer"] for r in rs if r["question"] == q)

    s1 = lambda f: [r for r in S1 if r["fact_set"] == ([f] if f else [])]
    nine = [r for r in S2 if len(r["fact_set"]) == 9]
    pair = lambda a, b: [r for r in S2 if r["fact_set"] == [a, b]]
    ex = [
        ("nonstop flight, no memory", answers(s1(None), "nonstop_flight")),
        ("nonstop flight, Lyft memory (B) alone", answers(s1("B"), "nonstop_flight")),
        ("nonstop flight, cleaner memory (H) alone", answers(s1("H"), "nonstop_flight")),
        ("general question, valet memory (F) alone", answers(s1("F"), "general")),
        ("train delay, valet memory (F) alone", answers(s1("F"), "train_delay")),
        ("weekend gig (4 h), declined-shift memory (G) alone", answers(s1("G"), "weekend_gig")),
        ("weekend gig (4 h), all nine memories", answers(nine, "weekend_gig")),
        ("general question, all nine memories", answers(nine, "general")),
        ("priority rideshare, Lyft + cleaner (B, H)", answers(pair("B", "H"), "priority_pickup")),
    ]
    bd = pair("B", "D")
    flagged = sum(has(r"contradict|inconsisten|conflict|doesn.t add up|paradox|mixed signal", r["thinking"]) for r in bd)
    rows = [{"example": k, "answers": " ".join(fmt_money(a) for a in v)} for k, v in ex]
    rows.append({"example": "Lyft + toll (B, D) traces that flag a contradiction", "answers": f"{flagged} of {len(bd)}"})
    return rows


# ----------------------------------------------------------------------------- outputs
def write_csv(name: str, rows: list[dict]) -> None:
    OUT.mkdir(exist_ok=True)
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.0f}%" if n else "–"


def svg_selection(sel: list[dict]) -> str:
    order = list("HCDBFAGIE")
    cw, ch, left, top = 70, 34, 300, 118
    w = left + cw * len(order) + 30
    h = top + ch * len(sel) + 74
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'font-family="Helvetica, Arial, sans-serif" font-size="13">',
         f'<rect width="{w}" height="{h}" fill="white"/>',
         '<text x="20" y="28" font-size="16" font-weight="bold">Which remembered choice does each question pull in?</text>',
         '<text x="20" y="48" font-size="12" fill="#444">Share of calls whose answer copies that memory\'s $/hour '
         '(and no other shown memory\'s), among calls where it was shown with 1-8 others.</text>']
    for j, f in enumerate(order):
        x = left + j * cw + cw / 2
        color = "#0f766e" if f in FLOOR else "#c2410c" if f in CEIL else "#6d28d9"
        sign = "≥" if f in FLOOR else "≤" if f in CEIL else "="
        p.append(f'<text x="{x:.0f}" y="{top - 44}" text-anchor="middle" font-weight="bold" fill="{color}">{f}</text>')
        words = SHORT[f].split(" ")
        line1, line2 = " ".join(words[:2]), " ".join(words[2:])
        p.append(f'<text x="{x:.0f}" y="{top - 30}" text-anchor="middle" font-size="10">{html.escape(line1)}</text>')
        p.append(f'<text x="{x:.0f}" y="{top - 19}" text-anchor="middle" font-size="10">{html.escape(line2)}</text>')
        p.append(f'<text x="{x:.0f}" y="{top - 6}" text-anchor="middle" font-size="10" fill="#555">'
                 f'{sign}${RATE[f]:g}/h</text>')
    for i, row in enumerate(sel):
        y = top + i * ch
        p.append(f'<text x="{left - 10}" y="{y + 21}" text-anchor="end">{QSHORT[row["question"]]}</text>')
        for j, f in enumerate(order):
            k, n = row[f"{f}_selected"], row[f"{f}_shown"]
            v = k / n
            shade = tuple(round(255 + (c - 255) * min(1.0, v * 1.15)) for c in (37, 99, 235))
            x = left + j * cw
            p.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="4" '
                     f'fill="rgb{shade}"/>')
            if f in row["predicted"]:
                p.append(f'<rect x="{x + 3}" y="{y + 3}" width="{cw - 6}" height="{ch - 6}" rx="3" fill="none" '
                         f'stroke="#d97706" stroke-width="2" stroke-dasharray="4 3"/>')
            weight = ' font-weight="bold"' if f == row["top_memory"] else ""
            color = "white" if v > 0.45 else "#111"
            p.append(f'<text x="{x + cw / 2:.0f}" y="{y + 21}" text-anchor="middle" fill="{color}"{weight}>'
                     f'{100 * v:.0f}%</text>')
    fy = top + ch * len(sel) + 22
    p.append(f'<text x="20" y="{fy}" font-size="11" fill="#444">Bold = most-selected memory for that question. '
             'Dashed outline = the memory we predicted before the run. Colour of letter: green = floor '
             '(paid money to save time),</text>')
    shown = [row[f"{f}_shown"] for row in sel for f in MEMORY_IDS]
    calls = sum(1 for r in S2 if len(r["fact_set"]) >= 2)
    p.append(f'<text x="20" y="{fy + 15}" font-size="11" fill="#444">orange = ceiling (spent time to save money), '
             f'purple = exact (wage). Qwen3-8B (4-bit), thinking on; {calls:,} calls with 2-9 memories; '
             f'each memory shown {min(shown)}-{max(shown)} times per question.</text>')
    p.append(f'<text x="20" y="{fy + 30}" font-size="11" fill="#444">Generated by analysis/make_results.py '
             'from runs/s2_combos/records.jsonl.</text>')
    p.append("</svg>")
    return "\n".join(p) + "\n"


def markdown(t: dict) -> str:
    sel, summ = t["selection"], t["selection_summary"]
    L = ["# Results", "",
         "Generated by `python analysis/make_results.py` from the saved runs in `runs/`. Do not edit by hand.", "",
         "Model: `mlx-community/Qwen3-8B-4bit`, thinking on, temperature 0.6, top-p 0.95, top-k 20. Each survey "
         "question is asked in its own fresh call. *Implied $/hour* = dollar answer / hours at stake. An answer "
         f"*copies* a memory if its implied $/hour is within {TOL:.0%} of the memory's; a memory is *selected* if the "
         "answer copies it and no other memory shown.", "",
         "## 0. The runs", "",
         "| run | records | ok | memories shown (count: calls) | first call | last call |",
         "|---|---:|---:|---|---|---|"]
    for r in t["runs"]:
        L.append(f"| `{r['run']}` | {r['records']} | {r['ok']} | {r['memories_shown']} | {r['first_call']} | {r['last_call']} |")
    L += ["", "`pilot01`, `timing_probe` and `timing_batch` were plumbing and speed checks; every table below uses "
          "`s1_single` and `s2_combos` only.", "",
          "## 1. Which memory each question selects (calls with 2+ memories)", "",
          f"{summ['calls']} calls from `s2_combos`. Cell = selected / shown. **Bold** = the question's most-selected "
          "memory; † = a memory we predicted for that question before the run (`hypothesized_facts` in the manifest).", "",
          "| question | " + " | ".join(f"{f} {SHORT[f]} ({BOUND[f]}, ${RATE[f]:g}/h)" for f in MEMORY_IDS) + " |",
          "|---|" + "---:|" * len(MEMORY_IDS)]
    for row in sel:
        cells = []
        for f in MEMORY_IDS:
            k, n = row[f"{f}_selected"], row[f"{f}_shown"]
            c = f"{pct(k, n)} ({k}/{n})" + ("†" if f in row["predicted"] else "")
            cells.append(f"**{c}**" if f == row["top_memory"] else c)
        L.append(f"| {QSHORT[row['question']]} | " + " | ".join(cells) + " |")
    L += ["", "![selection by question](selection_by_question.svg)", "",
          f"- Predicted memory is the most-selected one for {summ['top_was_predicted']}/10 questions.",
          f"- Predicted memories are selected in {pct(summ['predicted_selected'], summ['predicted_shown'])} of the calls "
          f"that show them ({summ['predicted_selected']}/{summ['predicted_shown']}); other memories in "
          f"{pct(summ['other_selected'], summ['other_shown'])} ({summ['other_selected']}/{summ['other_shown']}).",
          f"- Same two memories, ten questions ({summ['pairs']} pairs, 20 calls each): in {summ['pairs_both_used']} pairs "
          f"each memory is selected at least once; in {summ['pairs_one_always']} only one ever is. Within a pair, the "
          f"more-selected memory takes a median {summ['median_pair_dominance']:.0%} of the calls where one was selected.", "",
          "## 2. One memory at a time (`s1_single`, 50 calls per row)", "",
          "| memory | bound | $/h | answers that copy the rate | traces calling Sam cost-conscious / frugal / budget |",
          "|---|---|---:|---:|---:|"]
    for r in t["single"]:
        rate = f"{r['rate']:g}" if r["rate"] != "" else ""
        cp = f"{r['answers_copy_rate']}/50" if r["answers_copy_rate"] != "" else "–"
        L.append(f"| {r['memory']} {r['label']} | {r['bound']} | {rate} | {cp} | {r['trace_calls_sam_cost_conscious']}/50 |")
    L += ["", "### Median implied $/hour, one memory × question (5 calls per cell)", "",
          "| memory | " + " | ".join(QUESTIONS) + " |", "|---|" + "---:|" * len(QUESTIONS)]
    for r in t["single_medians"]:
        L.append(f"| {r['memory']} | " + " | ".join(f"{r[q]:g}" for q in QUESTIONS) + " |")
    L += ["", "## 3. More memories: pick one, don't average (all 1,640 calls)", "",
          "| memories shown | calls | answer copies a shown rate | answer = mean of shown rates | median trace words | median $/h, general question |",
          "|---:|---:|---:|---:|---:|---:|"]
    for r in t["by_count"]:
        c = f"{pct(r['answer_copies_a_shown_rate'], r['calls'])} ({r['answer_copies_a_shown_rate']}/{r['calls']})" if r["memories_shown"] else "–"
        m = f"{r['answer_equals_mean_of_shown_rates']}/{r['calls']}" if r["memories_shown"] >= 2 else "–"
        L.append(f"| {r['memories_shown']} | {r['calls']} | {c} | {m} | {r['median_trace_words']:g} | {r['median_general_question']:g} |")
    two = t["by_count"][2]
    L += ["", "The 1-memory row is the 450 stage-1 calls plus 40 calls that start a ladder in `s2_combos`. "
          f"With two memories, {two['of_which_also_copy_a_shown_rate']} of the {two['answer_equals_mean_of_shown_rates']} "
          "answers at the mean also copy one of the two rates (e.g. wage $19.23 and cleaner $20 have a midpoint "
          "within 3% of both).", "",
          "### With 3+ memories: how often each memory is selected when shown", "",
          "| memory | bound | $/h | selected / shown |", "|---|---|---:|---:|"]
    for r in t["wins"]:
        L.append(f"| {r['memory']} {r['label']} | {r['bound']} | {r['rate']:g} | {pct(r['selected'], r['shown'])} ({r['selected']}/{r['shown']}) |")
    pos = t["position"]
    L += ["", "Position of the selected memory in the list shown (observed vs. expected if position did not matter): "
          + ", ".join(f"{k} {o} vs {e}" for k, (o, e) in pos.items()) + ".", "",
          "### What the traces do with 3+ memories (keyword-coded)", "",
          "| move | traces |", "|---|---:|"]
    for r in t["moves"]:
        L.append(f"| {r['move']} | {pct(r['traces'], r['of'])} ({r['traces']}/{r['of']}) |")
    L += ["", "## 4. One floor memory plus one ceiling memory (pairs)", "", "| answer | count |", "|---|---:|"]
    for r in t["floor_ceiling"]:
        L.append(f"| {r['outcome']} | {r['answers']} ({pct(r['answers'], r['of'])}) |")
    L += ["", "## 5. Computing a rate is not choosing it (all calls showing the memory)", "",
          "| memory | calls shown | trace writes out its $/h | answer copies its $/h |", "|---|---:|---:|---:|"]
    for r in t["computed"]:
        L.append(f"| {r['memory']} {r['label']} | {r['calls_shown']} | {pct(r['trace_writes_its_rate'], r['calls_shown'])} "
                 f"({r['trace_writes_its_rate']}) | {pct(r['answer_copies_its_rate'], r['calls_shown'])} ({r['answer_copies_its_rate']}) |")
    L += ["", "## 6. Being paid to give up time vs. paying to save it (median implied $/hour)", "",
          "| calls | accept pay to give up time (weekend gig, study) | pay to save time (flight, groceries, bookshelf, theme park) |",
          "|---|---:|---:|"]
    for r in t["wta"]:
        L.append(f"| {r['calls']} | {r['median_accept_pay_to_give_up_time']:g} | {r['median_pay_to_save_time']:g} |")
    L += ["", "## 7. Raw answers behind examples in the write-up (dollars)", "", "| example | answers |", "|---|---|"]
    for r in t["examples"]:
        L.append(f"| {r['example']} | {r['answers']} |")
    return "\n".join(L) + "\n"


def build() -> dict:
    sel = table_selection()
    return {"runs": table_runs(), "selection": sel, "selection_summary": selection_summary(sel),
            "single": table_single(), "single_medians": table_single_medians(), "by_count": table_by_count(),
            "wins": table_wins(), "position": position_check(), "moves": table_trace_moves(),
            "floor_ceiling": table_floor_ceiling(), "computed": table_computed_vs_used(), "wta": table_wta_wtp(),
            "examples": table_examples()}


def main() -> None:
    t = build()
    write_csv("runs.csv", t["runs"])
    write_csv("selection_by_question.csv", t["selection"])
    write_csv("single_memory.csv", t["single"])
    write_csv("single_memory_medians.csv", t["single_medians"])
    write_csv("by_number_of_memories.csv", t["by_count"])
    write_csv("wins_3plus_memories.csv", t["wins"])
    write_csv("floor_plus_ceiling.csv", t["floor_ceiling"])
    write_csv("computed_vs_used.csv", t["computed"])
    write_csv("trace_moves_3plus.csv", t["moves"])
    write_csv("wta_vs_wtp.csv", t["wta"])
    write_csv("examples.csv", t["examples"])
    (OUT / "selection_by_question.svg").write_text(svg_selection(t["selection"]))
    (OUT / "RESULTS.md").write_text(markdown(t))
    print(f"wrote results to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
