"""Auditable decision diversity. Policies are rules, not personalities or LLM minds."""
VERSION=1

OBJECTIVES=('net_return','drawdown','capital_efficiency','low_turnover','liquidity',
            'trend_persistence','recovery','volatility_control','compression','range_discipline')
GUARDS={
 'majors':('trend_strength','quiet','volume','recovery','quiet_recovery','momentum_volume','breakout_quality','balanced_rsi','compression_quality','bounded_range'),
 'swing':('persistent_trend','trend_strength','persistent_breakout','deep_recovery','deep_reversion','persistent_momentum','volume_trend','slow_pullback','tight_compression','quiet_range'),
 'alts':('volume_trend','momentum_volume','breakout_quality','quiet_recovery','deep_reversion','trend_strength','persistent_breakout','balanced_rsi','compression_quality','quiet_range'),
 'memes':('quiet_volume','persistent_trend','volume_breakout_strict','deep_recovery','quiet_recovery','persistent_momentum','volume_breakout_strict','slow_pullback','tight_compression','bounded_range'),
}
DESK_WEIGHTS={'majors':1.,'swing':2.,'alts':1.5,'memes':3.,'futures':0.}
FUTURES_LENSES=('liquidity','positive_funding','negative_funding','positive_basis','negative_basis',
                'open_interest','upward_momentum','downward_momentum','tight_spread','volume_to_interest')

def policy_for(desk,index,family):
    # Each desk changes the evidence objective as well as its entry context.
    offset={'majors':0,'swing':3,'alts':6,'memes':8,'futures':0}[desk]
    objective=FUTURES_LENSES[index] if desk=='futures' else OBJECTIVES[(index+offset)%10]
    guard='research_only' if desk=='futures' else GUARDS[desk][index]
    horizon={'majors':48,'swing':72,'alts':36,'memes':24,'futures':0}[desk]+index*3
    return {'version':VERSION,'fingerprint':f'{desk}:{family}:{objective}:{guard}:{horizon}',
        'objective':objective,'entry_guard':guard,'max_holding_bars':horizon,
        'drawdown_weight':DESK_WEIGHTS[desk], 'family':family,
        'description':f'Prioritize {objective.replace("_"," ")}; require {guard.replace("_"," ")}; review time exit after {horizon} bars.'}

def entry_guard(policy,f,bars):
    if not policy:return True
    g=policy['entry_guard'];c=[b['c'] for b in bars];rising=c[-1]>c[-2]>c[-3]
    strength=f['sma12']/f['sma48']-1
    checks={
      'trend_strength':strength>.005,
      'quiet':f['volatility']<.02,
      'volume':f['volume_ratio']>=1.2,
      'recovery':rising and f['momentum']<0,
      'quiet_recovery':rising and f['volatility']<.025,
      'momentum_volume':f['momentum']>.025 and f['volume_ratio']>=1.,
      'breakout_quality':f['volume_ratio']>=1.2 and f['volatility']<.035,
      'balanced_rsi':35<=f['rsi']<=60,
      'compression_quality':f['volatility']<.02 and f['volume_ratio']>=1.,
      'bounded_range':abs(f['momentum'])<.04,
      'persistent_trend':rising and strength>.003,
      'persistent_breakout':rising and f['volume_ratio']>=1.1,
      'deep_recovery':rising and f['rsi']<25,
      'deep_reversion':f['z']<-2 and f['volatility']<.03,
      'persistent_momentum':rising and f['momentum']>.04,
      'volume_trend':strength>.005 and f['volume_ratio']>=1.,
      'slow_pullback':30<=f['rsi']<=50 and strength>.01,
      'tight_compression':f['short_range']<f['long_range']*.2 and f['volume_ratio']>=1.2,
      'quiet_range':abs(f['momentum'])<.025 and f['volatility']<.02,
      'quiet_volume':f['volatility']<.025 and f['volume_ratio']>=1.5,
      'volume_breakout_strict':rising and f['volume_ratio']>=2 and strength>.005,
      'research_only':False,
    }
    return checks[g]

def rank(row,policy):
    """Rank training evidence; holdout returns never enter this score."""
    t=row['train'];net=t['net_pct'];dd=t.get('drawdown_pct',0);orders=t.get('orders',0);fees=t.get('fees_usd',0)
    obj=policy['objective'];w=policy['drawdown_weight']
    base=net-w*dd
    if obj=='net_return':return net
    if obj in ('drawdown','volatility_control'):return net-3*w*dd
    if obj=='capital_efficiency':return net/max(1.,dd)
    if obj=='low_turnover':return base-.1*orders
    if obj=='liquidity':return base+min(2.,row['volume_usd_24h']/10_000_000)-row['spread_pct']*5
    if obj=='trend_persistence':return base-.05*orders
    if obj=='recovery':return net-2*dd-.1*fees
    if obj=='compression':return base-.1*fees
    if obj=='range_discipline':return base-.15*orders-.2*fees
    raise ValueError(obj)

def futures_score(row,lens):
    funding=float(row.get('relative_funding_rate_provider_units') or 0)
    basis=float(row.get('basis_pct') or 0);volume=float(row.get('volume_usd_24h') or 0)
    oi=float(row.get('open_interest') or 0);change=float(row.get('change_24h_pct') or 0)
    spread=(row['ask']-row['bid'])/((row['ask']+row['bid'])/2)
    return {'liquidity':volume,'positive_funding':funding,'negative_funding':-funding,
        'positive_basis':basis,'negative_basis':-basis,'open_interest':oi,
        'upward_momentum':change,'downward_momentum':-change,'tight_spread':-spread,
        'volume_to_interest':volume/max(1.,oi)}[lens]
