"""Reproducible historical research. Selection is fixed before forward execution."""
from collections import defaultdict
from statistics import mean
import math
from .strategies import candidates, signal, regime
from .engine import backtest, Costs, p_one_sided_hac

FAMILY = {
 'sma': ('Crosswind', 'Trend confirmation', 'Buys when short-term average exceeds long-term average.'),
 'breakout': ('Vanguard', 'Price channels', 'Buys when price rises above a trailing channel midpoint.'),
 'momentum': ('Vector', 'Momentum', 'Buys when current price exceeds an earlier close.'),
 'rsi': ('Undertow', 'Contrarian RSI', 'Buys after a recent decline creates an oversold RSI.'),
 'zscore': ('Echo', 'Mean reversion', 'Buys after a statistically unusual decline from the rolling mean.'),
 'voltrend': ('Sentinel', 'Volatility-filtered trend', 'Follows a rising average only when observed volatility is below its limit.'),
}
NAMES = ('Raven','Lynx','Vesper','Atlas','Comet','Cipher','Sable','Falcon','Vortex','Specter','Kite','Nova',
         'Orion','Mantis','Volt','Helix','Ghost','Monarch','Onyx','Cinder','Halo','Axiom','Kestrel','Mosaic',
         'Obsidian','Ember','Delta','Osprey','Quartz','Nomad','Phantom','Archer','Hydra','Talon','Pulse',
         'Titan','Sphinx','Dart','Silhouette','Horizon','Warden','Strix','Rook','Eclipse','Prism','Drift',
         'Frost','Acumen','Eon','Nexus')

def identity(s, i):
    # Unique short callsigns, even across >50 agents, with a consistent family identity.
    return {'name':f'{FAMILY[s.family][0]} {NAMES[i % len(NAMES)]}' if i < len(NAMES) else f'{FAMILY[s.family][0]} {NAMES[i % len(NAMES)]} {1+i//len(NAMES)}',
            'code':f'AG-{i+1:03d}', 'number':i+1, 'family_label':FAMILY[s.family][1],
            'thesis':FAMILY[s.family][2], 'sigil':i%12, 'stamp': (i*7)%9,
            'parameters': {'lookback':s.n, 'threshold_or_long_window':s.m}}

def benchmark(bars,start,end,cfg):
    from .engine import execute, liquidatable
    import random
    if start>=end: return {'net_pct':0, 'curve':[100.0]}
    cash, qty = 100.,0.
    cash,qty,rec=execute(side='buy',mid=bars[start]['o'],cash=cash,qty=qty,notional=95.,cfg=cfg,rng=random.Random(0))
    curve=[100.0]
    for b in bars[start:end]:curve.append(liquidatable(cash,qty,b['c'],cfg))
    return {'net_pct':(curve[-1]/100-1)*100,'curve':curve,'filled':rec['status']=='filled'}

def _thin(result):
    return {k:v for k,v in result.items() if k not in ('returns','curve','fills')}

def holm_pvalues(pvalues):
    ordered=sorted(pvalues,key=lambda item:item[1])
    prev=0.; out={}
    m=len(ordered)
    for i,(key,p) in enumerate(ordered):
        prev=max(prev,min(1.,(m-i)*p))
        out[key]=prev
    return out

def evaluate(market,count=100,cfg=None):
    """Train and select on earliest 72%, audit on remaining 28% once.

    Does not claim that the held-out period proves a strategy will be profitable.
    """
    cfg=cfg or Costs()
    pool=candidates(count)
    by_asset=defaultdict(list)
    for i,s in enumerate(pool):by_asset[s.asset].append((i,s))
    results=[]; benchmarks={}; pvalues=[]
    for asset, members in by_asset.items():
        bars=market[asset]
        boundary=max(240,int(len(bars)*.72))
        if len(bars)-boundary<85:
            raise ValueError(f'{asset}: need at least 85 held-out bars')
        # 160 days are warmup; the strategy never sees future days.
        start=max(160,int(len(bars)*.25))
        bench_train=benchmark(bars,start,boundary,cfg)
        bench_test=benchmark(bars,boundary,len(bars),cfg)
        benchmarks[asset]={'train_pct':round(bench_train['net_pct'],3),
                           'holdout_pct':round(bench_test['net_pct'],3),
                           'regime':regime([b['c'] for b in bars]),
                           'first':bars[0]['t'],'last':bars[-1]['t'],
                           'count':len(bars)}
        for i,s in members:
            train=backtest(s,bars,start,boundary,cfg)
            test=backtest(s,bars,boundary,len(bars),cfg)
            stress=backtest(s,bars,boundary,len(bars),cfg.stressed(),seed=19)
            # Candidate is screened on training performance only.
            # Three distinct chronological training subwindows, each with fresh virtual capital.
            # Candidate must hold up in at least two, instead of one lucky interval.
            fold_start=[start+int((boundary-start)*k/3) for k in range(3)]
            fold_end=[start+int((boundary-start)*(k+1)/3) for k in range(3)]
            folds=[]
            for lo,hi in zip(fold_start,fold_end):
                fr=backtest(s,bars,lo,hi,cfg)
                fb=benchmark(bars,lo,hi,cfg)
                folds.append({'from':bars[lo]['t'],'to':bars[hi-1]['t'],
                              'net_pct':round(fr['net_pct'],3),
                              'benchmark_pct':round(fb['net_pct'],3),
                              'beats_benchmark':fr['net_pct']>fb['net_pct']})
            fold_wins=sum(f['beats_benchmark'] for f in folds)
            eligible_train=(fold_wins>=2 and train['net_pct']>bench_train['net_pct'] and train['net_pct']>0
                            and train['trades']>=2 and train['max_dd_pct']<25
                            and not train['stopped'])
            # Forward holdout can veto the candidate but cannot be used for parameter tuning.
            qualified=(eligible_train and test['net_pct']>0 and
                       test['net_pct']>bench_test['net_pct'] and stress['net_pct']>0 and
                       test['max_dd_pct']<25 and not test['stopped'])
            p=p_one_sided_hac([a-b for a,b in zip(train['returns'],
                   [bench_train['curve'][j+1]/bench_train['curve'][j]-1 for j in range(len(bench_train['curve'])-1)])])
            pvalues.append((s.id,p))
            item={'id':s.id,'asset':asset,'family':s.family,'sig':identity(s,i),
                  'params':{'n':s.n,'m':s.m},'train':_thin(train),'holdout':_thin(test),
                  'stress':_thin(stress), 'eligible_train':eligible_train,'qualified':qualified,
                  'fold_wins':fold_wins,'training_slices':folds,
                  'p_raw':p,'holdout_curve':[round(x,4) for x in test['curve']],
                  'recent_signal':signal(s,[b['c'] for b in bars]),
                  'rejection_reason':('passed historical gates' if qualified else
                     'insufficient training evidence' if not eligible_train else
                     'failed untouched holdout or stress test'),
                  'last_eval':bars[-1]['t']}
            results.append(item)
    corrected=holm_pvalues(pvalues)
    for item in results:
        item['p_holm_train']=round(corrected[item['id']],6)
        # Conservative explanatory label, never turn a p-value into "probability of success".
        item['evidence']='insufficient' if corrected[item['id']]>=.05 else 'screened'
    # Diversify: one candidate per asset, up to three, based on qualifying test robustness.
    best=[]
    for asset in sorted(by_asset):
        eligible=[x for x in results if x['asset']==asset and x['qualified']]
        eligible.sort(key=lambda x:(x['train']['net_pct']-benchmarks[asset]['train_pct'],
                -x['train']['max_dd_pct']),reverse=True)
        if eligible:best.append(eligible[0]['id'])
    return {'agents':sorted(results,key=lambda x:x['sig']['number']),'benchmarks':benchmarks,
            'shortlist':best,'candidate_count':len(pool),
            'qualified_count':sum(a['qualified'] for a in results),
            'selection_note':'Research snapshot: train screen followed by one holdout and 2x-cost stress veto. Forward performance must be measured separately.',
            'costs':cfg.__dict__}
