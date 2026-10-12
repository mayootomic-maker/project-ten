"""Read-only free public feeds. Provider failures remain visible and fail closed."""
import concurrent.futures
import math
import time
import urllib.parse
from .data import get_json as raw_get_json, candle_from_row

def get_json(url, timeout=15):
    error=None
    for attempt in range(3):
        try:return raw_get_json(url,timeout=timeout)
        except Exception as exc:
            error=exc
            if attempt<2:time.sleep(.5*(attempt+1))
    raise error

def kraken(endpoint, **params):
    obj=get_json('https://api.kraken.com/0/public/'+endpoint+'?'+urllib.parse.urlencode(params))
    if obj.get('error'):raise ValueError(f'Kraken {endpoint}: {obj["error"]}')
    return obj['result']

MAJORS={'XBT','ETH','SOL','XRP','LTC','BCH'}
ALTS={'ADA','LINK','AVAX','DOT','ATOM','NEAR'}
MEMES={'XDG','DOGE','SHIB','PEPE','BONK','WIF','FLOKI','TRUMP','FARTCOIN'}

def fetch_spot_one(pair, spec, ticker_row, now, interval=60):
    step=interval*60
    result=kraken('OHLC',pair=pair,interval=interval)
    rows=next(v for k,v in result.items() if k!='last')
    bars=[candle_from_row(r) for r in rows if int(r[0])+step<=now]
    if len(bars)<400:raise ValueError('fewer than 400 completed hourly candles')
    if not step<=now-bars[-1]['t']<step*2:raise ValueError('stale history')
    for i,b in enumerate(bars):
        if not all(math.isfinite(b[k]) for k in ('o','h','l','c','v')) or b['l']<=0 or b['v']<0 or b['l']>min(b['o'],b['c']) or b['h']<max(b['o'],b['c']):raise ValueError('invalid OHLCV')
        if i and b['t']-bars[i-1]['t']!=step:raise ValueError('missing or duplicate candles')
    bid=float(ticker_row['b'][0]);ask=float(ticker_row['a'][0])
    if not 0<bid<=ask or not math.isfinite(bid+ask):raise ValueError('invalid bid/ask')
    base=spec['wsname'].split('/')[0]
    return {'id':pair if interval==60 else pair+'@240','pair':pair,'interval':interval,'asset':'BTC' if base=='XBT' else 'DOGE' if base=='XDG' else base,
        'sector':'swing' if interval==240 else 'majors' if base in MAJORS else 'alts' if base in ALTS else 'memes',
        'bars':bars,'bid':bid,'ask':ask,'quote_at':now,'spread_pct':(ask-bid)/((ask+bid)/2)*100,
        'volume_usd_24h':float(ticker_row['v'][1])*float(ticker_row['p'][1]),
        'qty_step':10**-int(spec['lot_decimals']),'min_qty':float(spec['ordermin']),
        'min_cost':float(spec.get('costmin',10)),'status':spec.get('status'),
        'source':'Kraken public OHLC / Ticker / AssetPairs'}

def collect():
    now=int(time.time()); failures=[]
    specs=kraken('AssetPairs');wanted=MAJORS|ALTS|MEMES
    selected={k:v for k,v in specs.items() if v.get('wsname','').endswith('/USD') and v['wsname'].split('/')[0] in wanted and v.get('status')=='online'}
    # One quote request per pair, obtained AFTER historical research downloads below.
    jobs=[(k,s,60) for k,s in selected.items()]+[(k,s,240) for k,s in selected.items() if s['wsname'].split('/')[0] in MAJORS]
    def one(item):
        k,s,interval=item
        try:
            t=kraken('Ticker',pair=k);row=next(iter(t.values()))
            data=fetch_spot_one(k,s,row,int(time.time()),interval)
            return data['id'],data,None
        except Exception as e:return k,None,str(e)
    spot={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for k,data,error in pool.map(one,jobs):
            if data:spot[k]=data
            else:failures.append({'source':'Kraken spot','instrument':k,'error':error})
    if not spot:raise RuntimeError('No verified spot histories; abort without changing portfolios')
    futures=[]
    try:
        obj=get_json('https://futures.kraken.com/derivatives/api/v3/tickers',timeout=20)
        if obj.get('result')!='success':raise ValueError('futures feed unsuccessful')
        for r in obj['tickers']:
            if r.get('tag')!='perpetual' or r.get('suspended') or not r.get('symbol','').startswith('PF_'):continue
            bid=float(r.get('bid',0));ask=float(r.get('ask',0))
            if not 0<bid<=ask or not math.isfinite(bid+ask):continue
            futures.append({'instrument':r['symbol'],'pair':r.get('pair'), 'bid':bid,'ask':ask,
                'volume_usd_24h':r.get('volumeQuote'), 'open_interest':r.get('openInterest'),
                'funding_rate_provider_units':r.get('fundingRate'),'relative_funding_rate_provider_units':r.get('relativeFundingRate'),
                'basis_pct':100*(r['markPrice']/r['indexPrice']-1) if r.get('indexPrice',0)>0 else None,
                'change_24h_pct':r.get('change24h'),'observed_at':int(time.time()),
                'execution':'BLOCKED: historical funding, contract-specific margin/liquidation and fill model not validated'})
        futures.sort(key=lambda r:float(r.get('volume_usd_24h') or 0),reverse=True)
    except Exception as e:failures.append({'source':'Kraken futures','error':str(e)})
    return {'at':int(time.time()),'spot':spot,'futures':futures[:30],'failures':failures,
        'dex_status':'BLOCKED: no validated contract/holder/sellability/on-chain execution checks. Listed meme coins are a separate spot universe.',
        'llm_status':'DISABLED: zero-budget deterministic research; no unattended LLM reasoning or web/news interpretation',
        'news_status':'NOT IMPLEMENTED: no sentiment or news-based trade decisions'}

def refresh_quotes(snapshot):
    """Do not execute against quotes captured before expensive research."""
    refreshed={}
    for key in list(snapshot['spot']):
        try:
            pair=snapshot['spot'][key]['pair']
            if pair not in refreshed:
                row=next(iter(kraken('Ticker',pair=pair).values()))
                refreshed[pair]=(float(row['b'][0]),float(row['a'][0]),int(time.time()))
            bid,ask,at=refreshed[pair]
            if not 0<bid<=ask or not math.isfinite(bid+ask):raise ValueError('invalid quote')
            m=snapshot['spot'][key];m.update(bid=bid,ask=ask,quote_at=at,spread_pct=100*(ask-bid)/((ask+bid)/2))
        except Exception as e:
            snapshot['failures'].append({'source':'quote refresh','instrument':key,'error':str(e)})
            del snapshot['spot'][key]
