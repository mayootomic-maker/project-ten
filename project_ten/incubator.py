"""Conservative candidate proposal engine. NEVER modifies deployed strategies."""
from .strategies import Strategy
from .research import FAMILY


def propose(research, count=12):
    """Use training-only rankings, mutate known parameters, reject identical configs.

    Proposals are NOT fitted, backtested, qualified, or automatically traded.
    No AI claims; this is an explicit reproducible research search heuristic.
    """
    pool=research['agents']
    ranked=sorted(pool,key=lambda a:(a['train']['net_pct']-research['benchmarks'][a['asset']]['train_pct'],
                                     -a['train']['max_dd_pct']),reverse=True)
    existing={a['id'] for a in pool}
    results=[]
    for agent in ranked:
        n=agent['params']['n'];m=agent['params']['m']
        for delta in (-3,3,-7,7):
            nn=max(3,n+delta)
            if agent['family'] in ('sma','voltrend') and nn>=m:continue
            if agent['family']=='breakout' and nn<=m:continue
            candidate=f"{agent['asset']}-{agent['family']}-{nn}-{m}"
            if candidate in existing:continue
            existing.add(candidate)
            results.append({'id':candidate,'asset':agent['asset'],
                      'family':agent['family'],'parent':agent['id'],
                      'n':nn,'m':m,'status':'UNTESTED / QUARANTINED',
                      'hypothesis':f'Test whether changing lookback {n} to {nn} for {FAMILY[agent["family"]][1].lower()} reduces sensitivity to the chosen parameter.',
                      'warning':'Not tested; cannot enter the shortlist or portfolio without an independently frozen study.'})
            if len(results)>=count:return results
    return results
