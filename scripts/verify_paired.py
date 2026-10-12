"""Verify persisted accounts and published report before Pages deployment."""
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from project_ten.paired import verify
b=json.loads((root/'state/paired_book.json').read_text())
r=json.loads((root/'docs/paired_dashboard.json').read_text())
verify(b,r)
assert (root/'reports/paired_dashboard.json').read_bytes()==(root/'docs/paired_dashboard.json').read_bytes()
assert r['meta']['mode']=='REAL PUBLIC PRICES / SIMULATED MONEY'
assert r['meta']['started_at']==b['started_at']
for d in r['duos']:
    a=b['accounts'][d['id']]
    assert d['orders']==a['orders']
    assert abs(d['balance_chf']-a['equity']/b['fx']['rate'])<.0001
print('Verified 50 independent paired ledgers, report consistency, accounting and paper-only restrictions.')
