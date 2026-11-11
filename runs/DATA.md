# The data files

Every file the experiment wrote, as it wrote it. 1,665 model calls across five runs, each with the
exact prompt, the full raw completion (including Qwen3's `<think>` trace), the parsed answer and
timing. About 27 MB, all tracked in git.

```python
import json
recs = [json.loads(l) for l in open("runs/s2_combos/records.jsonl") if l.strip()]
```

**The one alteration.** Each `manifest.json` stored the absolute path of the script on our machine in
`argv[0]`, and `runs/queue.log` contains the same absolute paths in Python tracebacks. We replaced the
machine-specific prefix with nothing, so those paths now read as repo-relative (`value_of_time/run.py`,
`.venv/lib/python3.11/...`). No other byte of any run file was changed. `runs_pilot01.log` was moved from
the repository root into `runs/`.

---

## The five runs

| run | calls | what it was | used in results? |
|---|---:|---|---|
| `pilot01/` | 3 | First real-model test, 21 Oct 2026. **Earlier prompt design** (see below). | no |
| `timing_probe/` | 6 | Speed check: six no-memory calls, one at a time. | no |
| `timing_batch/` | 16 | Speed check for continuous batching (8 calls decoded side by side). | no |
| `s1_single/` | 500 | **Stage 1.** No memory, or exactly one of the nine; 10 questions × 5 samples. | yes |
| `s2_combos/` | 1,140 | **Stage 2.** All 36 pairs, plus three ladders that add memories one at a time up to all nine; 10 questions × 2 samples. | yes |

`results/` and every figure in `docs/` use `s1_single` and `s2_combos` only.

Two things about `s2_combos` that its manifest does not make obvious:

- The ladders start from a single memory, so 40 of its 1,140 calls show **one** memory (the
  ladders that start with C and with I). Calls with 2+ memories number 1,100.
- The `full` stage (all nine) was requested but adds no new cells: the all-nine set is already the top
  rung of each ladder, and the design deduplicates. Its 20 all-nine calls are labelled `stage: "ladder"`.

### `pilot01` used an earlier prompt

The pilot was produced by the first version of the code (before the change to "one question per call"):
all ten questions in **one** call, answered as a JSON object, with a persona that named places (Jersey
City, Manhattan, Columbus, Ohio), place names in memories D and E, and a flight "home to Ohio". That version of the code is not in this
repository, but every pilot record stores its full `prompt`, and the pilot manifest stores that persona,
memories and questions. Pilot records therefore have `question_order` and dict-valued `answers` /
`implied_hourly` instead of a single `question` / `answer`.

---

## `<run>/records.jsonl`: one line per model call

Append-only; a line is never rewritten. A cell that failed would be retried and appear again; in the
shipped runs every call succeeded, so every `cell_id` appears once.

| field | meaning |
|---|---|
| `cell_id` | `<memories>__<question>__r<rep>`, e.g. `B-H__priority_pickup__r1`. `none` = no memory |
| `stage` | `baseline` (no memory) · `single` · `pairs` · `ladder` |
| `fact_set` | memory ids shown, sorted. This identifies the condition |
| `fact_order` | the order they were listed in the prompt. Fixed within (condition, rep), shuffled across reps |
| `question` | question id (see the table below) |
| `rep` | sample number within the condition × question |
| `seed` | per-cell seed. Used only by unbatched calls (`batch: null`); batched calls draw from `batch.batch_seed` |
| `engine` | `mlx` for every shipped record (`mock` would mark plumbing tests) |
| `timestamp` | when the call finished (local time, US Eastern) |
| `seconds` | wall time for the call. In batched runs this includes time sharing the GPU with the other 7 calls |
| `batch` | `null` = one call at a time. Otherwise `{mode: "continuous", size, session, batch_seed}`; `session` changes on every restart |
| `status`, `problems`, `warnings` | `ok` if the answer parsed to one number and the thinking block closed. All shipped records are `ok` |
| `prompt` | the complete user message the model saw |
| `raw` | the complete completion, `<think> … </think>` included |
| `thinking` | the text inside `<think>`; the trace we analyse |
| `answer_text` | what followed `</think>` |
| `answer` | the dollar amount parsed from `answer_text` |
| `implied_hourly` | `answer / hours` for that question, rounded to cents. **The outcome variable** |
| `facts_mentioned` | `{memory_id: bool}`: did a keyword for that shown memory appear in the trace? Nearly always true, because traces restate the prompt; we do not treat it as evidence of use |
| `thinking_chars` | length of `thinking` |

## `<run>/manifest.json`: how the run was launched

Written once, on the first launch of a run id. Resumed launches do not rewrite it.

| field | meaning |
|---|---|
| `run_id`, `created` | name and first-launch time |
| `git_commit` | commit of our private development repository at launch. That history is not part of this repository, so the hash will not resolve here |
| `argv`, `args` | command line (scrubbed, see above) and parsed options. `args.batch_size` is 16 for both main runs; after out-of-memory crashes the queue restarted with 8, which `records.batch.size` shows (all but two calls in each run ran at 8) |
| `engine` | model id, `mlx_lm` version, `max_tokens`, temperature, top-p, top-k, `enable_thinking` |
| `n_cells` | cells the design asked for |
| `persona`, `facts`, `questions` | the exact stimuli. `analysis/make_results.py` reads memory rates and questions from here |

### The nine memories (`facts`)

`bound` says what the remembered choice reveals about an hour's value: `lower` = at least this much (we
call these *floors*: paid money to save time), `upper` = at most this much (*ceilings*: spent time to save
money), `point` = exactly (the wage). `mixed_motive` marks choices that plausibly reflect more than time
(a vacation, a date). `keywords` are the regexes behind `facts_mentioned`.

| id | memory (short) | bound | implied $/h |
|---|---|---|---:|
| A | earns $40,000 a year | point | 19.23 |
| B | waited 8 extra minutes on Lyft to save $4 | upper | 30 |
| C | paid $30 for a Disneyland skip-the-line pass, saving ~2 h | lower | 15 |
| D | pays a $9 toll to save 15 minutes on the commute | lower | 36 |
| E | circled 20 minutes for free parking instead of a $15 garage | upper | 45 |
| F | paid $35 for valet on a date, saving ~10 minutes | lower | 210 |
| G | turned down an extra Saturday shift at ~$29/h | lower | 28.85 |
| H | pays a cleaner $60 for a 3-hour job | lower | 20 |
| I | drove 10 extra minutes to save $3 on gas | upper | 18 |

### The ten questions (`questions`)

`direction`: WTP = pay to save time, WTA = accept money to give up time. `hours` converts the dollar
answer to $/hour. `hypothesized_facts` are the memories we expected each question to draw on, written
into the code **before** the runs; they are the "predicted" marks in the results.

| id | asks for | hours | predicted memories |
|---|---|---:|---|
| `general` | what one hour of your time is worth | 1 | A |
| `weekend_gig` | lowest pay for a one-time 4-hour Saturday job | 4 | A, G |
| `research_study` | lowest pay for a 1-hour study | 1 | A, G |
| `nonstop_flight` | most extra for a nonstop that saves 3 hours | 3 | B, D |
| `priority_pickup` | most extra for a rideshare 10 minutes sooner | 1/6 | B, D |
| `grocery_delivery` | most in fees + tip to skip a 1-hour store trip | 1 | E, I, H |
| `furniture_assembly` | most to have a 2-hour bookshelf assembled | 2 | H |
| `theme_park` | most for a pass skipping 2 hours of lines | 2 | C |
| `train_delay` | compensation for a 5-hour delay | 5 | B, D |
| `volunteer_or_donate` | donation equivalent to 2 hours volunteering | 2 | A |

---

## Files generated from the records (by `python -m value_of_time.analyze runs/<run>`)

These are byte-identical to what that command produces from the shipped records today.

### `answers.csv`: one row per call

`cell_id, stage, condition, n_facts, fact_order, rep, question, q_domain, answer, implied_hourly,
thinking_chars, seconds`, plus for each memory X: `shown_X`, `mentioned_X` (keyword hit in trace, blank if
not shown), `consistent_X` (answer respects X's bound, blank if not shown). `matched_fact` is the shown
memory whose rate the answer is closest to **within 10%**. Note that `results/` and our write-ups use a
stricter **3%** match. `pilot01/answers.csv` was written by the earlier analysis code and has fewer columns.
Rows end in CRLF (Python's `csv` default).

### `summary.md`

Median implied $/hour by condition × question, keyword mention rates, and bound-consistency rates.

### `traces.md`

Every thinking trace, grouped by question and then condition, with the answer. The easiest way to read
what the model actually thought.

---

## Logs

- `queue.log`: console output of `scripts/queue_vot.sh` for both main runs (21–22 Oct 2026), including
  every Metal out-of-memory crash and automatic resume. Paths scrubbed as described above.
- `runs_pilot01.log`: console output of the pilot. Its first lines are a harmless `git` error from
  recording the commit hash before the development repository had a first commit.

## `docs/tldr_data.json`

Intermediate numbers written by `scripts/analyze_schema.py` and read by `scripts/build_tldr_figs.py`.
Its `sel` entries are `[selected, shown]` per `question|memory`, among calls with 2+ memories.
