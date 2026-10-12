"""Prospective shadow opportunity calibration. Never counted as portfolio profit."""
import math
from statistics import mean, stdev
from .paired_signals import decision

def new_learning():
    return {'pending':[],'completed':[],'last_origins':{},'method':'Fixed 4-candle prospective cost-adjusted shadow outcomes; not actual trades or strategy P&L'}

def usable_quote(m,now):
    return bool(m and 0<=now-m['quote_at']<=120 and 0<m['bid']<=m['ask'] and math.isfinite(m['bid']+m['ask']))

def learn(account,snapshot,now,fee=.008,slippage=.0005):
    memory=account.setdefault('learning',new_learning())
    pending=[]
    for origin in memory['pending']:
        m=snapshot['spot'].get(origin['instrument'])
        if not usable_quote(m,now) or now<origin['due_at']:
            pending.append(origin);continue
        # No backdated exit. A late job grades the actual later quote and records delay.
        exit_value=m['bid']*(1-slippage)*(1-fee)
        result={**origin,'scored_at':now,'delay_seconds':now-origin['due_at'],
            'usable_for_calibration':now-origin['due_at']<=origin.get('interval_seconds',3600),
            'net_return_pct':100*(exit_value/origin['entry_unit_cost']-1),
            'gross_mid_return_pct':100*((m['bid']+m['ask'])/2/origin['entry_mid']-1)}
        memory['completed'].append(result)
    memory['pending']=pending
    memory['completed']=memory['completed'][-200:]
    chosen=account['research'].get('selected') if account.get('research') else None
    if account['desk']=='futures' or not chosen:return
    key=chosen['instrument'];m=snapshot['spot'].get(key)
    if not usable_quote(m,now):return
    bar=m['bars'][-1]['t'];origin_key=f'{key}:{account["policy"]["fingerprint"]}'
    if memory['last_origins'].get(origin_key)==bar:return
    target,_=decision(account['family'],m['bars'],policy=account['policy'])
    if not target:return
    if any(p['instrument']==key and p['policy']==account['policy']['fingerprint'] for p in memory['pending']):return
    memory['last_origins'][origin_key]=bar
    memory['pending'].append({'instrument':key,'asset':m['asset'],'origin_at':now,'bar_at_origin':bar,
        'due_at':now+4*m['interval']*60,'entry_mid':(m['bid']+m['ask'])/2,
        'interval_seconds':m['interval']*60,
        'entry_unit_cost':m['ask']*(1+slippage)*(1+fee),
        'policy':account['policy']['fingerprint'],
        'label':'SHADOW OPPORTUNITY — no money allocated, no fill or profit claimed'})
    memory['pending']=memory['pending'][-100:]

def summary(account,instrument=None):
    memory=account.get('learning',new_learning())
    rows=[r for r in memory['completed'] if r.get('usable_for_calibration',False) and r['policy']==account['policy']['fingerprint'] and (instrument is None or r['instrument']==instrument)]
    values=[r['net_return_pct'] for r in rows];n=len(values)
    avg=mean(values) if values else None
    # Exploratory t-style lower bound; overlapping samples are NOT independent.
    lower=avg-2*stdev(values)/math.sqrt(n) if n>1 else None
    return {'samples':n,'pending':len(memory['pending']),'late_outcomes':sum(not r.get('usable_for_calibration',False) for r in memory['completed']),'mean_shadow_net_pct':avg,
        'profitable_fraction':sum(v>0 for v in values)/n if n else None,
        'exploratory_lower_bound_pct':lower,'ready_to_influence_rank':n>=20,
        'status':'INSUFFICIENT FORWARD EVIDENCE' if n<20 else 'EXPLORATORY CALIBRATION — overlapping observations, not proof',
        'method':memory['method']}

def rank_adjustment(account,instrument):
    s=summary(account,instrument)
    # Only matured, instrument- and policy-specific observations can influence rank.
    if not s['ready_to_influence_rank']:return 0.
    return max(-2.,min(0.,s['exploratory_lower_bound_pct'] or 0.))
