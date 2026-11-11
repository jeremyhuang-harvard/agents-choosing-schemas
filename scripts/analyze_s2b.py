import json,re,collections,statistics as st
V={'A':19.23,'B':30,'C':15,'D':36,'E':45,'F':210,'G':28.85,'H':20,'I':18}
R=[json.loads(l) for l in open('runs/s2_combos/records.jsonl') if '"status": "ok"' in l]
hit=lambda h,f: h is not None and abs(h-V[f])/V[f]<=0.03
multi=[r for r in R if len(r['fact_set'])>=3]
# win rate per memory: matched / times shown (unique matches only)
shown=collections.Counter(); won=collections.Counter()
for r in multi:
    hs=[f for f in r['fact_set'] if hit(r['implied_hourly'],f)]
    for f in r['fact_set']: shown[f]+=1
    if len(hs)==1: won[hs[0]]+=1
print('3+ memories: win rate when shown', {f:f"{won[f]}/{shown[f]}" for f in sorted(V)})
# by question: which memory wins most
byq=collections.defaultdict(collections.Counter)
for r in multi:
    hs=[f for f in r['fact_set'] if hit(r['implied_hourly'],f)]
    byq[r['question']][hs[0] if len(hs)==1 else ('none' if not hs else 'tie')]+=1
for q,c in byq.items(): print(q, c.most_common(4))
# position normalised: expected share if uniform
exp=collections.Counter(); obs=collections.Counter()
for r in multi:
    n=len(r['fact_order']); hs=[f for f in r['fact_order'] if hit(r['implied_hourly'],f)]
    if len(hs)!=1: continue
    i=r['fact_order'].index(hs[0]); obs['first' if i==0 else 'last' if i==n-1 else 'middle']+=1
    exp['first']+=1/n; exp['last']+=1/n; exp['middle']+=(n-2)/n
print('position obs',dict(obs),'expected',{k:round(v) for k,v in exp.items()})
# aggregation language
pats={'average':r'\baverage|\bmean\b','pick most relevant':r'most relevant|most similar|closest|most applicable|directly relevant','range':r'between \$?\d+ and \$?\d+|range of'}
for k,p in pats.items(): print(k, sum(bool(re.search(p,r['thinking'],re.I)) for r in multi),'/',len(multi))
# is answer the arithmetic mean of shown rates?
m=sum(1 for r in multi if r['implied_hourly'] and abs(r['implied_hourly']-st.mean(V[f] for f in r['fact_set']))/st.mean(V[f] for f in r['fact_set'])<=0.03)
print('answer == mean of shown rates', m,'/',len(multi))
# quotes
def q(cid,pat,w=420):
    r=[x for x in R if x['cell_id']==cid][0]; t=re.sub(r'\s+',' ',r['thinking'])
    ms=list(re.finditer(pat,t,re.I)); m=ms[-1] if ms else None
    print(f"\n## {cid} answer={r['answer']} order={r['fact_order']}\n…{t[max(0,m.start()-w):m.end()+w//2] if m else t[-w:]}…")
q('A-B-C-D-E-F-G-H-I__general__r1',r'most relevant|closest|directly|cleaner|\$20')
q('A-B-C-D-E-F-G-H-I__nonstop_flight__r0',r'disney|skip')
q('A-B-C-D-E-F-G-H-I__weekend_gig__r0',r'cleaner|\$20|turned down|saturday')
