"""Single-host continuous paper runner. Requires durable disk and sole ownership."""
import argparse
import fcntl
import json
import os
import signal
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from .storage import ROOT, save_json

class DashboardHandler(SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(404);return None
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        super().end_headers()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--confirm-sole-runner', action='store_true')
    parser.add_argument('--interval',type=int,default=60)
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    if not args.confirm_sole_runner:
        parser.error('Disable GitHub scheduled execution before activating this runner')
    if args.interval<60:
        parser.error('Minimum 60 seconds: respect public API limits')
    if not (ROOT/'state/paired_book.json').exists():
        parser.error('Import latest verified ledger before starting; refusing to reset portfolios')
    ROOT.joinpath('state').mkdir(exist_ok=True)
    lock=ROOT.joinpath('state/continuous.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    os.environ['PROJECT_TEN_CONTINUOUS']='1'
    os.environ['PROJECT_TEN_INTERVAL']=str(args.interval)
    from .paired import run
    from .notifications import run as notify
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda *_:stop.set())
    handler=partial(DashboardHandler,directory=str(ROOT/'docs'))
    server=ThreadingHTTPServer(('0.0.0.0',args.port),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    while not stop.is_set():
        began=time.monotonic()
        health={'mode':'continuous paper runner','attempt_at':int(time.time()),'interval_seconds':args.interval}
        try:
            run()
            health.update(status='healthy',last_success_at=int(time.time()))
            try:notify()
            except Exception:health['notifications']='retry pending'
        except Exception as exc:
            health.update(status='failed_closed',error_type=type(exc).__name__)
            print('Observation failed closed; see runtime health',flush=True)
        save_json(ROOT/'docs/runtime_health.json',health)
        stop.wait(max(0,args.interval-(time.monotonic()-began)))
    server.shutdown();lock.close()

if __name__=='__main__':main()
