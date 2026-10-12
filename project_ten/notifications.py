"""At-least-once paper trade alerts. No research outcomes are trade alerts."""
import argparse
import json
import os
import re
import time
import urllib.request
from .storage import ROOT, save_json
from .engine import verify_chain

DASHBOARD = 'https://mayootomic-maker.github.io/project-ten/'

def trades(book):
    verify_chain(book['audit'])
    if book.get('paper_only') is not True:
        raise ValueError('Refusing alerts for non-paper ledger')
    return [e for e in book['audit'] if e['kind'] in ('paper_buy', 'paper_sell')]

def publish(topic, message, title='Project Ten | PAPER trades'):
    if not re.fullmatch(r'[A-Za-z0-9_-]{24,100}', topic):
        raise ValueError('Use a long random notification topic')
    body=json.dumps({'topic':topic,'title':title,'message':message,
                     'click':DASHBOARD,'priority':3}).encode()
    request=urllib.request.Request('https://ntfy.sh/', data=body,
                                   headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        result=json.load(response)
    if not result.get('id'):
        raise ValueError('Push service did not confirm acceptance')
    return result['id']

def deliver(book, state, topic, sender=publish):
    rows=trades(book)
    # Establish baseline: do not present old orders as new trades at activation.
    if not state.get('initialized'):
        state.update(initialized=True, seen=[e['hash'] for e in rows], status='armed',
                     activated_at=int(time.time()))
        return 0
    seen=set(state.get('seen', []))
    pending=[e for e in rows if e['hash'] not in seen]
    if not pending:
        state['status']='armed';return 0
    # Batches preserve all trades; small messages stay under service size limits.
    for start in range(0,len(pending),10):
        batch=pending[start:start+10]
        lines=['SIMULATED MONEY / REAL PUBLIC QUOTES.']
        for e in batch:
            d=e['data']
            side='BUY' if e['kind']=='paper_buy' else 'SELL'
            lines.append(f"{d['duo']} {side} {d['asset']} | qty {d['qty']:.8g} | USD {d['price']:.8g} | fee USD {d['fee']:.4f} | UTC {e['ts']}")
        sender(topic,'\n'.join(lines))
        state.setdefault('seen',[]).extend(e['hash'] for e in batch)
        state['last_sent_at']=int(time.time())
        # Save each accepted batch so subsequent failures don't repeat it.
        if state.get('_persist'):
            save_json(ROOT/'state/notifications.json',state)
    state['status']='armed'
    return len(pending)

def run(test=False):
    topic=os.environ.get('NTFY_TOPIC','')
    if not topic:
        print('Push alerts disabled: subscription channel not configured');return
    if test:
        publish(topic,'Notification setup test. NO trade was made. Money remains simulated.',
                'Project Ten | Setup test')
        print('Setup notification accepted by push service');return
    path=ROOT/'state/notifications.json'
    state=json.loads(path.read_text()) if path.exists() else {}
    state['_persist']=True
    book=json.loads((ROOT/'state/paired_book.json').read_text())
    try:
        count=deliver(book,state,topic)
        print(f'Paper trade alerts accepted: {count}')
    except Exception:
        state['status']='delivery_failed_retry_pending'
        # Do not log URLs or topic secrets, including HTTP exception strings.
        print('Push delivery failed; unsent ledger events retained for retry')
        raise RuntimeError('Push service delivery failed') from None
    finally:
        save_json(path,state)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--test',action='store_true')
    run(parser.parse_args().test)
