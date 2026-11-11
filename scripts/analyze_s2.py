"""Exploratory analysis of s2_combos (pairs, ladders, full) against s1_single baselines."""
import collections
import json
import re
import statistics as st

V = {'A': 19.23, 'B': 30, 'C': 15, 'D': 36, 'E': 45, 'F': 210, 'G': 28.85, 'H': 20, 'I': 18}
FLOOR = {'C', 'D', 'F', 'G', 'H'}
CEIL = {'B', 'E', 'I'}


def load(p):
    out = {}
    for l in open(p):
        r = json.loads(l)
        if r['status'] == 'ok':
            out[r['cell_id']] = r
    return list(out.values())


R = load('runs/s2_combos/records.jsonl')
S1 = load('runs/s1_single/records.jsonl')
print('s2 calls', len(R))


def hit(h, f):
    return h is not None and abs(h - V[f]) / V[f] <= 0.03


def med(rs, q=None):
    v = [r['implied_hourly'] for r in rs if (q is None or r['question'] == q) and r['implied_hourly'] is not None]
    return st.median(v) if v else None


pairs = [r for r in R if len(r['fact_set']) == 2]
print('\n== pairs: does the answer equal one shown memory rate? ==')
c = collections.Counter()
for r in pairs:
    hs = [f for f in r['fact_set'] if hit(r['implied_hourly'], f)]
    c['one' if len(hs) == 1 else ('none' if not hs else 'both')] += 1
print(c, len(pairs))

print('\n== floor x ceiling pairs: whose rate wins (all questions) ==')
win = collections.Counter()
for r in pairs:
    fs = set(r['fact_set'])
    if len(fs & FLOOR) == 1 and len(fs & CEIL) == 1:
        h = r['implied_hourly']
        fl, ce = (fs & FLOOR).pop(), (fs & CEIL).pop()
        if h is None:
            continue
        lo, hi = sorted([V[fl], V[ce]])
        if hit(h, fl):
            win['floor rate'] += 1
        elif hit(h, ce):
            win['ceiling rate'] += 1
        elif lo * 0.97 <= h <= hi * 1.03:
            win['between'] += 1
        elif h < lo:
            win['below both'] += 1
        else:
            win['above both'] += 1
print(win, sum(win.values()))

print('\n== floor rate-copy share: alone (s1) vs with a ceiling memory (s2) ==')
for fl in ['H', 'C', 'D', 'F', 'G']:
    alone = [r for r in S1 if r['fact_set'] == [fl]]
    withc = [r for r in pairs if fl in r['fact_set'] and set(r['fact_set']) & CEIL]
    withf = [r for r in pairs if fl in r['fact_set'] and set(r['fact_set']) & (FLOOR - {fl})]
    f = lambda rs: f"{sum(hit(r['implied_hourly'], fl) for r in rs)}/{len(rs)}"
    print(fl, 'alone', f(alone), '| +ceiling', f(withc), '| +other floor', f(withf))

print('\n== general question medians, selected pairs ==')
for p in [('B', 'D'), ('B', 'H'), ('D', 'I'), ('E', 'H'), ('F', 'I'), ('B', 'F'), ('A', 'D'), ('A', 'F'), ('A', 'B'), ('D', 'H'), ('C', 'F')]:
    rs = [r for r in pairs if tuple(r['fact_set']) == p]
    g = sorted(r['implied_hourly'] for r in rs if r['question'] == 'general')
    fl = sorted(r['implied_hourly'] for r in rs if r['question'] == 'nonstop_flight')
    print(p, 'general', g, 'flight $/h', fl, '| rates', V[p[0]], V[p[1]])

print('\n== B+D (ceiling $30 vs floor $36: logically inconsistent) ==')
bd = [r for r in pairs if set(r['fact_set']) == {'B', 'D'}]
pat = r'contradict|inconsisten|conflict|doesn.t add up|paradox|mixed signal'
print('traces with contradiction language', sum(bool(re.search(pat, r['thinking'], re.I)) for r in bd), '/', len(bd))
allc = sum(bool(re.search(pat, r['thinking'], re.I)) for r in pairs)
print('all pairs with contradiction language', allc, '/', len(pairs))
for r in bd:
    if re.search(pat, r['thinking'], re.I):
        t = re.sub(r'\s+', ' ', r['thinking'])
        m = re.search(pat, t, re.I)
        print(' ', r['cell_id'], r['answer'], '…' + t[max(0, m.start() - 250):m.end() + 250] + '…')
        break

print('\n== by number of memories (general question; all questions) ==')
for n in range(1, 10):
    rs = [r for r in (S1 if n == 1 else R) if len(r['fact_set']) == n]
    g = [r['implied_hourly'] for r in rs if r['question'] == 'general']
    rate_copy = sum(any(hit(r['implied_hourly'], f) for f in r['fact_set']) for r in rs)
    print(n, 'n', len(rs), 'general med', st.median(g) if g else None, 'range', (min(g), max(g)) if g else None,
          '| answer = some shown rate', f"{rate_copy}/{len(rs)}",
          '| think chars', st.median(r['thinking_chars'] for r in rs))

print('\n== all nine memories ==')
for r in sorted([r for r in R if len(r['fact_set']) == 9], key=lambda r: (r['question'], r['rep'])):
    hs = [f for f in r['fact_set'] if hit(r['implied_hourly'], f)]
    print(f"{r['question']:20s} r{r['rep']} ans={r['answer']:<7} $/h={r['implied_hourly']:<7} matches={hs}")

print('\n== ladders: general answer as memories are added ==')
from value_of_time.design import ladder_orders
for k, order in enumerate(ladder_orders(3)):
    seq = []
    for j in range(1, 10):
        fs = sorted(order[:j])
        src = S1 if j == 1 else R
        v = [r['implied_hourly'] for r in src if r['fact_set'] == fs and r['question'] == 'general']
        seq.append(f"+{order[j-1]}:{'/'.join(f'{x:g}' for x in sorted(v))}")
    print(f'ladder {k}:', '  '.join(seq))

print('\n== recency: in ladders, does the answer match the most recently added memory more than earlier ones? ==')
# position in displayed order (fact_order) of the matched memory
pos = collections.Counter()
for r in R:
    if len(r['fact_order']) >= 3:
        hs = [f for f in r['fact_order'] if hit(r['implied_hourly'], f)]
        if len(hs) == 1:
            i = r['fact_order'].index(hs[0])
            pos['first' if i == 0 else ('last' if i == len(r['fact_order']) - 1 else 'middle')] += 1
print(pos)

print('\n== F (valet on a date) in combos: still $210? ==')
fr = [r for r in R if 'F' in r['fact_set']]
print('answers equal $210/h:', sum(hit(r['implied_hourly'], 'F') for r in fr), '/', len(fr))
k = sum(bool(re.search(r'\bdate\b.{0,80}(special|impress|occasion|romantic)|(special|occasion|romantic).{0,80}\bdate\b', r['thinking'], re.I)) for r in fr)
print('traces discounting/special-casing the date:', k, '/', len(fr))

print('\n== which memory gets cited first in traces, multi-memory ==')
kw = {'A': r'40,?000|salary|office coordinator', 'B': r'lyft|wait\s*(&|and)\s*save', 'C': r'disney|skip-the-line pass',
      'D': r'toll', 'E': r'circl|street parking|garage', 'F': r'valet', 'G': r'saturday shift|time-and-a-half|turned (it )?down',
      'H': r'cleaner', 'I': r'gas station|fill-?up'}
first = collections.Counter()
for r in R:
    if len(r['fact_set']) >= 3:
        t = r['thinking'].lower()
        # skip the restated-prompt opening by looking after the question restatement where possible
        idx = {f: (m.start() if (m := re.search(kw[f], t)) else 10**9) for f in r['fact_set']}
        first[min(idx, key=idx.get)] += 1
print(first)
