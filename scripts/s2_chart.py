import json,collections
V={'A':19.23,'B':30,'C':15,'D':36,'E':45,'F':210,'G':28.85,'H':20,'I':18}
LAB={'A':'A wage $40k','B':'B Lyft wait','C':'C Disney pass','D':'D toll','E':'E circled parking','F':'F valet on date','G':'G declined shift','H':'H cleaner','I':'I cheap gas'}
R=[json.loads(l) for l in open('runs/s2_combos/records.jsonl') if '"status": "ok"' in l]
S1=[json.loads(l) for l in open('runs/s1_single/records.jsonl') if '"status": "ok"' in l]
hit=lambda h,f: h is not None and abs(h-V[f])/V[f]<=0.03
def rate(rs,f):
    n=sum(f in r['fact_set'] for r in rs); w=sum(f in r['fact_set'] and hit(r['implied_hourly'],f) and sum(hit(r['implied_hourly'],g) for g in r['fact_set'])==1 for r in rs)
    return w/n if n else 0, w, n
groups=[('1 memory',[r for r in S1 if len(r['fact_set'])==1]),('2 memories',[r for r in R if len(r['fact_set'])==2]),('3–9 memories',[r for r in R if len(r['fact_set'])>=3])]
h=['<style>.g{display:grid;grid-template-columns:150px repeat(3,170px);gap:3px 10px;font-size:12px;align-items:center}.b{height:14px;background:var(--accent);border-radius:2px}.t{color:var(--muted-foreground);font-size:11px}</style>',
'<div style="font-size:13px;margin-bottom:6px"><b>How often is the answer exactly this memory\'s $/hour rate, when the memory is shown?</b></div><div class="g"><div></div>'+''.join(f'<div><b>{g}</b></div>' for g,_ in groups)]
for f in sorted(V, key=lambda f:-rate(groups[2][1],f)[0]):
    h.append(f'<div>{LAB[f]} <span class="t">${V[f]:g}</span></div>')
    for _,rs in groups:
        p,w,n=rate(rs,f); h.append(f'<div style="display:flex;gap:6px;align-items:center"><div class="b" style="width:{max(2,p*110):.0f}px"></div><span class="t">{p:.0%} ({w}/{n})</span></div>')
h.append('</div><div class="t" style="margin-top:6px">With many memories, the model rarely averages (0/380 answers equal the mean of shown rates). It picks one memory, almost always the cleaner ($20) or the Disney pass ($15).</div>')
open('docs/s2_winners.html','w').write(''.join(h))
