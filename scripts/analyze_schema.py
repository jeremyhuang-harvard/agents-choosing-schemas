"""Schema-selection and trace analysis across s1_single + s2_combos. Prints numbers; writes docs/tldr_data.json.

    PYTHONPATH=. uv run python scripts/analyze_schema.py
"""
from __future__ import annotations

import collections
import json
import re
import statistics as st
from pathlib import Path

from value_of_time.stimuli import FACT_BY_ID, QUESTION_BY_ID, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
V = {f.id: f.implied_hourly for f in FACT_BY_ID.values()}
FLOOR = {f for f, x in FACT_BY_ID.items() if x.bound == "lower"}
CEIL = {f for f, x in FACT_BY_ID.items() if x.bound == "upper"}
QIDS = [q.id for q in QUESTIONS]


def load(p):
    out = {}
    for line in open(p):
        r = json.loads(line)
        if r["status"] == "ok":
            out[r["cell_id"]] = r
    return list(out.values())


S1 = load(ROOT / "runs/s1_single/records.jsonl")
S2 = load(ROOT / "runs/s2_combos/records.jsonl")
ALL = S1 + S2
hit = lambda h, f: h is not None and abs(h - V[f]) / V[f] <= 0.03


def winner(r):
    hs = [f for f in r["fact_set"] if hit(r["implied_hourly"], f)]
    return hs[0] if len(hs) == 1 else (None if not hs else "tie")


D = {}

# ---------- 1. schema selection by question (pairs: every memory shown equally often) ----------
pairs = [r for r in S2 if len(r["fact_set"]) == 2]
multi = [r for r in S2 if len(r["fact_set"]) >= 2]
sel = {}
for q in QIDS:
    for f in V:
        sh = [r for r in multi if r["question"] == q and f in r["fact_set"]]
        w = sum(winner(r) == f for r in sh)
        sel[(q, f)] = (w, len(sh))
D["sel"] = {f"{q}|{f}": v for (q, f), v in sel.items()}
print("== win rate by question x memory (all multi-memory calls) ==")
print("question".ljust(20), " ".join(f.rjust(5) for f in V))
for q in QIDS:
    print(q.ljust(20), " ".join(f"{sel[(q,f)][0]/sel[(q,f)][1]:5.0%}" for f in V))

# top schema per question
top = {q: max(V, key=lambda f: sel[(q, f)][0] / sel[(q, f)][1]) for q in QIDS}
print("top memory per question:", top)
D["top"] = top

# hypothesized (pre-registered in stimuli.py before the run) vs not
hyp_w = hyp_n = oth_w = oth_n = 0
for q in QIDS:
    hyp = set(QUESTION_BY_ID[q].hypothesized_facts)
    for f in V:
        w, n = sel[(q, f)]
        if f in hyp:
            hyp_w += w; hyp_n += n
        else:
            oth_w += w; oth_n += n
print(f"hypothesized memory win rate {hyp_w}/{hyp_n}={hyp_w/hyp_n:.1%}; others {oth_w}/{oth_n}={oth_w/oth_n:.1%}")
D["hyp"] = [hyp_w, hyp_n, oth_w, oth_n]

# per-question hypothesis check: did a hypothesized memory have the top win rate?
hyp_top = {q: top[q] in QUESTION_BY_ID[q].hypothesized_facts for q in QIDS}
print("hypothesized memory is top:", hyp_top, sum(hyp_top.values()), "/ 10")
D["hyp_top"] = hyp_top

# domain match
mdom = {f: FACT_BY_ID[f].domain for f in V}
qdom = {q: QUESTION_BY_ID[q].domain for q in QIDS}
dm = collections.Counter()
for (q, f), (w, n) in sel.items():
    k = "match" if mdom[f] == qdom[q] else "no match"
    dm[k + "_w"] += w; dm[k + "_n"] += n
print("domain match win", dm["match_w"], dm["match_n"], f"{dm['match_w']/dm['match_n']:.1%}",
      "no match", dm["no match_w"], dm["no match_n"], f"{dm['no match_w']/dm['no match_n']:.1%}")
D["dom"] = [dm["match_w"], dm["match_n"], dm["no match_w"], dm["no match_n"]]

# ---------- 2. does switching the question switch the selected memory? (pairs) ----------
flip = collections.Counter()
examples = []
by_pair = collections.defaultdict(lambda: collections.defaultdict(list))
for r in pairs:
    w = winner(r)
    if w in V:
        by_pair[tuple(r["fact_set"])][r["question"]].append(w)
for p in sorted({tuple(r["fact_set"]) for r in pairs}):
    ws = [w for q in by_pair[p] for w in by_pair[p][q]]
    used = set(ws)
    k = "both used (question decides)" if len(used) == 2 else "one always" if len(used) == 1 else "neither"
    flip[k] += 1
    if len(used) == 2:
        qa = {q: collections.Counter(by_pair[p][q]).most_common(1)[0][0] for q in by_pair[p]}
        examples.append((p, qa))
print("pairs:", dict(flip))
D["flip"] = dict(flip)
for p, qa in examples[:40]:
    a = [q for q, w in qa.items() if w == p[0]]; b = [q for q, w in qa.items() if w == p[1]]
    print(" ", p, p[0], "<-", a, "|", p[1], "<-", b)
D["flip_examples"] = [[list(p), qa] for p, qa in examples]

# dominance across all questions: for each pair, share of decided calls won by the more-winning memory
dom_share = []
for p in by_pair:
    ws = [w for q in by_pair[p] for w in by_pair[p][q]]
    if ws:
        dom_share.append(max(collections.Counter(ws).values()) / len(ws))
print("median within-pair dominance", st.median(dom_share))

# ---------- 3. trace reasoning moves ----------
RATE_PAT = {
    "A": r"19\.2|19 (per|an|/) ?h", "B": r"\$?30(\.0+)? ?(per|an|/|a) ?h", "C": r"\$?15(\.0+)? ?(per|an|/|a) ?h",
    "D": r"\$?36(\.0+)? ?(per|an|/|a) ?h", "E": r"\$?45(\.0+)? ?(per|an|/|a) ?h", "F": r"\$?210(\.0+)? ?(per|an|/|a) ?h",
    "G": r"\$?29(\.0+)? ?(per|an|/|a) ?h|28\.8", "H": r"\$?20(\.0+)? ?(per|an|/|a) ?h", "I": r"\$?18(\.0+)? ?(per|an|/|a) ?h",
}
MOVES = {
    "Computes an hourly rate": r"per hour|an hour|/hour|hourly rate|\$/h",
    "Trait: cost-conscious / frugal": r"cost[- ]conscious|frugal|budget[- ]conscious|thrifty|careful with money|money[- ]conscious",
    "Uses persona for income/status": r"(rescue dog|recreational|soccer league|31[- ]year).{0,120}(income|afford|money|budget|salary|earn)|(income|afford|salary|earn).{0,120}(rescue dog|recreational|soccer league|31[- ]year)",
    "Appeals to what's 'common/typical'": r"common (answer|figure|amount)|typical (person|answer|rate|amount)|most people|average person",
    "Mentions averaging": r"\baverag(e|ing)\b",
    "Flags a conflict between memories": r"contradict|inconsisten|conflict|doesn.t add up|mixed signal",
    "Cites a nonexistent example / prior turn": r"example (response|answer)|previous (interaction|answer|response)",
    "Says the value depends on context": r"depends on (the )?(context|situation|activity)|different (contexts|situations)|varies (by|with|depending)",
}
def moves(rs):
    return {k: sum(bool(re.search(p, re.sub(r"\s+", " ", r["thinking"]), re.I)) for r in rs) / len(rs) for k, p in MOVES.items()}

groups = {
    "No memory": [r for r in S1 if not r["fact_set"]],
    "1 floor memory": [r for r in S1 if r["fact_set"] and r["fact_set"][0] in FLOOR],
    "1 ceiling memory": [r for r in S1 if r["fact_set"] and r["fact_set"][0] in CEIL],
    "Wage only": [r for r in S1 if r["fact_set"] == ["A"]],
    "2 memories": [r for r in S2 if len(r["fact_set"]) == 2],
    "3–9 memories": [r for r in S2 if len(r["fact_set"]) >= 3],
}
mv = {g: moves(rs) for g, rs in groups.items()}
D["moves"] = mv
D["moves_n"] = {g: len(rs) for g, rs in groups.items()}
print("\n== reasoning moves (share of traces) ==")
for k in MOVES:
    print(k.ljust(42), " ".join(f"{mv[g][k]:5.0%}" for g in groups))
print("groups:", list(groups))

# ---------- 4. stated vs actual: trace computes memory's rate vs answer uses it ----------
sa = {}
for f in V:
    rs = [r for r in ALL if f in r["fact_set"] and len(r["fact_set"]) >= 1]
    comp = [bool(re.search(RATE_PAT[f], r["thinking"], re.I)) for r in rs]
    used = [hit(r["implied_hourly"], f) for r in rs]
    both = sum(c and u for c, u in zip(comp, used))
    sa[f] = {"n": len(rs), "computed": sum(comp), "used": sum(used), "computed_not_used": sum(c and not u for c, u in zip(comp, used)),
             "used_given_computed": both / max(1, sum(comp))}
    print(f, sa[f])
D["stated_actual"] = sa

# ---------- 5. trace length and answer dispersion vs number of memories ----------
ln = {}
for n in range(0, 10):
    rs = [r for r in ALL if len(r["fact_set"]) == n]
    if rs:
        g = [r["implied_hourly"] for r in rs if r["question"] == "general"]
        ln[n] = {"think_words": st.median(len(r["thinking"].split()) for r in rs), "n": len(rs),
                 "copy": sum(any(hit(r["implied_hourly"], f) for f in r["fact_set"]) for r in rs) / len(rs) if n else None}
print(ln)
D["length"] = ln

# ---------- 6. WTA vs WTP ----------
wta = ["weekend_gig", "research_study"]; wtp = ["nonstop_flight", "grocery_delivery", "furniture_assembly", "theme_park"]
for lab, rs in [("no memory", [r for r in S1 if not r["fact_set"]]), ("wage only", [r for r in S1 if r["fact_set"] == ["A"]]),
                ("all calls", ALL)]:
    a = st.median(r["implied_hourly"] for r in rs if r["question"] in wta)
    b = st.median(r["implied_hourly"] for r in rs if r["question"] in wtp)
    print("WTA vs WTP", lab, a, b)
    D.setdefault("wta", {})[lab] = [a, b]

(ROOT / "docs/tldr_data.json").write_text(json.dumps(D, indent=1, default=str))
