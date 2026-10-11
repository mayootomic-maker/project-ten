"""Fee-aware, long-only, no-leverage simulated exchange + portfolio controls."""
from dataclasses import dataclass, asdict
from math import floor, log, sqrt, erf, isfinite
from statistics import mean
import hashlib
import json
import random

@dataclass(frozen=True)
class Costs:
    taker_fee: float = .008       # conservative configured assumption, 0.80% per side
    spread: float = .001          # ASSUMPTION: 10 bps total spread
    slippage: float = .0005       # ASSUMPTION: 5 bps per side
    min_order_usd: float = 10.0   # conservative configured floor, NOT venue guarantee
    qty_step: float = .00000001  # generic decimal precision; not pair-specific venue lot size
    partial_prob: float = 0.0
    reject_prob: float = 0.0
    extra_delay_prob: float = 0.0

    def stressed(self):
        return Costs(self.taker_fee*2, self.spread*2, self.slippage*2,
                     self.min_order_usd, self.qty_step, .15, .04, .05)


def executed_price(mid, side, cfg):
    return mid * (1 + (1 if side == 'buy' else -1) * (cfg.spread/2 + cfg.slippage))


def quantity_round(qty, step):
    return max(0.0, floor((qty + step*0.000001)/step) * step)


def execute(*, side, mid, cash, qty, notional, cfg, rng, quote=None):
    """Returns (new_cash, new_qty, fill-or-rejection). quote=(bid,ask) if live.

    Uses taker orders only. Limit-order queue model deliberately NOT fabricated.
    For partial fills the remainder is canceled, never assumed filled.
    """
    assert side in ('buy','sell')
    if rng.random() < cfg.reject_prob:
        return cash, qty, {'status':'rejected','reason':'injected_exchange_reject'}
    if rng.random() < cfg.extra_delay_prob:
        return cash, qty, {'status':'rejected','reason':'simulated_latency_timeout'}
    if quote:
        bid, ask = quote
        if not (0 < bid <= ask):
            return cash,qty,{'status':'rejected','reason':'invalid_quote'}
        price = (ask if side == 'buy' else bid)*(1 + (cfg.slippage if side=='buy' else -cfg.slippage))
    else:
        price = executed_price(mid, side, cfg)
    if side == 'buy':
        max_qty = min(notional/(price*(1+cfg.taker_fee)), cash/(price*(1+cfg.taker_fee)))
    else:
        max_qty = min(qty, notional/price)
    if rng.random() < cfg.partial_prob:
        max_qty *= rng.uniform(.35,.85)
    amount_qty = quantity_round(max_qty, cfg.qty_step)
    gross = amount_qty*price
    if gross + 1e-8 < cfg.min_order_usd:
        return cash,qty,{'status':'rejected','reason':'below_min_notional','gross':gross}
    fee = gross*cfg.taker_fee
    if side == 'buy':
        if gross+fee > cash + 1e-8:
            return cash,qty,{'status':'rejected','reason':'insufficient_cash'}
        cash -= gross+fee
        qty += amount_qty
    else:
        qty -= amount_qty
        cash += gross-fee
    if cash < -1e-7 or qty < -1e-7:
        raise AssertionError('Simulated negative cash/holdings')
    return max(0.0,cash), max(0.0,qty), {
        'status':'filled','side':side,'price':price,'qty':amount_qty,
        'gross':gross,'fee':fee,'partial': bool(notional > gross*(1+cfg.taker_fee)+1e-4),
    }


def liquidatable(cash, qty, mid, cfg):
    # Conservative daily mark-to-liquidation, includes hypothetical exit costs.
    return cash+qty*executed_price(mid, 'sell', cfg)*(1-cfg.taker_fee)


def backtest(strategy, bars, start, end, cfg=None, seed=13):
    """At day i open, act ONLY on signal from candles through i-1.
    No candle i price information is used to calculate the order signal.
    Signals are independent per strategy. Capital initialized at test window start.
    """
    from .strategies import signal
    cfg = cfg or Costs()
    rng = random.Random(seed)
    cash, qty, fees = 100.0, 0.0, 0.0
    curve, trades, total_reject = [100.0], [], 0
    closes = [b['c'] for b in bars]
    max_equity = 100.0
    stopped = False
    for i in range(start, min(end,len(bars))):
        b = bars[i]
        # Decision made using PREVIOUS day's completed close.
        target = signal(strategy, closes[:i])
        if stopped or (i and b['t'] - bars[i-1]['t'] != 86400):
            target = 0
        side = None
        if target and not qty:
            side = 'buy'
            notional = cash*0.95
        elif not target and qty:
            side = 'sell'
            notional = qty*b['o']*1.05  # sell whole position
        if side:
            next_cash,next_qty,record=execute(side=side,mid=b['o'],cash=cash,qty=qty,
                                             notional=notional,cfg=cfg,rng=rng)
            if record['status']=='filled':
                fees+=record['fee']; cash,qty=next_cash,next_qty
                record.update({'t':b['t'], 'equity_after':liquidatable(cash,qty,b['o'],cfg)})
                trades.append(record)
            else:
                total_reject += 1
        equity=liquidatable(cash,qty,b['c'],cfg)
        max_equity = max(max_equity,equity)
        if equity < 75.0:
            stopped=True
        curve.append(equity)
    peak=curve[0]; max_dd=0
    for val in curve:
        peak=max(peak,val)
        max_dd=max(max_dd,1-val/peak if peak else 1)
    returns=[curve[i]/curve[i-1]-1 for i in range(1,len(curve)) if curve[i-1]>0]
    return {'id':strategy.id, 'asset':strategy.asset, 'family':strategy.family,
            'net_pct': (curve[-1]/100-1)*100, 'end_usd':curve[-1],
            'max_dd_pct':max_dd*100,'fees_usd':fees, 'trades':len(trades),
            'rejections':total_reject, 'returns':returns,'curve':curve,
            'fills':trades, 'stopped':stopped}


def p_one_sided_hac(values, max_lag=7):
    """Approx one-sided HAC z-test vs zero, not an independence guarantee."""
    n=len(values)
    if n<60:
        return 1.0
    mu=mean(values)
    centered=[x-mu for x in values]
    gamma0=sum(x*x for x in centered)/n
    variance=gamma0
    for lag in range(1,min(max_lag,n-1)+1):
        gamma=sum(centered[i]*centered[i-lag] for i in range(lag,n))/n
        variance += 2*(1-lag/(max_lag+1))*gamma
    if variance<=0:
        return 1.0
    z=mu/sqrt(variance/n)
    return max(0.0,min(1.0,.5*(1-erf(z/sqrt(2)))))


def verify_chain(events):
    prev='GENESIS'
    for i, ev in enumerate(events):
        payload={k:v for k,v in ev.items() if k!='hash'}
        if ev.get('previous')!=prev or ev.get('hash')!=hash_event(payload):
            raise ValueError(f'Audit chain corrupted at event #{i}')
        prev=ev['hash']
    return True


def hash_event(ev):
    return hashlib.sha256(json.dumps(ev,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def event_append(events, kind, data, ts):
    prev=events[-1]['hash'] if events else 'GENESIS'
    ev={'kind':kind,'ts':ts,'data':data,'previous':prev}
    ev['hash']=hash_event(ev)
    events.append(ev)
    return ev
