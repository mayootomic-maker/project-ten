"""Command line: demo | sync | run | serve | report | audit."""
import argparse
import csv
import json
import sys
import shutil
from pathlib import Path
from . import __version__
from .demo import generate
from .data import candles, ticker, merge_history, load_csv, usd_per_chf, date_utc, MarketDataError
from .research import evaluate
from .incubator import propose
from .portfolio import make_book, advance, advance_at_quotes, observe_quotes, make_public_state
from .engine import Costs, verify_chain
from .storage import DATA, STATE, REPORTS, save_json, load_json, save_book, load_book


def _save_reports(research,book):
    state=make_public_state(research,book)
    state['proposals']=propose(research)
    save_json(REPORTS/'dashboard.json',state)
    rows=[{'rank':i,'code':a['sig']['code'],'name':a['sig']['name'],'asset':a['asset'],
           'family':a['family'],'net_chf':round(a['paper']['balance_chf']-100,3),
           'net_pct':a['paper']['net_pct'],'fees_chf':a['paper']['fees_chf'],
           'trades':a['paper']['trades'],'qualified':a['qualified']}
          for i,a in enumerate(sorted(state['agents'],key=lambda x:x['paper']['net_pct'],reverse=True),1)]
    REPORTS.mkdir(parents=True,exist_ok=True)
    with (REPORTS/'agents.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    REPORTS.joinpath('DAILY_REPORT.md').write_text(
      f"# Project Ten | {state['meta']['last_day'] or 'Not started'}\n\n"
      f"**Data:** {state['meta']['mode']} | **Capital:** CHF 100 (simulated)\n\n"
      f"Shared portfolio: **CHF {state['shared']['balance_chf']:.2f}** "
      f"({state['shared']['net_pct']:+.2f}%) after modeled execution costs.\n\n"
      f"Fees: CHF {state['shared']['fees_chf']:.3f}; executed orders: {state['shared']['trades']}; "
      f"maximum drawdown: {state['shared']['max_dd_pct']:.2f}%.\n\n"
      f"Candidates: {state['stats']['total']}; passed screen: {state['stats']['passed_train']}; "
      f"qualified: {state['stats']['qualified']}; deployed: {state['stats']['shortlist']}.\n\n"
      f"This is a simulated research experiment, not real or promised returns. "
      f"If data mode is SYNTHETIC, ALL performance shown is invented test data.\n",encoding='utf-8')
    print(f"{state['meta']['mode']} | {state['meta']['last_day']} | "
          f"{len(state['agents'])} agents | qualified {state['stats']['qualified']} | "
          f"portfolio CHF {state['shared']['balance_chf']:.2f}")


def cmd_demo(args):
    if not args.force and (STATE/'book.json').exists():
        raise SystemExit('Existing state detected; rerun with --force to replace it with synthetic demo data.')
    all_data=generate(900)
    # Strictly separate discovery/selection (first 720 days) from future replay (180 days).
    study={k:v[:720] for k,v in all_data.items()}
    research=evaluate(study,count=args.agents,cfg=Costs())
    book=make_book(research,all_data,capital_usd=120.,fx_usd_chf=1.2)
    for i in range(720,900):advance(book,research,all_data,i)
    save_json(STATE/'research.json',research);save_book(book)
    _save_reports(research,book)
    print('SYNTHETIC data only. Run: python -m project_ten serve')


def cmd_sync(args):
    """Acquire FREE public Kraken OHLC and currency reference, no broker credentials."""
    fetched={}
    for asset in ('BTC','ETH','SOL'):
        incoming=candles(asset)
        fetched[asset]=merge_history(DATA/f'{asset}.csv',incoming)
        print(f'{asset}: verified {len(fetched[asset])} completed daily bars, latest {date_utc(fetched[asset][-1]["t"])}')
    fx=usd_per_chf()
    save_json(DATA/'fx.json',fx)
    print(f'CHF/USD indicative reference: {fx["rate"]:.5f} as of {fx["as_of"]}')


def cmd_init(args):
    if (STATE/'book.json').exists() and not args.force:
        raise SystemExit('State already exists. Refusing to overwrite; --force to reset explicitly.')
    market={a:load_csv(DATA/f'{a}.csv') for a in ('BTC','ETH','SOL')}
    times={a:market[a][-1]['t'] for a in market}
    if len(set(times.values()))!=1:raise SystemExit(f'Assets not aligned: {times}. Re-sync required.')
    fx=load_json(DATA/'fx.json')
    base=100*fx['rate']
    research=evaluate(market,count=args.agents,cfg=Costs())
    book=make_book(research,market,capital_usd=base,fx_usd_chf=fx['rate'],dataset='KRAKEN REAL PRICES / VIRTUAL MONEY')
    book['meta']['fx_label']=f"Frozen reference CHF/USD {fx['as_of']} (not executable rate)"
    book['meta']['last_bar']=times['BTC']
    # Start forward AFTER newest complete historical bar; never retrospectively trade.
    save_json(STATE/'research.json',research);save_book(book)
    _save_reports(research,book)
    print('Initialized. Zero historical forward trades claimed; next day uses fresh Kraken data.')


def cmd_run(args):
    book=load_book(); research=load_json(STATE/'research.json')
    if book['meta']['mode'].startswith('SYNTHETIC'):
        raise SystemExit('Demo state cannot be upgraded to real-data mode. Run sync then init --force.')
    market={a:load_csv(DATA/f'{a}.csv') for a in ('BTC','ETH','SOL')}
    last=book['meta']['last_bar']; times=[b['t'] for b in market['BTC']]
    pending=[i for i,t in enumerate(times) if last is None or t>last]
    if not pending:
        quotes={a:ticker(a) for a in ('BTC','ETH','SOL')}
        observe_quotes(book,research,quotes)
        save_book(book)
        print('No new completed daily candle. Quotes refreshed; no duplicated orders.')
        _save_reports(research,book)
        return
    # Obtain fresh quotes before changing any persisted ledger state.
    # If GitHub skipped scheduled executions, never replay nonexistent historical fills.
    quotes={a:ticker(a) for a in ('BTC','ETH','SOL')}
    if len(pending)>1:
        from datetime import datetime, timezone
        from .engine import event_append
        skipped=len(pending)-1
        print(f'WARNING: Missed {skipped} full market evaluation(s). Skipping without simulated fills.')
        book['meta']['skipped_days']=book['meta'].get('skipped_days',0)+skipped
        book['meta']['last_bar']=times[pending[-1]-1]
        event_append(book['audit'],'missed_market_sessions',
                     {'skipped_days':skipped,'note':'No retrospective orders were manufactured'},
                     int(datetime.now(timezone.utc).timestamp()))
    advance_at_quotes(book,research,market,quotes)
    save_book(book);_save_reports(research,book)
    print('Model fills at current Kraken public bid/ask (+ slippage). No live orders.')


def cmd_live(args):
    """Idempotent one-command switch from synthetic demo to real-price paper mode.

    Never submits orders. A new live ledger starts with zero forward trades.
    Subsequent invocations update one day at most, using CURRENT public quotes.
    """
    from datetime import datetime, timezone
    from .storage import ROOT
    import shutil

    # Network-dependent operation; failure does not change live book or orders.
    cmd_sync(args)
    bookfile=STATE/'book.json'
    init_needed=not bookfile.exists()
    if not init_needed:
        book=load_book()
        init_needed=book['meta']['mode'].startswith('SYNTHETIC')
        if init_needed:
            backup=STATE/'synthetic-demo-backup'
            backup.mkdir(parents=True,exist_ok=True)
            for filename in ('book.json','research.json'):
                src=STATE/filename
                if src.exists() and not (backup/filename).exists():shutil.copy2(src,backup/filename)
            print('Original synthetic demonstration backed up in state/synthetic-demo-backup/.')
    if init_needed:
        print('Initializing REAL PRICE / VIRTUAL MONEY. Historic results are screening only.')
        cmd_init(argparse.Namespace(force=True,agents=100))
        book=load_book(); research=load_json(STATE/'research.json')
        quotes={a:ticker(a) for a in ('BTC','ETH','SOL')}
        observe_quotes(book,research,quotes)
        book['meta']['observation_started_at']=datetime.now(timezone.utc).isoformat()
        save_book(book);_save_reports(research,book)
        print('LIVE PAPER MODE INITIALIZED. First new completed daily bar triggers simulated decisions.')
    else:
        cmd_run(args)

def cmd_watch(args):
    """Hourly public-data polling while this local process remains running.

    The agent strategies themselves act at most once per completed daily candle.
    Closing the window/losing power ends this loop; GitHub Actions is the
    alternative for a free cloud-hosted daily schedule.
    """
    import threading
    import time
    from .app import serve

    cmd_live(args)
    def poll():
        while True:
            time.sleep(3600)
            try:
                cmd_live(args)
            except Exception as exc:
                print(f'Hourly paper update failed safely (no orders submitted): {exc}',flush=True)
    threading.Thread(target=poll,daemon=True,name='project-ten-paper-feed').start()
    print('Paper monitoring enabled: checks once per hour while THIS process stays open.')
    serve(args.host,args.port)

def cmd_export_offline(args):
    """Make a completely self-contained, phone-openable HTML snapshot."""
    from .storage import ROOT
    html=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
    css=(ROOT/'web'/'style.css').read_text(encoding='utf-8')
    js=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
    raw=(REPORTS/'dashboard.json').read_text(encoding='utf-8').replace('</','<\\/')
    html=html.replace('<link rel="stylesheet" href="/style.css">','<style>'+css+'</style>')
    html=html.replace('<script src="/app.js" defer></script>',
        '<script>const __PROJECT_TEN__='+raw+';window.fetch=async()=>({ok:true,json:async()=>__PROJECT_TEN__});</script><script>'+js+'</script>')
    dest=ROOT/'ProjectTen-Offline-Dashboard.html'
    dest.write_text(html,encoding='utf-8')
    print(f'Offline phone/desktop snapshot created: {dest.name} ({dest.stat().st_size//1024} KB).')
    print('Static snapshot, not a live data feed. No network connection required to view.')

def cmd_publish(args):
    """Build static phone-friendly dashboard for GitHub Pages (public research data only)."""
    from .storage import ROOT
    source=ROOT/'web';dest=ROOT/'docs'
    dest.mkdir(parents=True,exist_ok=True)
    html=(source/'index.html').read_text(encoding='utf-8')
    html=html.replace('href="/style.css"','href="./style.css"').replace('src="/app.js"','src="./app.js"')
    (dest/'index.html').write_text(html,encoding='utf-8')
    for file in ('style.css','app.js'):
        shutil.copy2(source/file,dest/file)
    shutil.copy2(REPORTS/'dashboard.json',dest/'dashboard.json')
    (dest/'.nojekyll').write_text('')
    print('Static dashboard prepared in docs/. Select GitHub Pages source: GitHub Actions.')
    print('No API keys, account access, or live order capability are included.')

def cmd_audit(args):
    book=load_book();verify_chain(book['audit'])
    print(f'VALID: {len(book["audit"])} sequential hash-linked virtual execution events.')
    print('Note: hash chain detects accidental local edits; it is not externally signed or tamper-proof.')


def main():
    p=argparse.ArgumentParser(prog='python -m project_ten',description='Project Ten — simulation-only multi-agent research lab')
    sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ('demo','init'):
        pp=sub.add_parser(cmd);pp.add_argument('--force',action='store_true');pp.add_argument('--agents',type=int,default=100,choices=range(1,109))
    sub.add_parser('sync');sub.add_parser('run');sub.add_parser('live');sub.add_parser('audit');
    watch=sub.add_parser('watch');watch.add_argument('--host',default='127.0.0.1');watch.add_argument('--port',type=int,default=8765)
    sub.add_parser('report');sub.add_parser('publish');sub.add_parser('export-offline')
    server=sub.add_parser('serve');server.add_argument('--host',default='127.0.0.1');server.add_argument('--port',type=int,default=8765)
    args=p.parse_args()
    if args.cmd=='demo':cmd_demo(args)
    elif args.cmd=='sync':cmd_sync(args)
    elif args.cmd=='init':cmd_init(args)
    elif args.cmd=='run':cmd_run(args)
    elif args.cmd=='live':cmd_live(args)
    elif args.cmd=='watch':cmd_watch(args)
    elif args.cmd=='audit':cmd_audit(args)
    elif args.cmd=='publish':cmd_publish(args)
    elif args.cmd=='export-offline':cmd_export_offline(args)
    elif args.cmd=='report':
        state=load_json(REPORTS/'dashboard.json');print(json.dumps({'meta':state['meta'],'shared':{k:v for k,v in state['shared'].items() if k not in ('curve','events')},'stats':state['stats']},indent=2))
    elif args.cmd=='serve':
        from .app import serve;serve(args.host,args.port)

if __name__=='__main__':main()
