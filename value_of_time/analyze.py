"""Summarize a run. One record = one question answered in its own call.

Outputs in the run directory:
- answers.csv : one row per completed call (implied $/h, matched fact, bound consistency, facts mentioned)
- summary.md  : median implied $/h by condition x question; mention rates; bound-consistency rates
- traces.md   : every thinking trace, grouped question -> condition, with the answer

    uv run python -m value_of_time.analyze runs/<run_id>
"""
from __future__ import annotations

import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

from .engines import MOCK_WARNING
from .parse import bound_consistent, nearest_fact
from .stimuli import FACT_BY_ID, QUESTION_BY_ID, QUESTIONS


def load_ok(run_dir: Path) -> list[dict]:
    latest: dict[str, dict] = {}
    for line in (run_dir / "records.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["status"] == "ok":
            latest[r["cell_id"]] = r
    return list(latest.values())


def count_failed(run_dir: Path) -> int:
    return sum(1 for l in (run_dir / "records.jsonl").read_text().splitlines() if json.loads(l)["status"] != "ok")


def cond_name(r: dict) -> str:
    return "-".join(r["fact_set"]) or "none"


def rows(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        shown = tuple(r["fact_set"])
        h = r["implied_hourly"]
        row = {"cell_id": r["cell_id"], "stage": r["stage"], "condition": cond_name(r), "n_facts": len(shown),
               "fact_order": "-".join(r["fact_order"]), "rep": r["rep"], "question": r["question"],
               "q_domain": QUESTION_BY_ID[r["question"]].domain, "answer": r["answer"], "implied_hourly": h,
               "matched_fact": nearest_fact(h, shown), "thinking_chars": r["thinking_chars"],
               "seconds": r["seconds"]}
        for f in FACT_BY_ID:
            row[f"shown_{f}"] = f in shown
            row[f"mentioned_{f}"] = r["facts_mentioned"].get(f) if f in shown else None
            row[f"consistent_{f}"] = bound_consistent(h, f) if f in shown else None
        out.append(row)
    return out


def _median(vals: list[float]) -> str:
    return f"{st.median(vals):.0f}" if vals else "–"


def main(argv: list[str] | None = None) -> None:
    run_dir = Path((argv or sys.argv[1:])[0])
    recs = load_ok(run_dir)
    is_mock = any(r.get("warning") for r in recs)
    rs = rows(recs)
    if rs:
        with (run_dir / "answers.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rs[0]))
            w.writeheader()
            w.writerows(rs)

    qids = [q.id for q in QUESTIONS]
    conds = sorted({r["condition"] for r in rs}, key=lambda c: (c != "none", len(c), c))
    by = defaultdict(list)
    for r in rs:
        if r["implied_hourly"] is not None:
            by[(r["condition"], r["question"])].append(r["implied_hourly"])

    md = [f"# Summary: {run_dir.name}", ""]
    if is_mock:
        md += [f"> **{MOCK_WARNING}**", ""]
    md += [f"{len(recs)} completed calls, {count_failed(run_dir)} failed attempts on record.", "",
           "## Median implied $/hour (rows = memories shown, cols = question; n per cell in parentheses)", ""]
    md.append("| memories | " + " | ".join(qids) + " |")
    md.append("|---" * (len(qids) + 1) + "|")
    for c in conds:
        md.append(f"| {c} | " + " | ".join(f"{_median(by[(c, q)])} ({len(by[(c, q)])})" for q in qids) + " |")

    md += ["", "## Memory values (for reading the table)", ""]
    for f in FACT_BY_ID.values():
        md.append(f"- **{f.id}** ({f.bound}, {f.implied_hourly:g} $/h{', mixed motive' if f.mixed_motive else ''}): {f.text}")

    md += ["", "## When a memory is shown, how often does the trace mention it? (rows = memory, cols = question)", ""]
    md.append("| memory | " + " | ".join(qids) + " |")
    md.append("|---" * (len(qids) + 1) + "|")
    for f in FACT_BY_ID:
        cells = []
        for q in qids:
            v = [r[f"mentioned_{f}"] for r in rs if r["question"] == q and r[f"shown_{f}"]]
            cells.append(f"{sum(v)}/{len(v)}" if v else "–")
        md.append(f"| {f} | " + " | ".join(cells) + " |")

    md += ["", "## Single-memory stage: is the answer consistent with the memory's bound?", ""]
    md.append("| memory | " + " | ".join(qids) + " |")
    md.append("|---" * (len(qids) + 1) + "|")
    for f in FACT_BY_ID:
        cells = []
        for q in qids:
            v = [r[f"consistent_{f}"] for r in rs if r["question"] == q and r["condition"] == f]
            cells.append(f"{sum(bool(x) for x in v)}/{len(v)}" if v else "–")
        md.append(f"| {f} | " + " | ".join(cells) + " |")
    (run_dir / "summary.md").write_text("\n".join(md) + "\n")

    tr = [f"# Thinking traces: {run_dir.name}", ""] + ([f"> **{MOCK_WARNING}**", ""] if is_mock else [])
    for q in QUESTIONS:
        qrecs = [r for r in recs if r["question"] == q.id]
        if not qrecs:
            continue
        tr += [f"# Question `{q.id}`", "", f"> {q.text}", "", f"(implied $/h = answer / {q.hours:g})", ""]
        for r in sorted(qrecs, key=lambda r: (len(r["fact_set"]), cond_name(r), r["rep"])):
            mem = ", ".join(r["fact_order"]) or "none"
            tr += [f"## memories: {mem} · rep {r['rep']} · answer **{r['answer']}** → {r['implied_hourly']} $/h", "",
                   r["thinking"] or "(no thinking)", ""]
    (run_dir / "traces.md").write_text("\n".join(tr) + "\n")
    print(f"wrote answers.csv, summary.md, traces.md in {run_dir} ({len(recs)} calls)")


if __name__ == "__main__":
    main()
