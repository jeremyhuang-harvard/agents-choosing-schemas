"""The saved run records must reproduce the numbers we report, and the repo must stay clean."""

import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_results", ROOT / "analysis" / "make_results.py")
assert spec is not None and spec.loader is not None
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)


def cell(rows, question, memory):
    row = next(r for r in rows if r["question"] == question)
    return row[f"{memory}_selected"], row[f"{memory}_shown"]


def test_run_inventory():
    runs = {r["run"]: r for r in mr.table_runs()}
    assert (runs["s1_single"]["records"], runs["s1_single"]["ok"]) == (500, 500)
    assert (runs["s2_combos"]["records"], runs["s2_combos"]["ok"]) == (1140, 1140)
    assert len(mr.ALL) == 1640


def test_headline_question_selects_memory():
    sel = mr.table_selection()
    assert cell(sel, "general", "H") == (34, 48)
    assert cell(sel, "priority_pickup", "B") == (29, 36)
    assert cell(sel, "theme_park", "C") == (49, 50)
    assert cell(sel, "furniture_assembly", "H") == (35, 48)
    assert cell(sel, "volunteer_or_donate", "A") == (15, 32)
    assert cell(sel, "general", "A") == (2, 32)
    tops = {r["question"]: r["top_memory"] for r in sel}
    assert tops == {"general": "H", "weekend_gig": "H", "research_study": "C", "nonstop_flight": "C",
                    "priority_pickup": "B", "grocery_delivery": "C", "furniture_assembly": "H",
                    "theme_park": "C", "train_delay": "C", "volunteer_or_donate": "H"}
    s = mr.selection_summary(sel)
    assert s["calls"] == 1100
    assert s["top_was_predicted"] == 3
    assert (s["predicted_selected"], s["predicted_shown"], s["other_selected"], s["other_shown"]) == (199, 638, 466, 2962)
    assert (s["pairs"], s["pairs_both_used"], s["median_pair_dominance"]) == (36, 24, 0.852)


def test_floor_memories_become_rates_ceiling_memories_become_traits():
    single = {r["memory"]: r for r in mr.table_single()}
    assert {f: single[f]["answers_copy_rate"] for f in "HCDF"} == {"H": 39, "C": 37, "D": 27, "F": 18}
    assert {f: single[f]["trace_calls_sam_cost_conscious"] for f in ["B", "E", "I", "none"]} == {
        "B": 48, "E": 46, "I": 49, "none": 14}
    assert {f: single[f]["answers_copy_rate"] for f in "BEI"} == {"B": 6, "E": 2, "I": 9}


def test_more_memories_means_picking_not_averaging():
    rows = {r["memories_shown"]: r for r in mr.table_by_count()}
    assert sum(rows[n]["answer_equals_mean_of_shown_rates"] for n in range(3, 10)) == 0
    assert sum(rows[n]["calls"] for n in range(3, 10)) == 380
    assert (rows[9]["answer_copies_a_shown_rate"], rows[9]["calls"]) == (19, 20)
    wins = {r["memory"]: (r["selected"], r["shown"]) for r in mr.table_wins()}
    assert wins["C"] == (144, 340) and wins["H"] == (104, 320) and wins["A"] == (9, 160)
    assert mr.position_check() == {"first": (69, 61), "middle": (190, 197), "last": (59, 61)}


def test_floor_plus_ceiling_lands_below_both():
    fc = {r["outcome"]: r["answers"] for r in mr.table_floor_ceiling()}
    assert fc == {"below both": 136, "equals the floor rate": 106, "equals the ceiling rate": 34,
                  "between the two": 12, "above both": 12}


def test_computing_is_not_choosing():
    c = {r["memory"]: r for r in mr.table_computed_vs_used()}
    assert (c["A"]["calls_shown"], c["A"]["trace_writes_its_rate"], c["A"]["answer_copies_its_rate"]) == (370, 248, 35)
    moves = {r["move"]: r["traces"] for r in mr.table_trace_moves()}
    assert moves["flags a conflict between memories"] == 160
    assert moves["says the value depends on context"] == 47


def test_committed_results_match_a_fresh_build():
    t = mr.build()
    assert mr.markdown(t) == (ROOT / "results" / "RESULTS.md").read_text()
    assert mr.svg_selection(t["selection"]) == (ROOT / "results" / "selection_by_question.svg").read_text()


def test_manifests_were_scrubbed_to_repo_relative_paths():
    for m in sorted((ROOT / "runs").glob("*/manifest.json")):
        assert json.loads(m.read_text())["argv"][0] == "value_of_time/run.py", m


def test_no_credentials_or_machine_paths_in_tracked_files():
    pattern = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|hf_[A-Za-z0-9]{30,}|/Users/[A-Za-z]|/home/[a-z]+/|"
                         r"BEGIN [A-Z ]*PRIVATE KEY")
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.split("\0")
    for name in filter(None, tracked):
        path = ROOT / name
        if path.name == "test_results.py":
            continue
        assert not pattern.search(path.read_bytes().decode("utf-8", errors="ignore")), name
