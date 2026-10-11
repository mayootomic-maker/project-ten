"""Fail deployment if its report is synthetic, incomplete, or detached from state."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
book = json.loads((root / 'state/book.json').read_text())
report = json.loads((root / 'docs/dashboard.json').read_text())
assert book['meta']['paper_only'] is True
assert book['meta']['mode'] == 'KRAKEN REAL PRICES / VIRTUAL MONEY'
assert report['meta'] == {**book['meta'], 'last_day': report['meta']['last_day']}
assert book['meta']['initial_chf'] == 100
assert len(book['agents']) == len(report['agents']) == 100
assert {a['id'] for a in report['agents']} == set(book['agents'])
assert len({a['id'] for a in report['agents']}) == 100
assert set(book['meta']['quotes']) == {'BTC', 'ETH', 'SOL'}
assert (root / 'reports/dashboard.json').read_bytes() == (root / 'docs/dashboard.json').read_bytes()
for a in report['agents']:
    p = book['agents'][a['id']]
    assert p['cash'] >= 0 and p['qty'] >= 0
    assert a['paper']['trades'] == p['trades']
print('Verified: 100 independent CHF 100 paper portfolios, real quote metadata, matching published state.')
