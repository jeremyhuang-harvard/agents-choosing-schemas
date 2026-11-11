"""Run the survey. Append-only and resumable at the cell level.

    uv run --extra mlx python -m value_of_time.run --stages baseline single --reps 5 --engine mlx --batch-size 8 --run-id s1
    uv run python -m value_of_time.run --stages baseline single --reps 1 --engine mock --run-id smoke

One record = one (condition, question, rep) answered in its own fresh call. With --batch-size > 1 the
independent calls are decoded side by side (continuous batching); each has its own context and KV cache.

Layout: runs/<run_id>/manifest.json, runs/<run_id>/records.jsonl (one line per attempt, never rewritten).
A cell is complete when some attempt has status == "ok"; failed cells are retried on resume.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import random
import subprocess
import sys
import time
from pathlib import Path

from .design import STAGES, build_cells
from .engines import MLXEngine, MockEngine, MOCK_WARNING
from .parse import facts_mentioned, parse_single, split_thinking
from .prompt import build_prompt
from .stimuli import FACTS, PERSONA, QUESTION_BY_ID, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def completed_cells(path: Path) -> set[str]:
    done: set[str] = set()
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("status") == "ok":
                    done.add(r["cell_id"])
    return done


def make_record(engine, cell, prompt: str, raw: str, secs: float, err: str | None, batch: dict | None) -> dict:
    thinking, answer_text, closed = split_thinking(raw)
    answer, notes = parse_single(answer_text)
    problems = [n for n in notes if not n.startswith("extra_text")]
    warnings = [n for n in notes if n.startswith("extra_text")]
    if err:
        problems.append(err)
    if not closed:
        problems.append("thinking_not_closed")
    status = "ok" if not problems else "failed"
    hours = QUESTION_BY_ID[cell.question].hours
    return {
        **dataclasses.asdict(cell),
        "engine": engine.name,
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "seconds": secs,
        "batch": batch,
        "status": status,
        "problems": problems,
        "warnings": warnings,
        "prompt": prompt,
        "raw": raw,
        "thinking": thinking,
        "answer_text": answer_text,
        "answer": answer,
        "implied_hourly": None if answer is None else round(answer / hours, 2),
        "facts_mentioned": facts_mentioned(thinking, cell.fact_set),
        "thinking_chars": len(thinking),
        **({"warning": MOCK_WARNING} if engine.name == "mock" else {}),
    }


def run_cell(engine, cell) -> dict:
    prompt = build_prompt(cell)
    t0 = time.time()
    try:
        raw = engine.generate(prompt, cell.seed)
        err = None
    except Exception as e:  # keep the failure on record
        raw, err = "", f"{type(e).__name__}: {e}"
    return make_record(engine, cell, prompt, raw, round(time.time() - t0, 1), err, None)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="+", default=["baseline", "single"], choices=STAGES)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--ladders", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--engine", choices=["mock", "mlx"], default="mock")
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--questions", nargs="+", default=None, help="subset of question ids")
    ap.add_argument("--limit", type=int, default=None, help="run at most N pending cells")
    ap.add_argument("--batch-size", type=int, default=1,
                    help=">1 = continuous batching: independent calls decoded side by side (never share context)")
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args(argv)

    engine = MockEngine() if a.engine == "mock" else MLXEngine(model_id=a.model or MLXEngine.model_id,
                                                               max_tokens=a.max_tokens)
    cells = build_cells(tuple(a.stages), a.reps, a.ladders, a.seed,
                        tuple(a.questions) if a.questions else None)
    out_dir = ROOT / "runs" / a.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = {
        "run_id": a.run_id, "created": dt.datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit(), "argv": sys.argv, "args": vars(a), "engine": engine.config(),
        "n_cells": len(cells), "persona": PERSONA,
        "facts": [dataclasses.asdict(f) for f in FACTS], "questions": [dataclasses.asdict(q) for q in QUESTIONS],
    }
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if (old["args"]["stages"], old["args"]["reps"], old["args"]["seed"], old["engine"].get("model_id")) != \
           (manifest["args"]["stages"], manifest["args"]["reps"], manifest["args"]["seed"], manifest["engine"].get("model_id")):
            sys.exit("run-id exists with a different design/model; use a new --run-id")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2))

    rec_path = out_dir / "records.jsonl"
    done = completed_cells(rec_path)
    pending = [c for c in cells if c.cell_id not in done][: a.limit]
    print(f"{len(cells)} cells, {len(done)} done, running {len(pending)}", flush=True)

    def write(i: int, rec: dict) -> None:
        with rec_path.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"[{i}/{len(pending)}] {rec['cell_id']} {rec['status']} {rec['seconds']}s "
              f"ans={rec['answer']} think={rec['thinking_chars']}ch {rec['problems'] or ''}", flush=True)

    if a.batch_size <= 1:
        for i, cell in enumerate(pending, 1):
            write(i, run_cell(engine, cell))
        return

    # Shuffle within stage so concurrent sequences mix conditions and questions (no condition-aligned batches).
    session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    rng = random.Random(f"{a.seed}|{session}")
    stage_rank = {s: i for i, s in enumerate(a.stages)}
    pending = sorted(pending, key=lambda c: (stage_rank[c.stage], rng.random()))
    by_id = {c.cell_id: c for c in pending}
    prompts = {c.cell_id: build_prompt(c) for c in pending}
    if hasattr(engine, "batch_seed"):
        engine.batch_seed = rng.randrange(2**31)
    started: dict[str, float] = {}

    def jobs():
        for c in pending:
            started[c.cell_id] = time.time()
            yield c.cell_id, prompts[c.cell_id]

    batch_meta = {"mode": "continuous", "size": a.batch_size, "session": session,
                  "batch_seed": getattr(engine, "batch_seed", None)}
    for i, (cid, raw) in enumerate(engine.generate_stream(jobs(), a.batch_size), 1):
        secs = round(time.time() - started[cid], 1)
        write(i, make_record(engine, by_id[cid], prompts[cid], raw, secs, None, batch_meta))


if __name__ == "__main__":
    main()
