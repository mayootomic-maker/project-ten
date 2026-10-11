"""100 transparent, deterministic, long-or-cash strategy hypotheses."""
from dataclasses import dataclass
from statistics import mean, pstdev

ASSETS = ('BTC', 'ETH', 'SOL')

@dataclass(frozen=True)
class Strategy:
    id: str
    asset: str
    family: str
    n: int
    m: int


def candidates(count=100):
    # 6 families x 6 hyperparameter variants x 3 assets = 108 distinct
    # strategies; take first 100 in round-robin order across assets.
    families = ['sma', 'breakout', 'momentum', 'rsi', 'zscore', 'voltrend']
    pairs = {
        'sma': [(5,30),(8,50),(10,70),(15,90),(20,120),(30,150)],
        'breakout': [(12,5),(20,7),(30,10),(45,15),(60,20),(90,30)],
        'momentum': [(7,0),(14,0),(21,0),(35,0),(60,0),(100,0)],
        'rsi': [(8,25),(10,30),(14,30),(14,35),(20,35),(25,40)],
        'zscore': [(15,150),(20,175),(25,200),(35,175),(45,150),(60,125)],
        'voltrend': [(5,30),(8,40),(10,50),(15,60),(20,80),(30,100)],
    }
    out = []
    for variant in range(6):
        for family in families:
            for asset in ASSETS:
                n,m = pairs[family][variant]
                out.append(Strategy(f'{asset}-{family}-{n}-{m}', asset, family, n, m))
    return out[:count]


def signal(s, closes):
    """Evaluate using available COMPLETED bars only; 0 = cash, 1 = long."""
    c = closes
    if len(c) < max(s.n, s.m if s.family in ('sma','voltrend') else 0) + 2:
        return 0
    cur = c[-1]
    if s.family == 'sma':
        return int(mean(c[-s.n:]) > mean(c[-s.m:]))
    if s.family == 'breakout':
        # Long until drops below trailing shorter exit window.
        # Stateless variant: channel midpoint as an exit threshold.
        history = c[-s.n-1:-1]
        return int(cur > (max(history) + min(history[-s.m:]))/2)
    if s.family == 'momentum':
        return int(cur > c[-s.n-1])
    if s.family == 'rsi':
        diffs = [c[i]-c[i-1] for i in range(len(c)-s.n,len(c))]
        gain = sum(max(0,d) for d in diffs) / s.n
        loss = sum(max(0,-d) for d in diffs) / s.n
        rsi = 100 if loss == 0 else 100 - 100/(1+gain/loss)
        return int(rsi < s.m)  # contrarian, no short positions
    if s.family == 'zscore':
        window = c[-s.n:]
        sd = pstdev(window)
        z = (cur-mean(window)) / sd if sd else 0
        return int(z < -(s.m / 100))
    if s.family == 'voltrend':
        short = mean(c[-s.n:]); long = mean(c[-s.m:])
        daily_returns = [c[i]/c[i-1]-1 for i in range(len(c)-s.n+1,len(c))]
        vol = pstdev(daily_returns) if len(daily_returns)>1 else 0
        return int(short > long and vol < 0.075)
    raise ValueError(f'Unknown strategy family {s.family}')


def regime(closes):
    if len(closes) < 40:
        return 'insufficient-data'
    recent = closes[-20:]
    change = recent[-1]/recent[0]-1
    returns = [recent[i]/recent[i-1]-1 for i in range(1,len(recent))]
    volatile = pstdev(returns) > .045
    direction = 'uptrend' if change > .07 else ('downtrend' if change < -.07 else 'range')
    return ('high-volatility ' if volatile else '') + direction


def explain_signal(s, closes):
    """Plain-language explanation with actual numerical inputs, from known candles."""
    from math import isfinite
    c=closes
    target=signal(s,c)
    needed=max(s.n, s.m if s.family in ('sma','voltrend') else 0)+2
    if len(c)<needed:
        return f'Waiting for sufficient completed price history ({len(c)}/{needed} required).'
    cur=c[-1]
    if s.family=='sma':
        short=mean(c[-s.n:]);long=mean(c[-s.m:])
        return f'{s.n}-day average {short:,.2f} vs {s.m}-day average {long:,.2f}; '+('shorter is higher, LONG.' if target else 'shorter is not higher, CASH.')
    if s.family=='breakout':
        history=c[-s.n-1:-1]; threshold=(max(history)+min(history[-s.m:]))/2
        return f'Last close {cur:,.2f} vs channel threshold {threshold:,.2f}; '+('above threshold, LONG.' if target else 'not above threshold, CASH.')
    if s.family=='momentum':
        ref=c[-s.n-1]
        return f'Last close {cur:,.2f} vs {s.n} days prior {ref:,.2f}; '+('momentum positive, LONG.' if target else 'momentum not positive, CASH.')
    if s.family=='rsi':
        diffs=[c[i]-c[i-1] for i in range(len(c)-s.n,len(c))]
        gain=sum(max(0,x) for x in diffs)/s.n
        loss=sum(max(0,-x) for x in diffs)/s.n
        rsi=100 if loss==0 else 100-100/(1+gain/loss)
        return f'{s.n}-period RSI {rsi:.1f}, buy below {s.m}; '+('oversold signal, LONG.' if target else 'not oversold, CASH.')
    if s.family=='zscore':
        from statistics import pstdev
        window=c[-s.n:];sd=pstdev(window)
        z=(cur-mean(window))/sd if sd else 0
        return f'Price deviation {z:+.2f} standard deviations; buy below {-s.m/100:.2f}; '+('LONG.' if target else 'CASH.')
    if s.family=='voltrend':
        from statistics import pstdev
        short=mean(c[-s.n:]);long=mean(c[-s.m:])
        returns=[c[i]/c[i-1]-1 for i in range(len(c)-s.n+1,len(c))]
        vol=pstdev(returns) if len(returns)>1 else 0
        return f'Short/long averages {short:,.2f} / {long:,.2f}; observed daily volatility {100*vol:.1f}%, limit 7.5%; '+('LONG.' if target else 'CASH.')
    return 'No explanation available.'
