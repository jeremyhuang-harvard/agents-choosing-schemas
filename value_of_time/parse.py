"""Split a Qwen3 thinking completion into trace + answer, parse answers, and tag facts mentioned in the trace."""
from __future__ import annotations

import json
import re
from typing import Any

from .stimuli import FACTS, QUESTION_BY_ID

_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def split_thinking(text: str) -> tuple[str, str, bool]:
    """Return (thinking, answer, thinking_closed)."""
    if "</think>" in text:
        think, answer = text.split("</think>", 1)
        return think.replace("<think>", "").strip(), answer.strip(), True
    if "<think>" in text:  # ran out of tokens mid-thought
        return text.replace("<think>", "").strip(), "", False
    return "", text.strip(), True


def _last_json_object(text: str) -> dict | None:
    dec = json.JSONDecoder()
    found = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            found = obj
    return found


def to_number(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        nums = _NUM.findall(v)
        if len(nums) == 1:  # refuse ranges / multiple numbers
            return float(nums[0].replace(",", ""))
    return None


def parse_single(answer_text: str) -> tuple[float | None, list[str]]:
    """Parse a one-question reply. Accepts '45', '$45', '45.00', '1,200', or {"answer": 45}."""
    t = answer_text.strip()
    if not t:
        return None, ["empty_answer"]
    obj = _last_json_object(t)
    if obj is not None and len(obj) == 1:
        t = str(next(iter(obj.values())))
    t = t.replace("$", "").strip().rstrip(".")
    v = to_number(t)
    if v is None:
        return None, [f"non_numeric:{answer_text[:80]!r}"]
    if not re.fullmatch(r"[\s\-\d,\.]*(dollars|usd)?[\s\.]*", t, flags=re.I):
        return v, [f"extra_text:{answer_text[:80]!r}"]
    return v, []


def parse_answers(answer_text: str, question_order: tuple[str, ...]) -> tuple[dict[str, float | None], list[str]]:
    """Map displayed keys Q1..Qn back to question ids. Returns (answers, problems)."""
    problems: list[str] = []
    obj = _last_json_object(answer_text)
    if obj is None:
        return {q: None for q in question_order}, ["no_json"]
    norm = {str(k).strip().upper(): v for k, v in obj.items()}
    out: dict[str, float | None] = {}
    for i, qid in enumerate(question_order, 1):
        raw = norm.get(f"Q{i}")
        val = to_number(raw)
        if raw is None:
            problems.append(f"missing_Q{i}")
        elif val is None:
            problems.append(f"non_numeric_Q{i}:{raw!r}")
        out[qid] = val
    return out, problems


def implied_hourly(answers: dict[str, float | None]) -> dict[str, float | None]:
    return {q: (None if v is None else round(v / QUESTION_BY_ID[q].hours, 2)) for q, v in answers.items()}


def facts_mentioned(thinking: str, shown: tuple[str, ...]) -> dict[str, bool]:
    """Keyword detection of each *shown* fact in the trace. Crude by design; audit against hand-coding."""
    t = thinking.lower()
    return {f.id: any(re.search(k, t) for k in f.keywords) for f in FACTS if f.id in shown}


def nearest_fact(hourly: float | None, shown: tuple[str, ...], tol: float = 0.10) -> str | None:
    """Which shown fact's implied $/h does this answer match (within tol, relative)? None if no match."""
    if hourly is None or not shown:
        return None
    best, best_err = None, tol
    for f in FACTS:
        if f.id in shown:
            err = abs(hourly - f.implied_hourly) / f.implied_hourly
            if err <= best_err:
                best, best_err = f.id, err
    return best


def bound_consistent(hourly: float | None, fact_id: str) -> bool | None:
    from .stimuli import FACT_BY_ID
    f = FACT_BY_ID[fact_id]
    if hourly is None:
        return None
    if f.bound == "upper":
        return hourly <= f.implied_hourly * 1.10
    if f.bound == "lower":
        return hourly >= f.implied_hourly * 0.90
    return abs(hourly - f.implied_hourly) / f.implied_hourly <= 0.25
