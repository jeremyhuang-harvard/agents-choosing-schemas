"""Condition generator.

A condition is a set of fact ids shown in the memory slot. Each survey question is asked in its OWN call
(no other questions visible, no shared conversation), so a cell is (condition, rep, question). Within a
(condition, rep), all ten questions see the same fact order, so cross-question differences within a rep
are not driven by order; order varies across reps.

Stages
- baseline : no facts
- single   : each fact alone
- pairs    : every pair of facts
- ladder   : add facts one at a time along K random orders (deduplicated against earlier stages)
- full     : all facts

Cells are ordered stage -> rep -> condition -> question, so a partially finished run stays balanced.
"""
from __future__ import annotations

import hashlib
import itertools
import random
from dataclasses import dataclass

from .stimuli import FACTS, QUESTIONS

STAGES = ("baseline", "single", "pairs", "ladder", "full")


def stable_seed(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:4], "big")


@dataclass(frozen=True)
class Cell:
    cell_id: str
    stage: str
    fact_set: tuple[str, ...]     # sorted, identifies the condition
    fact_order: tuple[str, ...]   # order shown to the model (fixed within condition x rep)
    question: str
    rep: int
    seed: int


def ladder_orders(n_ladders: int = 3, base_seed: int = 0) -> list[list[str]]:
    ids = [f.id for f in FACTS]
    out = []
    for k in range(n_ladders):
        order = ids[:]
        random.Random(stable_seed(base_seed, "ladder", k)).shuffle(order)
        out.append(order)
    return out


def conditions(stages: tuple[str, ...], n_ladders: int = 3, base_seed: int = 0) -> list[tuple[str, tuple[str, ...]]]:
    ids = [f.id for f in FACTS]
    out: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, ...]] = set()

    def add(stage: str, fs: tuple[str, ...]) -> None:
        key = tuple(sorted(fs))
        if key not in seen:
            seen.add(key)
            out.append((stage, key))

    for stage in stages:
        if stage == "baseline":
            add(stage, ())
        elif stage == "single":
            for i in ids:
                add(stage, (i,))
        elif stage == "pairs":
            for p in itertools.combinations(ids, 2):
                add(stage, p)
        elif stage == "ladder":
            for order in ladder_orders(n_ladders, base_seed):
                for j in range(1, len(order) + 1):
                    add(stage, tuple(order[:j]))
        elif stage == "full":
            add(stage, tuple(ids))
        else:
            raise ValueError(f"unknown stage {stage!r}; choose from {STAGES}")
    return out


def build_cells(stages: tuple[str, ...], reps: int, n_ladders: int = 3, base_seed: int = 0,
                questions: tuple[str, ...] | None = None) -> list[Cell]:
    qids = questions or tuple(q.id for q in QUESTIONS)
    conds = conditions(stages, n_ladders, base_seed)
    cells = []
    for stage in stages:
        stage_conds = [fs for s, fs in conds if s == stage]
        for rep in range(reps):
            for fs in stage_conds:
                cond = "-".join(fs) or "none"
                fo = list(fs)
                random.Random(stable_seed(base_seed, cond, rep, "order")).shuffle(fo)
                for q in qids:
                    cells.append(Cell(f"{cond}__{q}__r{rep}", stage, fs, tuple(fo), q, rep,
                                      stable_seed(base_seed, cond, q, rep)))
    ids = [c.cell_id for c in cells]
    assert len(ids) == len(set(ids)), "duplicate cell ids"
    return cells
