"""Forward-only virtual execution, 100 individual ledgers and ONE shared book."""
from collections import defaultdict
from datetime import datetime,timezone
import copy
import random
from .engine import Costs, execute, executed_price, liquidatable, event_append, verify_chain
from .strategies import Strategy, signal, explain_signal


def make_book(research, market, capital_usd, fx_usd_chf, *, dataset='SYNTHETIC DEMO'):
    agents={a['id']:{'cash':capital_usd,'qty':0.,'fees':0.,'trades':0,'rejects':0,
                    'last_action':'Not evaluated','last_side':None,'events':[],
                    'equity':capital_usd,'curve':[capital_usd],'peak':capital_usd,
                    'max_drawdown':0.,'stopped':False,'last_signal':0} for a in research['agents']}
    shared={'cash':capital_usd,'positions':{},'fees':0.,'trades':0,'rejects':0,
            'curve':[capital_usd],'equity':capital_usd,'peak':capital_usd,
            'max_drawdown':0.,'stopped':False,'events':[]}
    return {'meta':{'mode':dataset,'initial_chf':100.0, 'fx_usd_per_chf':fx_usd_chf,
                    'fx_label':'Synthetic fixed rate' if dataset.startswith('SYNTHETIC') else 'Reference FX at initialization; frozen',
                    'currency':'USD','last_bar':None,'forward_days':0,'last_run':None,
                    'initial_usd':capital_usd,'feed':'Kraken historical OHLC, daily' if not dataset.startswith('SYNTHETIC') else 'Seeded synthetic daily candles',
                    'paper_only':True},'agents':agents,'shared':shared,'audit':[],
            'shortlist':research['shortlist']}


def _risk_update(account, equity):
    account['equity']=max(0.,equity)
    account['peak']=max(account['peak'],account['equity'])
    account['max_drawdown']=max(account['max_drawdown'],
                             1.-account['equity']/account['peak'] if account['peak'] else 1.)
    account['curve'].append(round(account['equity'],6))
    account['curve']=account['curve'][-300:]
    # This is a new-entry freeze, not a guaranteed stop-loss execution.
    if account['equity'] < account['peak']*.75:
        account['stopped']=True


def advance(book, research, market, i, cfg=None, *, quote_by_asset=None):
    """Advance exactly one simulation date. Positions executed at next bar open.

    Offline replay uses modeled open +/- spread/slippage. Online uses supplied best
    bid/ask, with additional slippage. Never uses future candles for signals.
    """
    cfg=cfg or Costs()
    rng=random.Random(99991+i)
    if i>=min(map(len,market.values())):raise IndexError('No complete candle at requested index')
    t=market['BTC'][i]['t']
    if any(market[a][i]['t']!=t for a in market):
        raise ValueError('Asset time grids differ: cannot safely advance')
    last=book['meta']['last_bar']
    if last is not None and t <= last:raise ValueError('Duplicate or retrograde time')
    if last is not None and t-last!=86400:raise ValueError('Time gap. Abort; do not pretend execution happened')
    agent_map={a['id']:a for a in research['agents']}
    signals={}
    for a in research['agents']:
        asset=a['asset']; s=Strategy(a['id'],asset,a['family'],a['params']['n'],a['params']['m'])
        signals[s.id]=signal(s,[bar['c'] for bar in market[asset][:i]])

    for a in research['agents']:
        aid=a['id']; asset=a['asset']; pos=book['agents'][aid]; b=market[asset][i]
        target=signals[aid]
        pos['reason']=explain_signal(Strategy(aid,asset,a['family'],a['params']['n'],a['params']['m']),[bar['c'] for bar in market[asset][:i]])
        pos['last_signal']=target
        if pos['stopped']:target=0
        side='buy' if target and pos['qty']<=1e-10 else 'sell' if not target and pos['qty']>1e-10 else None
        if side:
            notional=(pos['cash']*.95 if side=='buy' else pos['qty']*b['o']*1.05)
            cash, qty, rec=execute(side=side,mid=b['o'],cash=pos['cash'],qty=pos['qty'],notional=notional,cfg=cfg,
                                  rng=rng,quote=quote_by_asset.get(asset) if quote_by_asset else None)
            pos['last_action']=f'{side.upper()} filled' if rec['status']=='filled' else f'{side.upper()} rejected: {rec["reason"]}'
            pos['last_side']=side
            if rec['status']=='filled':
                pos['cash'],pos['qty']=cash,qty;pos['trades']+=1;pos['fees']+=rec['fee']
            else:pos['rejects']+=1
            entry={'t':t,'agent':aid,'asset':asset,'action':side,'book':'individual',**rec}
            pos['events'].append(entry);pos['events']=pos['events'][-20:]
            event_append(book['audit'],'execution',entry,t)
        else:
            pos['last_action']='Risk freeze' if pos['stopped'] else 'HOLD '+('position' if pos['qty'] else 'cash')
        _risk_update(pos,liquidatable(pos['cash'],pos['qty'],b['c'],cfg))

    shared=book['shared']; equity=shared['cash']
    for asset, position in shared['positions'].items():
        equity+=position['qty']*executed_price(market[asset][i]['o'],'sell',cfg)*(1-cfg.taker_fee)
    shortlist=book['shortlist']
    # Selling first avoids a buy firing with hypothetical funds from an unrealized sale.
    for aid in shortlist:
        a=agent_map[aid]; asset=a['asset']; position=shared['positions'].get(asset)
        if not position:continue
        if signals[aid] and not shared['stopped']:continue
        b=market[asset][i]
        cash,qty,rec=execute(side='sell',mid=b['o'],cash=shared['cash'],qty=position['qty'],
                             notional=position['qty']*b['o']*1.05,cfg=cfg,rng=rng,
                             quote=quote_by_asset.get(asset) if quote_by_asset else None)
        _shared_fill(book,asset,aid,'sell',rec,t)
        if rec['status']=='filled':
            shared['cash']=cash
            if qty<1e-10:shared['positions'].pop(asset,None)
            else:position['qty']=qty

    for aid in shortlist:
        a=agent_map[aid];asset=a['asset']
        if not signals[aid] or shared['stopped'] or asset in shared['positions']:continue
        b=market[asset][i]
        # Up to 28% of opening equity per distinct asset; 16%+ stays unallocated.
        budget=min(shared['cash']*.95,equity*.28)
        if budget < cfg.min_order_usd:continue
        cash,qty,rec=execute(side='buy',mid=b['o'],cash=shared['cash'],qty=0.,notional=budget,
                             cfg=cfg,rng=rng,quote=quote_by_asset.get(asset) if quote_by_asset else None)
        _shared_fill(book,asset,aid,'buy',rec,t)
        if rec['status']=='filled':
            shared['cash']=cash
            shared['positions'][asset]={'qty':qty,'agent':aid}

    current=shared['cash']+sum(position['qty']*executed_price(market[asset][i]['c'],'sell',cfg)*(1-cfg.taker_fee)
                                      for asset,position in shared['positions'].items())
    _risk_update(shared,current)
    book['meta']['last_bar']=t
    book['meta']['forward_days']+=1
    book['meta']['last_run']=datetime.now(timezone.utc).isoformat()
    return book


def _shared_fill(book,asset,aid,side,rec,t):
    shared=book['shared']
    item={'t':t,'agent':aid,'asset':asset,'action':side,'book':'shared',**rec}
    shared['events'].append(item);shared['events']=shared['events'][-80:]
    event_append(book['audit'],'execution',item,t)
    if rec['status']=='filled':shared['trades']+=1;shared['fees']+=rec['fee']
    else:shared['rejects']+=1


def make_public_state(research,book):
    from .data import date_utc
    base=book['meta']['initial_usd'];fx=book['meta']['fx_usd_per_chf']
    shared=book['shared']; agents=[]
    for a in research['agents']:
        pos=book['agents'][a['id']]
        agents.append({**a,'paper':{'balance_chf':round(pos['equity']/fx,2),
            'net_pct':round((pos['equity']/base-1)*100,2),
            'fees_chf':round(pos['fees']/fx,3),'trades':pos['trades'],
            'rejects':pos['rejects'],'last_action':pos['last_action'],
            'signal':'LONG' if pos['last_signal'] else 'CASH',
            'has_position':pos['qty']>1e-10,'stopped':pos['stopped'],
            'decision_reason':pos.get('reason','Not evaluated yet'),
            'max_dd_pct':round(pos['max_drawdown']*100,2),
            'curve':[round(v/fx,3) for v in pos['curve']],
            'events':pos['events'][-8:]}})
    return {'meta':{**book['meta'], 'last_day':date_utc(book['meta']['last_bar']) if book['meta']['last_bar'] else None},
            'stats':{'total':len(agents),'passed_train':sum(a['eligible_train'] for a in agents),
                     'qualified':research['qualified_count'],'active':sum(a['paper']['has_position'] for a in agents),
                     'total_agent_trades':sum(a['paper']['trades'] for a in agents),'shortlist':len(book['shortlist'])},
            'shared':{'balance_chf':round(shared['equity']/fx,2),
                      'net_pct':round((shared['equity']/base-1)*100,3),
                      'fees_chf':round(shared['fees']/fx,3),
                      'trades':shared['trades'],'rejects':shared['rejects'],
                      'max_dd_pct':round(shared['max_drawdown']*100,2),
                      'cash_chf':round(shared['cash']/fx,2),
                      'positions':{k:{'agent':v['agent'],'qty':v['qty']} for k,v in shared['positions'].items()},
                      'curve':[round(v/fx,3) for v in shared['curve']],
                      'stopped':shared['stopped'],'events':shared['events'][-30:]},
            'agents':agents,'benchmarks':research['benchmarks'],
            'shortlist':book['shortlist'], 'selection_note':research['selection_note'],
            'costs':research['costs'],'audit_events':len(book['audit']),
            'event_log':[e['data'] for e in book['audit'] if e['kind']=='execution']}


def advance_at_quotes(book, research, market, quotes, cfg=None):
    """Real-data forward evaluation at quotes received *after* latest daily close.

    Never pretends an earlier day's opening price remained available. A fill is
    a conservative modeled execution, NOT an actual broker/exchange confirmation.
    """
    import time
    cfg=cfg or Costs()
    now=int(time.time())
    if not all(asset in quotes for asset in ('BTC','ETH','SOL')):
        raise ValueError('Missing executable bid/ask quote: abort all trading')
    for asset, q in quotes.items():
        if q['at']>now+10 or now-q['at']>120:
            raise ValueError(f'{asset}: stale quote; abort')
        if not (0<q['bid']<=q['ask']):raise ValueError('Crossed or invalid quote')
    last_day=market['BTC'][-1]['t']
    if any(market[a][-1]['t']!=last_day for a in ('BTC','ETH','SOL')):
        raise ValueError('Unequal completed candle timestamps')
    if now<last_day+86400:
        raise ValueError('Latest daily candle has not completed')
    prior=book['meta']['last_bar']
    if prior is not None:
        if last_day<=prior:raise ValueError('This daily candle was already processed')
        if last_day-prior!=86400:raise ValueError('Unprocessed market days: do not backfill fictional fills')
    rng=random.Random(now)
    sigmap={}
    for a in research['agents']:
        bars=market[a['asset']]
        strategy=Strategy(a['id'],a['asset'],a['family'],a['params']['n'],a['params']['m'])
        sigmap[a['id']]=signal(strategy,[b['c'] for b in bars])
    amap={a['id']:a for a in research['agents']}
    for a in research['agents']:
        aid=a['id'];asset=a['asset'];book_pos=book['agents'][aid]
        bid=quotes[asset]['bid'];ask=quotes[asset]['ask'];mid=(bid+ask)/2
        target=sigmap[aid];book_pos['last_signal']=target
        book_pos['reason']=explain_signal(Strategy(aid,asset,a['family'],a['params']['n'],a['params']['m']),[b['c'] for b in market[asset]])
        if book_pos['stopped']:target=0
        side='buy' if target and book_pos['qty']<=1e-10 else 'sell' if not target and book_pos['qty']>1e-10 else None
        if side:
            size=(book_pos['cash']*.95 if side=='buy' else book_pos['qty']*ask*1.05)
            cash, qty, rec=execute(side=side,mid=mid,cash=book_pos['cash'],qty=book_pos['qty'],
                notional=size,cfg=cfg,rng=rng,quote=(bid,ask))
            book_pos['last_action']=f'{side.upper()} filled (quote-model)' if rec['status']=='filled' else f'{side.upper()} rejected: {rec["reason"]}'
            if rec['status']=='filled':
                book_pos['cash']=cash;book_pos['qty']=qty;book_pos['trades']+=1;book_pos['fees']+=rec['fee']
            else:book_pos['rejects']+=1
            rec={'t':now,'agent':aid,'asset':asset,'action':side,'book':'individual',
                 'execution_model':'post-close quote, not broker-confirmed',**rec}
            book_pos['events'].append(rec);book_pos['events']=book_pos['events'][-20:]
            event_append(book['audit'],'execution',rec,now)
        else:book_pos['last_action']='Risk freeze' if book_pos['stopped'] else 'HOLD '+('position' if book_pos['qty'] else 'cash')
        _risk_update(book_pos,book_pos['cash']+book_pos['qty']*bid*(1-cfg.slippage)*(1-cfg.taker_fee))
    shared=book['shared']
    equity=shared['cash']+sum(pos['qty']*quotes[asset]['bid']*(1-cfg.slippage)*(1-cfg.taker_fee)
                               for asset,pos in shared['positions'].items())
    for aid in book['shortlist']:
        asset=amap[aid]['asset'];position=shared['positions'].get(asset)
        if not position or (sigmap[aid] and not shared['stopped']):continue
        q=quotes[asset];bid,ask=q['bid'],q['ask']
        cash,qty,rec=execute(side='sell',mid=(bid+ask)/2,cash=shared['cash'],qty=position['qty'],
                       notional=position['qty']*ask*1.05,cfg=cfg,rng=rng,quote=(bid,ask))
        rec={'execution_model':'post-close quote, not broker-confirmed',**rec}
        _shared_fill(book,asset,aid,'sell',rec,now)
        if rec['status']=='filled':
            shared['cash']=cash
            if qty<1e-10:shared['positions'].pop(asset,None)
            else:position['qty']=qty
    for aid in book['shortlist']:
        asset=amap[aid]['asset']
        if not sigmap[aid] or shared['stopped'] or asset in shared['positions']:continue
        budget=min(shared['cash']*.95,equity*.28)
        if budget < cfg.min_order_usd:continue
        q=quotes[asset];bid,ask=q['bid'],q['ask']
        cash,qty,rec=execute(side='buy',mid=(bid+ask)/2,cash=shared['cash'],qty=0.,
                             notional=budget,cfg=cfg,rng=rng,quote=(bid,ask))
        rec={'execution_model':'post-close quote, not broker-confirmed',**rec}
        _shared_fill(book,asset,aid,'buy',rec,now)
        if rec['status']=='filled':
            shared['cash']=cash;shared['positions'][asset]={'qty':qty,'agent':aid}
    current=shared['cash']+sum(pos['qty']*quotes[asset]['bid']*(1-cfg.slippage)*(1-cfg.taker_fee)
                               for asset,pos in shared['positions'].items())
    _risk_update(shared,current)
    book['meta']['last_bar']=last_day
    book['meta']['forward_days']+=1
    book['meta']['last_run']=datetime.now(timezone.utc).isoformat()
    book['meta']['execution_kind']='public bid/ask + assumed slippage; never confirmed fills'
    book['meta']['quote_at']=max(q['at'] for q in quotes.values())
    book['meta']['quotes']={a:{'bid':q['bid'],'ask':q['ask'],'at':q['at']} for a,q in quotes.items()}
    return book


def observe_quotes(book, research, quotes, cfg=None):
    """Refresh real quote marks without creating trades or fictional forward days.

    One paper trade decision per completed daily candle. Extra price checks may
    update unrealized equity and freeze *new* entries; never backfill orders.
    """
    import time
    cfg=cfg or Costs()
    now=int(time.time())
    if set(quotes) != {'BTC','ETH','SOL'}:
        raise ValueError('All three public quotes required')
    for asset,q in quotes.items():
        if not (0<q['bid']<=q['ask']) or q['at']>now+10 or now-q['at']>120:
            raise ValueError(f'Stale or invalid public quote: {asset}')
    for a in research['agents']:
        pos=book['agents'][a['id']]
        q=quotes[a['asset']]
        value=pos['cash']+pos['qty']*q['bid']*(1-cfg.slippage)*(1-cfg.taker_fee)
        pos['equity']=max(0.,value)
        pos['peak']=max(pos['peak'],pos['equity'])
        pos['max_drawdown']=max(pos['max_drawdown'],1-pos['equity']/pos['peak'] if pos['peak'] else 1.)
        if pos['equity']<pos['peak']*.75:pos['stopped']=True
    shared=book['shared']
    equity=shared['cash']+sum(pos['qty']*quotes[asset]['bid']*(1-cfg.slippage)*(1-cfg.taker_fee)
                               for asset,pos in shared['positions'].items())
    shared['equity']=max(0.,equity)
    shared['peak']=max(shared['peak'],shared['equity'])
    shared['max_drawdown']=max(shared['max_drawdown'],1-shared['equity']/shared['peak'] if shared['peak'] else 1.)
    if shared['equity']<shared['peak']*.75:shared['stopped']=True
    book['meta']['quote_at']=max(q['at'] for q in quotes.values())
    book['meta']['quotes']={a:{'bid':q['bid'],'ask':q['ask'],'at':q['at']} for a,q in quotes.items()}
    return book
