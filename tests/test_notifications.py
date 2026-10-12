import unittest
from copy import deepcopy
from project_ten.engine import event_append
from project_ten.notifications import deliver

class Alerts(unittest.TestCase):
    def book(self):return {'paper_only':True,'audit':[]}
    def add(self,b,kind='paper_buy'):
        event_append(b['audit'],kind,{'duo':'DUO-001','asset':'BTC','qty':.001,'price':80000.,'fee':.64},123)
    def test_baseline_does_not_send_old_trades(self):
        b=self.book();self.add(b);s={};sent=[]
        self.assertEqual(deliver(b,s,'t',lambda *x:sent.append(x)),0)
        self.assertEqual(sent,[])
    def test_only_actual_paper_events_and_no_duplicate(self):
        b=self.book();s={};deliver(b,s,'t');self.add(b,'research_snapshot');self.add(b);self.add(b,'paper_sell');sent=[]
        self.assertEqual(deliver(b,s,'t',lambda *x:sent.append(x)),2)
        self.assertEqual(len(sent),1);self.assertIn('SIMULATED MONEY',sent[0][1])
        self.assertEqual(deliver(b,s,'t',lambda *x:sent.append(x)),0)
    def test_failure_retains_pending_and_portfolio_untouched(self):
        b=self.book();s={};deliver(b,s,'t');self.add(b);before=deepcopy(b)
        def fail(*x):raise RuntimeError('offline')
        with self.assertRaises(RuntimeError):deliver(b,s,'t',fail)
        self.assertEqual(s['seen'],[]);self.assertEqual(b,before)
    def test_non_paper_and_invalid_audit_rejected(self):
        b=self.book();b['paper_only']=False
        with self.assertRaises(ValueError):deliver(b,{},'t')
        b=self.book();self.add(b);b['audit'][0]['data']['qty']=99
        with self.assertRaises(ValueError):deliver(b,{},'t')
