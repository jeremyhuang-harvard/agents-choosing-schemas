import json
import re

from value_of_time import analyze, run
from value_of_time.design import build_cells, conditions
from value_of_time.parse import bound_consistent, nearest_fact, parse_single, split_thinking, to_number
from value_of_time.prompt import build_prompt
from value_of_time.stimuli import FACTS, PERSONA, QUESTIONS


def test_persona_has_no_money_time_or_place_signal():
    assert not re.search(r"\$|\d+ ?(minutes|hours)|salary|income|wage", PERSONA, re.I)
    assert not re.search(r"New York|Manhattan|Jersey|Ohio|Columbus", PERSONA)


def test_no_place_names_in_any_stimulus():
    text = " ".join([f.text for f in FACTS] + [q.text for q in QUESTIONS])
    assert not re.search(r"New York|Manhattan|Jersey|Ohio|Columbus", text)


def test_fact_values_are_distinct():
    vals = [f.implied_hourly for f in FACTS]
    assert len(set(vals)) == len(vals)
    assert all(f.bound in {"point", "lower", "upper"} for f in FACTS)
    assert len(QUESTIONS) == 10


def test_condition_counts():
    n = len(FACTS)
    assert len(conditions(("baseline", "single"))) == 1 + n
    assert len(conditions(("pairs",))) == n * (n - 1) // 2
    assert len(conditions(("full",))) == 1


def test_one_question_per_cell_and_shared_order_within_rep():
    cells = build_cells(("baseline", "single", "pairs"), reps=2)
    assert len(cells) == (1 + len(FACTS) + len(FACTS) * (len(FACTS) - 1) // 2) * 2 * len(QUESTIONS)
    assert cells == build_cells(("baseline", "single", "pairs"), reps=2)
    assert len({c.cell_id for c in cells}) == len(cells)
    orders = {}
    for c in cells:
        assert sorted(c.fact_order) == list(c.fact_set)
        orders.setdefault((c.fact_set, c.rep), set()).add(c.fact_order)
    assert all(len(v) == 1 for v in orders.values())


def test_prompt_contains_exactly_one_question_and_no_number_exemplar():
    cell = [c for c in build_cells(("pairs",), reps=1) if c.fact_set == ("B", "D")][0]
    p = build_prompt(cell)
    asked = [q for q in QUESTIONS if q.text in p]
    assert len(asked) == 1 and asked[0].id == cell.question
    assert not re.search(r"\d", p.strip().splitlines()[-1])
    assert "relevant" not in p.lower()


def test_parsing():
    t, a, closed = split_thinking("<think>hmm $40,000</think>\n\n45")
    assert closed and t == "hmm $40,000" and a == "45"
    assert parse_single("$1,200") == (1200.0, [])
    assert parse_single("10-20")[0] is None
    assert parse_single("")[1] == ["empty_answer"]
    v, notes = parse_single("I would pay 30")
    assert v == 30.0 and notes[0].startswith("extra_text")
    assert split_thinking("<think>cut off")[2] is False
    assert to_number(True) is None


def test_matching_and_bounds():
    assert nearest_fact(30.5, ("B", "D")) == "B"
    assert nearest_fact(100, ("B", "D")) is None
    assert bound_consistent(25, "B") is True and bound_consistent(40, "B") is False
    assert bound_consistent(40, "D") is True


def test_mock_end_to_end_and_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    args = ["--stages", "baseline", "single", "--reps", "1", "--engine", "mock", "--run-id", "t"]
    run.main(args)
    recs = [json.loads(l) for l in (tmp_path / "runs/t/records.jsonl").read_text().splitlines()]
    assert len(recs) == (1 + len(FACTS)) * len(QUESTIONS) and all(r["status"] == "ok" for r in recs)
    assert all(r["warning"] for r in recs)
    run.main(args)
    assert len((tmp_path / "runs/t/records.jsonl").read_text().splitlines()) == len(recs)  # nothing rerun
    analyze.main([str(tmp_path / "runs/t")])
    assert "MOCK" in (tmp_path / "runs/t/summary.md").read_text()
    assert "# Question `general`" in (tmp_path / "runs/t/traces.md").read_text()
