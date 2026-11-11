# Findings: s2_combos (memories in combination)

Run `runs/s2_combos`: 1,140 calls, all valid. Pairs (36 × 10 questions × 2 samples), three one-at-a-time
ladders, and all nine memories. Same model and settings as `s1_single`. "Rate" = the memory's implied $/hour;
an answer "matches" a memory if its implied $/h is within 3% of that rate. **2 samples per pair × question;
patterns are provisional.** Scripts: `scripts/analyze_s2.py`, `scripts/analyze_s2b.py`.

## 1. With many memories, the model picks one; it does not average

- 0/380 answers with 3+ memories equal the average of the shown rates.
- 131/380 traces use the word "average" anyway, but the final answer is one memory's rate.
- As memories are added, the share of answers that equal *some* shown rate rises: 1 memory 34%, 2: 48%,
  3: 63%, 4–9: 83–95%. More memories → more often a copied rate, not a blend.
- The general-question answer settles at $20–25 by 3 memories and stays there through all nine.

## 2. Two memories win almost every contest: the cleaner ($20) and the Disney pass ($15)

When shown among 3+ memories, how often the answer equals that memory's rate (and no other):

| Memory | Rate | Wins when shown |
|---|---|---|
| C. Disney pass $30 / 2 h | $15 | 144/340 (42%) |
| H. Cleaner $60 / 3 h | $20 | 104/320 (33%) |
| B. Lyft wait | $30 | 32/200 (16%) |
| F. Valet on a date | $210 | 13/180 (7%) |
| A. Wage $40k | $19.23 | 9/160 (6%) |
| G, I, D, E | | 1–3% each |

- The winners are the two memories stated in whole hours with easy division ($60 ÷ 3, $30 ÷ 2). They are
  also close to the model's no-memory default (~$15–20/h). **This design can't separate "easiest
  arithmetic" from "closest to my prior."** A follow-up should give an easy-arithmetic memory a far-from-prior
  rate (e.g. $120 for 2 hours).
- The wage (A), the obvious economist's answer, almost never wins (6%).
- Order of presentation doesn't matter: the winning memory is first/middle/last in proportion to chance
  (69/190/59 observed vs 61/197/61 expected).
- Some topic matching: priority pickup → Lyft (B) most often; bookshelf → cleaner (H); theme park → Disney (C).
  But the general, flight, and train questions also go to C or H.

All nine memories, general question: *"…the answer is $20, based on the cleaner example. I think the answer
is likely $20… the cleaner example is a direct calculation, so that's a strong indicator."*
Flight: *"…based on the skip-the-line pass, which was $30 for 2 hours. So 3 hours would be $45."*

## 3. A floor memory plus a ceiling memory → the answer usually falls below both

300 answers had one "paid to save time" (floor) memory and one "spent time to save money" (ceiling) memory:

| Outcome | Count |
|---|---|
| Below both rates | 136 (45%) |
| Equals the floor rate | 106 (35%) |
| Equals the ceiling rate | 34 (11%) |
| Between the two | 12 (4%) |
| Above both | 12 (4%) |

This matches s1: a ceiling memory works as a "cost-conscious" trait and pulls everything down, more than
its own number would. The ceiling memory also suppresses copying of the floor rate: toll (D) copied
27/50 alone vs 17/60 with a ceiling memory; valet (F) 18/50 vs 10/60; declined shift (G) 9/50 vs 2/60.

## 4. Logical contradictions are sometimes noticed, never resolved

Lyft (B: worth ≤ $30/h) and toll (D: worth ≥ $36/h) can't both hold under a single fixed hourly value.
5/20 B+D traces flag the conflict, then pick one: *"…$36 per hour… the Lyft example… that's $30. Hmm,
conflicting numbers. But maybe he's more like the toll road."* None says the value depends on the setting
(e.g. commute vs. leisure), which is the standard economic resolution.

## 5. The extreme valet rate fades in company

Valet on a date (F, $210/h) dominated when alone (general question 5/5). In combinations it wins 7% of the
time; 5/340 traces mention the date as a special occasion. It is outvoted, not discounted for its reason.

## 6. Turning down the $29/h shift still doesn't raise the work price

All nine memories, weekend gig: $80 for 4 hours ($20/h, the cleaner rate) in both samples, below the
$29/h already refused. *"…he turned down the $29/hour job. That suggests he's not interested in taking on
extra work… given that he pays the cleaner $60 for 3 hours, which is $20/hour, he might be willing to do
the job for that rate."*

## Caveats

- 2 samples per pair × question; one model, one persona, one wording per memory.
- "Matches a rate" uses ±3%; answers like $20 can match the cleaner by coincidence because $20 is also a
  common round default. Compare with the no-memory baseline before claiming use.
- Floor/ceiling direction is confounded with memory topic (all ceilings are small errands).
