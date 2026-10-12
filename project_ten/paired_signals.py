"""Explicit entry/exit hypotheses. No LLM, learning, or proven edge is claimed."""
from statistics import mean, pstdev
import math
from .paired_policies import entry_guard

FAMILIES = {
    'sma_trend': 'Moving-average trend',
    'ema_trend': 'Exponential-average trend',
    'channel': 'Channel breakout',
    'rsi': 'RSI reversal',
    'bands': 'Volatility-band reversion',
    'momentum': 'Relative momentum',
    'volume_breakout': 'Volume-confirmed breakout',
    'pullback': 'Trend pullback',
    'compression': 'Compression breakout',
    'range': 'Range support bounce',
}

def ema(values, n):
    x = values[0]
    for v in values[1:]: x += 2 / (n + 1) * (v - x)
    return x

def features(bars):
    c = [b['c'] for b in bars]
    ret = [c[i]/c[i-1]-1 for i in range(len(c)-23, len(c))]
    diffs = [c[i]-c[i-1] for i in range(len(c)-14, len(c))]
    gains = mean([max(0,d) for d in diffs]); losses = mean([max(0,-d) for d in diffs])
    rsi = 50 if gains == losses == 0 else 100 if losses == 0 else 100-100/(1+gains/losses)
    tr = [max(bars[i]['h']-bars[i]['l'], abs(bars[i]['h']-c[i-1]), abs(bars[i]['l']-c[i-1])) for i in range(len(c)-14,len(c))]
    return {'close':c[-1], 'sma12':mean(c[-12:]), 'sma48':mean(c[-48:]),
            'ema12':ema(c[-80:],12), 'ema48':ema(c[-120:],48),
            'rsi':rsi, 'atr_pct':mean(tr)/c[-1], 'volatility':pstdev(ret),
            'momentum':c[-1]/c[-25]-1, 'volume_ratio':bars[-1]['v']/max(1e-12,mean([b['v'] for b in bars[-25:-1]])),
            'z':(c[-1]-mean(c[-24:]))/max(1e-12,pstdev(c[-24:])),
            'high':max(c[-25:-1]), 'low':min(c[-25:-1]),
            'previous':c[-2], 'short_range':(max(c[-7:-1])-min(c[-7:-1]))/c[-1],
            'long_range':(max(c[-49:-1])-min(c[-49:-1]))/c[-1]}

_SERIES_CACHE={}

def feature_series(bars):
    # One shared historical feature calculation per instrument, not per worker.
    key=tuple((b['t'],b['h'],b['l'],b['c'],b['v']) for b in bars)
    if key not in _SERIES_CACHE:
        _SERIES_CACHE[key]=[features(bars[:i+1]) if i>=129 else None for i in range(len(bars))]
    return _SERIES_CACHE[key]

def decision(family, bars, holding=False, _features=None, policy=None):
    if len(bars)<130:return False, 'Insufficient completed candles: need 130.'
    f=_features if _features is not None else features(bars); cur=f['close']; up=f['sma12']>f['sma48']
    if family=='sma_trend': enter=up; leave=not up
    elif family=='ema_trend': enter=f['ema12']>f['ema48']; leave=not enter
    elif family=='channel': enter=cur>f['high']; leave=cur<min(b['c'] for b in bars[-13:-1])
    elif family=='rsi': enter=f['rsi']<30 and cur>f['previous']; leave=f['rsi']>55
    elif family=='bands': enter=f['z']<-1.5 and cur>f['previous']; leave=f['z']>=0
    elif family=='momentum': enter=f['momentum']>.025 and up; leave=f['momentum']<0 or not up
    elif family=='volume_breakout': enter=cur>f['high'] and f['volume_ratio']>1.5; leave=cur<f['sma12']
    elif family=='pullback': enter=up and cur<f['sma12'] and cur>f['sma48'] and cur>f['previous']; leave=not up
    elif family=='compression':
        enter=f['short_range']<f['long_range']*.3 and cur>max(b['c'] for b in bars[-7:-1]) and up
        leave=cur<f['sma12']
    elif family=='range':
        width=f['high']-f['low']; enter=not up and width>0 and cur<f['low']+width*.2 and cur>f['previous']
        leave=width>0 and cur>f['low']+width*.7
    else:raise ValueError(family)
    guard=entry_guard(policy,f,bars)
    target=not leave if holding else enter and guard
    context=f" Policy guard {policy['entry_guard']}: {'passed' if guard else 'failed'}." if policy else ''
    return target, f"{FAMILIES[family]}: close {cur:.6g}; fast/slow {f['sma12']:.6g}/{f['sma48']:.6g}; RSI {f['rsi']:.1f}; momentum {f['momentum']*100:+.2f}%; volume ratio {f['volume_ratio']:.2f}.{context} {'Keep position' if holding and target else 'Exit' if holding else 'Entry condition met' if target else 'No entry'}."

def screen(family, bars, start, end, fee=.008, friction=.001, policy=None, execution=None):
    """Past signals execute at the NEXT completed bar open; no same-close fills."""
    series=feature_series(bars)
    execution=execution or {};capital=execution.get('capital',100.)
    cash=capital;qty=0.;fees=0.;trades=0;entries=0;peak=capital;drawdown=0.;entry_i=None;stop=None;target_price=None;frozen=False
    step=execution.get('qty_step',1e-8);min_qty=execution.get('min_qty',0);minimum=max(10,execution.get('min_cost',10))
    for i in range(start,end):
        target,_=decision(family,bars[:i],bool(qty),_features=series[i-1],policy=policy)
        if qty and policy and i-entry_i>=policy['max_holding_bars']:target=False
        b=bars[i]
        # Observe current opening quote proxy, never fabricate an intrabar stop fill.
        if qty and (b['o']<=stop or b['o']>=target_price or frozen):target=False
        if target and not qty and not frozen:
            price=b['o']*(1+friction)
            atr=series[i-1]['atr_pct'];stop_pct=min(.15,max(.03,2*atr))
            cost_buffer=2*fee+2*friction;target_pct=max(2*stop_pct,4*atr)
            cap=.1 if execution.get('sector')=='memes' else .25
            budget=min(cash*.95,cash*cap,cash*.01/(stop_pct+cost_buffer))
            amount=math.floor(budget/(price*(1+fee))/step)*step;cost=amount*price
            if target_pct>=2*cost_buffer and amount>=min_qty and cost>=minimum:
                qty=amount;cash-=cost*(1+fee);fees+=cost*fee;trades+=1;entries+=1;entry_i=i
                stop=price*(1-stop_pct);target_price=price*(1+target_pct)
        elif not target and qty:
            gross=qty*b['o']*(1-friction)
            if qty>=min_qty and gross>=minimum:
                cash+=gross*(1-fee);fees+=gross*fee;qty=0.;trades+=1
        equity=cash+qty*b['c']
        peak=max(peak,equity);drawdown=max(drawdown,1-equity/peak)
        if equity<peak*.9:frozen=True
    equity=cash+qty*bars[end-1]['c']*(1-friction)*(1-fee)
    return {'net_pct':round((equity/capital-1)*100,4), 'entries':entries,'orders':trades,'drawdown_pct':round(100*drawdown,4),'fees_usd':round(fees,5)}

def evaluate(family, bars, policy=None, execution=None):
    if len(bars)<400:raise ValueError('Need 400 complete candles for chronological screening')
    boundary=int(len(bars)*.7)
    train=screen(family,bars,130,boundary,policy=policy,execution=execution)
    holdout=screen(family,bars,boundary,len(bars),policy=policy,execution=execution)
    stress=screen(family,bars,boundary,len(bars),fee=.016,friction=.002,policy=policy,execution=execution)
    bounds=[boundary+int((len(bars)-boundary)*i/3) for i in range(4)]
    folds=[screen(family,bars,lo,hi,policy=policy,execution=execution) for lo,hi in zip(bounds,bounds[1:])]
    positive_folds=sum(f['net_pct']>0 for f in folds)
    qualified=train['net_pct']>0 and train['entries']>=3 and holdout['net_pct']>0 and holdout['entries']>=5 and stress['net_pct']>0 and holdout['drawdown_pct']<10 and positive_folds>=2
    return {'train':train,'holdout':holdout,'stress':stress,'qualified':qualified,
            'validation_version':3,'validation_folds':folds,'positive_folds':positive_folds,
            'evidence_requirement':'At least 3 training and 5 holdout entries; 2/3 later subwindows positive; positive doubled-cost result. Still exploratory, not statistical proof.',
            'from':bars[0]['t'],'to':bars[-1]['t'],
            'note':'Repeated rolling exploratory screening with risk sizing, exposure caps, venue floors and open-observed stop/target exits. Intrabar touches and historical venue/spread changes are not reconstructed. Later folds, sample size and doubled costs may veto the candidate.'}
