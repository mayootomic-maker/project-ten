"""Public, unauthenticated Kraken spot data. No trading endpoints are used."""
import csv
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = 'https://api.kraken.com/0/public/'
PAIRS = {'BTC': 'XBTUSD', 'ETH': 'ETHUSD', 'SOL': 'SOLUSD'}
INTERVAL = 1440  # one day, UTC; about 720 completed candles per query
STEP = INTERVAL * 60

class MarketDataError(RuntimeError):
    pass


def get_json(url: str, timeout=15):
    request = urllib.request.Request(url, headers={'User-Agent': 'ProjectTenPaperResearch/0.1', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise MarketDataError(f'HTTP {response.status}')
        return json.load(response)


def kraken(endpoint, **params):
    url = BASE + endpoint + '?' + urllib.parse.urlencode(params)
    obj = get_json(url)
    if obj.get('error'):
        raise MarketDataError(f'Kraken {endpoint}: {obj["error"]}')
    return obj['result']


def candle_from_row(row):
    # Kraken row = [starttime, open, high, low, close, vwap, volume, count]
    return {'t': int(row[0]), 'o': float(row[1]), 'h': float(row[2]),
            'l': float(row[3]), 'c': float(row[4]), 'v': float(row[6])}


def require_recent_completed(rows, now=None):
    """Fail closed if latest completed UTC daily bar is missing or premature."""
    now=int(time.time() if now is None else now)
    if not rows:
        raise MarketDataError('No completed OHLC bars')
    age=now-int(rows[-1]['t'])
    if not STEP <= age < 2*STEP:
        raise MarketDataError(f'Latest completed daily candle is not current (age {age//3600}h)')
    return rows


def candles(asset):
    result = kraken('OHLC', pair=PAIRS[asset], interval=INTERVAL)
    rows = next(v for k,v in result.items() if k != 'last')
    now = int(time.time())
    # Omit *current* unfinished candle. API explicitly includes it.
    complete = [candle_from_row(r) for r in rows if int(r[0]) + STEP <= now]
    return require_recent_completed(validate(complete),now)


def ticker(asset):
    result = kraken('Ticker', pair=PAIRS[asset])
    row = next(iter(result.values()))
    bid, ask = float(row['b'][0]), float(row['a'][0])
    if not (0 < bid <= ask and math.isfinite(bid) and math.isfinite(ask)):
        raise MarketDataError(f'Invalid {asset} quote')
    if (ask - bid) / ((ask + bid) / 2) > 0.05:
        raise MarketDataError(f'{asset} quote spread > 5%, stop')
    return {'bid': bid, 'ask': ask, 'at': int(time.time())}


def usd_per_chf():
    """ECB-derived reference via Frankfurter; indicative FX, not executable rate."""
    obj = get_json('https://api.frankfurter.dev/v1/latest?base=CHF&symbols=USD')
    rate = float(obj['rates']['USD'])
    if not (0.1 < rate < 10):
        raise MarketDataError('Invalid CHF/USD conversion')
    return {'rate': rate, 'as_of': obj['date'], 'source': 'Frankfurter (ECB reference)'}


def validate(items, *, min_count=80):
    if len(items) < min_count:
        raise MarketDataError(f'Only {len(items)} candles, require {min_count}')
    items = sorted(items, key=lambda x: x['t'])
    seen = set()
    for i, c in enumerate(items):
        t, o, h, l, close, volume = (c[x] for x in ('t','o','h','l','c','v'))
        if t in seen or (i and t - items[i-1]['t'] != STEP):
            raise MarketDataError(f'Duplicate or missing daily bar near {t}')
        seen.add(t)
        if (not all(math.isfinite(v) for v in [o,h,l,close,volume])
                or l <= 0 or volume < 0 or l > min(o,close) or h < max(o,close)):
            raise MarketDataError(f'Invalid OHLCV at {t}')
        if i and abs(math.log(close/items[i-1]['c'])) > 1.0:
            raise MarketDataError(f'Unusually large close-to-close move at {t}; review manually')
    return items


def merge_history(file_path, incoming):
    """Preserve older valid history so periodic fetches can extend beyond 720 bars."""
    path = Path(file_path)
    old = load_csv(path) if path.exists() else []
    merged = {row['t']: row for row in old}
    for row in incoming:
        if row['t'] in merged and row != merged[row['t']]:
            # Provider revisions may happen; historical data change is serious.
            raise MarketDataError(f'Historical candle revised at {row["t"]}; manual review required')
        merged[row['t']] = row
    result = sorted(merged.values(), key=lambda x: x['t'])
    validate(result)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['t','o','h','l','c','v'])
        writer.writeheader()
        writer.writerows(result)
    tmp.replace(path)
    return result


def load_csv(path):
    with Path(path).open(newline='') as f:
        return validate([{'t':int(r['t']), **{k:float(r[k]) for k in ('o','h','l','c','v')}}
                         for r in csv.DictReader(f)])


def date_utc(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%d')
