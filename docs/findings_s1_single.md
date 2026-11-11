# Findings: s1_single (no memory vs. one memory)

Run `runs/s1_single`: 500 calls, 0 failures. One fixed persona, 0 or 1 memory, 10 survey questions, each
asked in its own fresh call. `mlx-community/Qwen3-8B-4bit` with thinking on; temp 0.6, top-p 0.95, top-k 20;
continuous batching of 8 independent calls. 5 samples per memory × question. **These are draws from one
model configuration, not independent people. n = 5 per cell, so treat every pattern as provisional.**

Implied $/hour = answer ÷ hours at stake in the question.

## 1. When a memory implies a minimum, the model turns it into a fixed hourly rate and multiplies

A "floor" memory shows Sam paid money to save time, so an hour is worth *at least* the implied amount.
The model computes that number and then applies it to unrelated questions. Share of all 50 answers that
equal the memory's rate (within 3%):

| Memory (floor) | Rate | Answers equal to rate |
|---|---|---|
| H. paid cleaner $60 for 3 h | $20 | 39/50 |
| C. Disneyland $30 pass for 2 h | $15 | 37/50 |
| D. $9 toll saves 15 min | $36 | 27/50 |
| F. $35 valet on a date, saves 10 min | $210 | 18/50 |

- **H:** every question gives exactly $20/h: flight $60, theme park $40, train delay $100, donation $40.
  Trace: *"$60 divided by 3 hours is $20 per hour. If the nonstop flight saves 3 hours… 3 hours times…"*
- **F (valet on a date):** general question $210 in 5/5 samples, train delay $1,050 in 5/5. The model
  notices the number is extreme but goes with the arithmetic anyway, and doesn't discount the date context:
  *"…$210 per hour. If he values his time that high, 5 hours would be 5×210 = $1050. But that seems high…"*
  The final answer is still 1050.

## 2. When a memory implies a maximum, the model reads it as a personality trait

A "ceiling" memory shows Sam spent time to save money, so an hour is worth *at most* the implied amount.
The model rarely computes the rate. It infers that Sam is "cost-conscious" and lowers every answer.

| Memory (ceiling) | Rate | Answers equal to rate | Trace calls Sam cost-conscious/frugal/budget |
|---|---|---|---|
| B. Lyft wait 8 min to save $4 | $30 | 6/50 | 48/50 |
| E. circled 20 min to skip $15 garage | $45 | 2/50 | 46/50 |
| I. drove 10 min to save $3 on gas | $18 | 9/50 | 49/50 |
| (no memory) | – | – | 14/50 |

- **B, nonstop flight:** $150–200 with no memory vs **$10–50 with the Lyft memory** ($3–17/h).
  *"The key is that he's shown to be cost-conscious, so he's not going to pay a lot… the answer is $15."*
- **E, general question:** in 2/5 samples the model reads the $45 *maximum* as a *minimum*: *"the parking
  example suggests a higher value… I'll go with $45."*

Floor memories are used as an exchange rate; ceiling memories are used to infer a type. Both are bounds on
the same quantity, so a consistent valuer would use them symmetrically.

## 3. Turning down paid work lowers what the model will accept to work

G: Sam turned down an extra Saturday shift at $29/h. Read correctly, his free Saturday is worth more than
$29/h. Weekend-gig answers: $10, $20, $30, $50, $116 for 4 hours. Only 1/5 is ≥ $29/h.
*"Since he turned down the higher rate, maybe he would accept something lower, like $50."*
The one correct sample: *"he values his time higher than that… 4 × $29 = $116."*

## 4. Being paid to give up time is valued below paying to save time

Humans usually demand more to give time up than they'd pay to get it back. Here, with no memory, the
weekend gig implies ~$12/h and the research study $15/h, while the general question gets $20/h and the
nonstop flight ~$50/h. The wage memory (A, $19.23/h) moves the general answer to $19–20 but not the gig
answer (still $50 for 4 h, $12.50/h), even though the trace computes the wage: *"40k divided by 2080 hours
… about $19.23 per hour… since it's a one-time job, he might be willing to take less."*

## 5. Memory mentions don't show memory use

Keyword matching finds the shown memory in ~100% of traces, because the trace restates the prompt. Mentions
are not evidence of use; the answer values (above) are the better measure.

## Measurement artifact to fix

12/500 traces refer to an "example answer" or "previous interaction" that doesn't exist (e.g. *"the example
answer in the previous interaction was $100"*). The prompt contains no example. This is a confabulated
anchor and is worth flagging when quoting those traces.

## Caveats

- One model (Qwen3-8B, 4-bit), one persona, one wording per memory; n = 5 per cell.
- Floor vs. ceiling is confounded with memory content: every ceiling memory is a small-dollar errand.
  A clean test would flip the direction while holding the domain fixed (e.g. paid the toll vs. skipped it).
- No human data yet.
