"""50 researcher/trader pairs: transparent zero-budget, simulation-only prototype."""
import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from .paired_feeds import collect, refresh_quotes
from .paired_signals import FAMILIES, evaluate, decision, features
from .storage import save_json, ROOT
from .engine import event_append, verify_chain
from .paired_policies import policy_for, rank, futures_score
from .paired_learning import learn, summary as learning_summary, rank_adjustment

FEE=.008
SLIPPAGE=.0005
DESKS={'majors':'Major crypto / hourly','swing':'Major crypto / four-hour',
       'alts':'Liquid altcoins / hourly','memes':'Exchange-listed meme coins / hourly',
       'futures':'Perpetual futures / research only'}
BOOK=ROOT/'state/paired_book.json'

def registry():
    return [{'id':f'DUO-{i*10+j+1:03d}', 'researcher_id':f'R-{i*10+j+1:03d}',
        'trader_id':f'T-{i*10+j+1:03d}','desk':desk,'family':family,
        'policy':policy_for(desk,j,family),
        'mandate':f'{DESKS[desk]} · {title}'}
        for i,desk in enumerate(DESKS) for j,(family,title) in enumerate(FAMILIES.items())]

def create_book(fx, now):
    base=100*fx['rate']
    return {'schema':2,'paper_only':True,'started_at':now,'initial_chf':100.,'initial_usd':base,
        'fx':fx,'mode':'REAL PUBLIC PRICES / SIMULATED MONEY','llm_enabled':False,
        'audit':[], 'accounts':{d['id']:{**d,'cash':base,'position':None,'equity':base,
            'liquidation_equity':base,'fees':0.,'execution_impact':0.,'realized_market_pnl':0.,
            'orders':0,'rejects':0,'peak':base,'drawdown':0.,'last_bars':{},'research':None,
            'research_at':None,'last_decision':'Waiting for first research observation',
            'curve':[],'events':[],'blocked':False} for d in registry()}}

def research_spot(account, snapshot, now):
    rows=[]
    prior={r['instrument']:r for r in (account.get('research') or {}).get('candidates',[])}
    for key,m in snapshot['spot'].items():
        if m['sector']!=account['desk']:continue
        if m['volume_usd_24h']<1_000_000 or m['spread_pct']>.5:continue
        old=prior.get(key)
        if old and old.get('to')==m['bars'][-1]['t'] and old.get('validation_version')==3 and old.get('policy_fingerprint')==account['policy']['fingerprint']:
            e={k:v for k,v in old.items() if k not in ('instrument','asset','interval','volume_usd_24h','spread_pct','selection_score','learning_adjustment')}
        else:e=evaluate(account['family'],m['bars'],account.get('policy'),{**m,'capital':account.get('initial_capital',100.)})
        e['policy_fingerprint']=account.get('policy',{}).get('fingerprint')
        rows.append({'instrument':key,'asset':m['asset'],'interval':m['interval'],
            'volume_usd_24h':m['volume_usd_24h'],'spread_pct':m['spread_pct'],**e})
    # Never choose the best holdout performer. Training selects; later tests veto.
    policy=account.get('policy')
    for row in rows:
        adjustment=rank_adjustment(account,row['instrument']) if policy else 0.
        row['learning_adjustment']=adjustment
        row['selection_score']=(rank(row,policy) if policy else row['train']['net_pct'])+adjustment
    rows.sort(key=lambda x:x['selection_score'],reverse=True)
    chosen=rows[0] if rows else None
    return {'kind':'chronological price/volume research','candidates':rows,'selected':chosen,
        'selection':f"Research objective: {policy['objective'] if policy else 'net return'}. Rank uses training evidence and, for liquidity specialists, current liquidity/friction. Holdout returns never enter the rank; the chosen candidate must pass holdout and doubled-cost gates.",
        'qualified':bool(chosen and chosen['qualified']), 'observed_at':now,
        'reason':'Selected candidate passed exploratory tests' if chosen and chosen['qualified'] else
            'No candidate passed all validation gates' if chosen else 'No sufficiently liquid instrument with verified history',
        'limitations':'No news/sentiment, on-chain safety research, or LLM reasoning. Rolling screens repeat each run and overlap: exploratory evidence, not fresh independent holdouts or proof of edge.'}

def research_futures(account,snapshot,now):
    rows=snapshot['futures'][:]
    # Different research views; none translates unvalidated funding units into P&L.
    lens=account['policy']['objective']
    rows.sort(key=lambda r:futures_score(r,lens),reverse=True)
    return {'kind':'futures liquidity / funding / basis observation','candidates':rows[:5],
        'selected':rows[0] if rows else None,'qualified':False,'observed_at':now,
        'reason':'Futures execution blocked: funding history, contract-specific margin, liquidation and fill model need validation.',
        'limitations':'Ticker statistics are not an entry strategy. No futures returns or fills are simulated.'}

def valid_quote(m,now):
    return 0<m['bid']<=m['ask'] and math.isfinite(m['bid']+m['ask']) and 0<=now-m['quote_at']<=120

def mark(account,spot,now):
    p=account['position'];value=account['cash'];liq=value;unreal=0.
    if p:
        m=spot.get(p['instrument'])
        if not m or not valid_quote(m,now):
            account['mark_stale']=True;return False
        mid=(m['bid']+m['ask'])/2
        value+=p['qty']*mid;liq+=p['qty']*m['bid']*(1-SLIPPAGE)*(1-FEE)
        unreal=p['qty']*(mid-p['entry_mid'])
    account['mark_stale']=False;account['equity']=value;account['liquidation_equity']=liq
    account['unrealized_market_pnl']=unreal
    account['peak']=max(account['peak'],value)
    account['drawdown']=max(account['drawdown'],1-value/account['peak'])
    if value<account['peak']*.9:account['blocked']=True
    return True

def record(book,a,event,now):
    event={'duo':a['id'],'at':now,**event}
    a['events'].append(event);a['events']=a['events'][-30:]
    event_append(book['audit'],event['kind'],event,now)

def buy(book,a,m,now):
    mid=(m['bid']+m['ask'])/2;price=m['ask']*(1+SLIPPAGE)
    atr=features(m['bars'])['atr_pct']
    stop_pct=min(.15,max(.03,atr*2))
    round_trip=2*FEE+2*SLIPPAGE+(m['ask']-m['bid'])/mid
    target_pct=max(stop_pct*2,atr*4)
    if target_pct<round_trip*2:return 'REJECT: target distance too small relative to modeled costs'
    # ATR is a sizing input, NOT a forecast of expected profit.
    risk=a['equity']*.01;cap=.1 if a['desk']=='memes' else .25
    budget=min(a['cash']*.95,a['equity']*cap,risk/(stop_pct+round_trip))
    qty=math.floor(budget/(price*(1+FEE))/m['qty_step'])*m['qty_step']
    gross=qty*price;fee=gross*FEE
    if qty<m['min_qty'] or gross<max(10,m['min_cost']):return 'REJECT: venue minimum quantity/notional or configured USD 10 floor'
    if gross+fee>a['cash']+1e-8:return 'REJECT: insufficient simulated cash'
    a['cash']-=gross+fee;a['fees']+=fee;a['execution_impact']+=qty*(price-mid);a['orders']+=1
    a['position']={'instrument':m['id'],'asset':m['asset'],'qty':qty,'entry_mid':mid,
        'entry_price':price,'entry_at':now,'stop':price*(1-stop_pct),'target':price*(1+target_pct),
        'risk_budget_usd':risk,'research_at':a['research_at']}
    a['position']['entry_policy']=a.get('policy')
    record(book,a,{'kind':'paper_buy','asset':m['asset'],'instrument':m['id'],'qty':qty,'price':price,'fee':fee,
        'stop':a['position']['stop'],'target':a['position']['target'],'fill_model':'observed public ask + assumed slippage; no broker order'},now)
    return 'BUY: validated candidate and entry condition, modeled at current ask'

def sell(book,a,m,now,reason):
    p=a['position'];qty=p['qty'];mid=(m['bid']+m['ask'])/2;price=m['bid']*(1-SLIPPAGE)
    gross=qty*price
    if qty<m['min_qty'] or gross<max(10,m['min_cost']):return 'REJECT EXIT: venue minimum; position remains marked and held'
    fee=gross*FEE;a['cash']+=gross-fee;a['fees']+=fee;a['execution_impact']+=qty*(mid-price)
    a['realized_market_pnl']+=qty*(mid-p['entry_mid']);a['orders']+=1;a['position']=None
    record(book,a,{'kind':'paper_sell','asset':m['asset'],'qty':qty,'price':price,'fee':fee,'reason':reason,
        'fill_model':'observed public bid - assumed slippage; no broker order'},now)
    return 'SELL: '+reason+'; observed bid, never a guaranteed stop price'

def act(book,a,snapshot,now,initial=False):
    spot=snapshot['spot']
    if a['desk']=='futures':
        a['last_decision']='BLOCKED: '+a['research']['reason'];return
    if not mark(a,spot,now):a['last_decision']='BLOCKED: missing/stale position quote';return
    p=a['position'];chosen=a['research'].get('selected')
    key=p['instrument'] if p else chosen['instrument'] if chosen else None
    if key not in spot:a['last_decision']='WAIT: no usable selected instrument';return
    m=spot[key];bar=m['bars'][-1]['t'];last=a['last_bars'].get(key)
    if not valid_quote(m,now):a['last_decision']='BLOCKED: stale executable quote';return
    if m['spread_pct']>.5:a['last_decision']='BLOCKED: spread exceeds 0.5%';return
    # Risk exits may act on the current observation even without a new completed bar.
    entry_policy=(p.get('entry_policy') or a.get('policy')) if p else None
    time_exit=bool(p and entry_policy and now-p['entry_at']>=entry_policy['max_holding_bars']*m['interval']*60)
    if p and (m['bid']<=p['stop'] or m['bid']>=p['target'] or a['blocked'] or time_exit):
        reason='observed stop breach' if m['bid']<=p['stop'] else 'observed target reached' if m['bid']>=p['target'] else 'drawdown freeze' if a['blocked'] else 'policy maximum holding time'
        a['last_decision']=sell(book,a,m,now,reason)
        if a['last_decision'].startswith('REJECT'):a['rejects']+=1
        mark(a,spot,now);a['last_bars'][key]=bar;return
    if initial or last is None:
        a['last_bars'][key]=bar;a['last_decision']='OBSERVING: no retrospective entry; wait for a new completed candle';return
    if bar<=last:a['last_decision']='HOLD: no new completed candle; refreshed price mark';return
    if bar-last>m['interval']*60:
        record(book,a,{'kind':'missed_observation','instrument':key,'bars_skipped':(bar-last)//(m['interval']*60)-1,
            'note':'No historical fills manufactured; current quote evaluation only'},now)
    a['last_bars'][key]=bar
    target,why=decision(a['family'],m['bars'],bool(p),policy=entry_policy if p else a.get('policy'));a['signal_reason']=why
    if p:
        a['last_decision']='HOLD position: '+why if target else sell(book,a,m,now,'strategy exit')
    elif a['blocked']:a['last_decision']='BLOCKED: 10% observed drawdown freeze'
    elif not a['research']['qualified']:a['last_decision']='REJECT: research did not pass validation'
    elif not target:a['last_decision']='WAIT: '+why
    else:a['last_decision']=buy(book,a,m,now)
    if a['last_decision'].startswith('REJECT'):
        a['rejects']+=1
        record(book,a,{'kind':'rejected_proposal','instrument':key,'reason':a['last_decision']},now)
    mark(a,spot,now)

def public_report(book,snapshot):
    fx=book['fx']['rate'];base=book['initial_usd'];now=snapshot['at'];duos=[]
    for a in book['accounts'].values():
        unreal=a.get('unrealized_market_pnl',0);gross_pnl=a['realized_market_pnl']+unreal
        exit_cost=max(0,a['equity']-a['liquidation_equity'])
        duos.append({k:a[k] for k in ('id','researcher_id','trader_id','desk','family','policy','mandate','research','research_at','last_decision','events','orders','rejects','position','curve')}|{
            'balance_chf':round(a['equity']/fx,4),'liquidation_chf':round(a['liquidation_equity']/fx,4),
            'net_pct':round((a['equity']/base-1)*100,4),'market_pnl_chf':round(gross_pnl/fx,5),
            'paid_fees_chf':round(a['fees']/fx,5),'execution_impact_chf':round(a['execution_impact']/fx,5),
            'estimated_exit_cost_chf':round(exit_cost/fx,5),'cash_chf':round(a['cash']/fx,4),
            'drawdown_pct':round(a['drawdown']*100,4),'stale_mark':a.get('mark_stale',False),
            'signal_reason':a.get('signal_reason'),'blocked':a['blocked']})
        duos[-1]['learning']=learning_summary(a)
    instruments=[{k:v for k,v in m.items() if k!='bars'} for m in snapshot['spot'].values()]
    return {'meta':{'schema':2,'paper_only':True,'mode':book['mode'],'started_at':book['started_at'],
        'observed_at':now,'initial_chf_per_duo':100,'research_workers':50,'trading_workers':50,
        'runtime':'GitHub Actions monitoring requested every 5 minutes; research recomputed for new closed candles. Best effort, not continuous hosting.',
        'monitor_interval_seconds':300,'pipeline_metrics':snapshot.get('pipeline_metrics',{}),
        'llm_status':snapshot['llm_status'],'fx':book['fx'],'fee_per_side':FEE,'slippage_per_side':SLIPPAGE,
        'risk':'1% sizing budget, max 25% position (10% listed memes), 10% drawdown entry freeze. Stops checked only when a job observes quotes; gaps may exceed budget.'},
        'stats':{'duos':50,'positions':sum(bool(a['position']) for a in duos),
            'qualified':sum(bool(a['research']['qualified']) for a in duos),'orders':sum(a['orders'] for a in duos),
            'rejected':sum(a['rejects'] for a in duos),'spot_instruments':len({m['pair'] for m in instruments}),
            'futures_observed':len(snapshot['futures']),'research_only_duos':10},
        'learning_stats':{'pending':sum(d['learning']['pending'] for d in duos),
            'completed_usable':sum(d['learning']['samples'] for d in duos),
            'late_excluded':sum(d['learning']['late_outcomes'] for d in duos)},
        'duos':duos,'spot_universe':instruments,'futures':snapshot['futures'],
        'feed_failures':snapshot['failures'],'dex_status':snapshot['dex_status'],'news_status':snapshot['news_status'],
        'audit_events':len(book['audit']),'notes':['No real-money credentials or order endpoints.',
            'V1 results retained at legacy/. New portfolios begin at their own timestamp; old losses are not erased.',
            '100 workers are 50 paired deterministic research/trading pipelines, not 100 LLMs.',
            'Cash and buy-and-hold benchmarks are needed when assessing returns; one selected holdout is not proof of profitability.']}

def verify(book,report):
    verify_chain(book['audit'])
    assert book['paper_only'] is report['meta']['paper_only'] is True
    assert not book['llm_enabled']
    assert len(book['accounts'])==len(report['duos'])==50
    assert len({d['researcher_id'] for d in report['duos']})==50
    assert len({d['trader_id'] for d in report['duos']})==50
    assert len({d['policy']['fingerprint'] for d in report['duos']})==50
    for a in book['accounts'].values():
        assert math.isfinite(a['cash']) and a['cash']>=-1e-7
        if a['desk']=='futures':assert not a['position'] and a['orders']==0
        if a['position']:assert a['position']['qty']>0
        if not a.get('mark_stale'):
            expected=book['initial_usd']+a['realized_market_pnl']+a.get('unrealized_market_pnl',0)-a['fees']-a['execution_impact']
            assert abs(a['equity']-expected)<1e-6, (a['id'],a['equity'],expected)
    assert report['stats']['orders']==sum(a['orders'] for a in book['accounts'].values())

def run():
    clock=time.perf_counter()
    print('Collecting verified public spot histories and futures observations...',flush=True)
    snapshot=collect();now=snapshot['at'];initial=not BOOK.exists()
    collected=time.perf_counter()
    print(f"Collected {len(snapshot['spot'])} instrument/timeframe histories; {len(snapshot['futures'])} futures observations.",flush=True)
    if initial:
        from .data import usd_per_chf
        fx=None
        for attempt in range(3):
            try:fx=usd_per_chf();break
            except Exception:
                if attempt==2:raise
                time.sleep(.5*(attempt+1))
        book=create_book(fx,now)
    else:book=json.loads(BOOK.read_text());verify_chain(book['audit'])
    for d in registry():
        a=book['accounts'][d['id']]
        a.setdefault('initial_capital',book['initial_usd'])
        if a.get('policy')!=d['policy']:
            a['policy']=d['policy']
            record(book,a,{'kind':'policy_revision','policy':d['policy'],
                'note':'Decision mandate changed; balances, start time and prior orders preserved.'},now)
    for a in book['accounts'].values():
        if a['id'] in ('DUO-001','DUO-011','DUO-021','DUO-031','DUO-041'):
            print(f"Processing research desk: {a['desk']}",flush=True)
        if a['desk']=='futures':a['research']=research_futures(a,snapshot,now);a['research_at']=now
        else:
            a['research']=research_spot(a,snapshot,now);a['research_at']=now
            selected=a['research']['selected']
            fingerprint=(selected['instrument'],selected['to'],a['research']['qualified'],a['policy']['fingerprint']) if selected else (None,a['policy']['fingerprint'])
            if a.get('research_fingerprint')!=list(fingerprint):
                record(book,a,{'kind':'research_snapshot','chosen':selected['instrument'] if selected else None,
                    'qualified':a['research']['qualified'],'note':a['research']['selection']},now)
                a['research_fingerprint']=list(fingerprint)
    researched=time.perf_counter()
    refresh_quotes(snapshot);now=int(time.time());snapshot['at']=now
    snapshot['pipeline_metrics']={'fetch_seconds':round(collected-clock,3),
        'research_seconds':round(researched-collected,3),
        'quote_refresh_seconds':round(time.perf_counter()-researched,3),
        'history_cache_hits':snapshot.get('history_cache_hits',0)}
    for a in book['accounts'].values():
        learn(a,snapshot,now,FEE,SLIPPAGE)
        act(book,a,snapshot,now,initial)
        if not a.get('mark_stale'):
            a['curve'].append({'t':now,'equity_chf':round(a['equity']/book['fx']['rate'],5),
                'liquidation_chf':round(a['liquidation_equity']/book['fx']['rate'],5)})
            a['curve']=a['curve'][-500:]
    snapshot['pipeline_metrics']['processing_seconds']=round(time.perf_counter()-clock,3)
    report=public_report(book,snapshot);verify(book,report)
    # Persist only after all research, accounting and audit checks pass.
    save_json(BOOK,book);save_json(ROOT/'reports/paired_dashboard.json',report)
    save_json(ROOT/'docs/paired_dashboard.json',report)
    save_json(ROOT/'data/paired_market.json',snapshot)
    print(json.dumps({'mode':book['mode'],'stats':report['stats'],'failures':snapshot['failures']}))

if __name__=='__main__':run()
