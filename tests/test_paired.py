import unittest
from unittest.mock import patch
from copy import deepcopy
from project_ten.paired import registry, create_book, buy, sell, mark, act, public_report, verify, research_spot
from project_ten.paired_signals import screen

def market(now=2000000000):
    bars=[]
    for i in range(500):
        p=100+i*.2
        bars.append({'t':now-(500-i)*3600,'o':p,'h':p*1.02,'l':p*.98,'c':p*1.001,'v':10000.})
    return {'id':'X','pair':'XUSD','asset':'BTC','sector':'majors','interval':60,
        'bars':bars,'bid':199.7,'ask':199.8,'quote_at':now,'spread_pct':.05,
        'volume_usd_24h':10_000_000,'qty_step':.000001,'min_qty':.0001,'min_cost':.5,'status':'online'}

def snapshot(m,now):
    return {'at':now,'spot':{'X':m},'futures':[],'failures':[],
        'dex_status':'blocked','llm_status':'disabled','news_status':'not implemented'}

class PairedTests(unittest.TestCase):
    def setUp(self):
        self.now=2000000000;self.m=market(self.now);self.s=snapshot(self.m,self.now)
        self.book=create_book({'rate':1.2,'as_of':'2033-01-01','source':'test'},self.now)
        self.a=self.book['accounts']['DUO-001']
        for a in self.book['accounts'].values():
            a['research']={'qualified':False,'selected':None,'reason':'test','candidates':[]}
            a['research_at']=self.now

    def test_fifty_distinct_pairs_and_independent_capital(self):
        ds=registry();self.assertEqual(len(ds),50)
        self.assertEqual(len({(d['desk'],d['family']) for d in ds}),50)
        self.assertEqual(len({d['researcher_id'] for d in ds}),50)
        self.a['cash']-=1
        self.assertEqual(self.book['accounts']['DUO-002']['cash'],120)

    def test_paid_costs_and_hypothetical_exit_separated(self):
        result=buy(self.book,self.a,self.m,self.now);self.assertTrue(result.startswith('BUY'))
        self.assertLessEqual(self.a['position']['qty']*self.a['position']['entry_price'],30)
        mark(self.a,self.s['spot'],self.now)
        d=public_report(self.book,self.s);verify(self.book,d)
        a=d['duos'][0]
        self.assertAlmostEqual(a['market_pnl_chf'],0)
        self.assertGreater(a['paid_fees_chf'],0)
        self.assertGreater(a['execution_impact_chf'],0)
        self.assertGreater(a['estimated_exit_cost_chf'],0)
        self.assertGreater(a['balance_chf'],a['liquidation_chf'])
        result=sell(self.book,self.a,self.m,self.now+1,'test exit')
        self.assertTrue(result.startswith('SELL'));mark(self.a,self.s['spot'],self.now+1)
        verify(self.book,public_report(self.book,self.s))
        self.assertIsNone(self.a['position']);self.assertLess(self.a['cash'],120)

    def test_venue_quantity_floor_blocks_without_mutating_cash(self):
        self.m['min_qty']=1000
        before=deepcopy(self.a)
        self.assertTrue(buy(self.book,self.a,self.m,self.now).startswith('REJECT'))
        self.assertEqual(self.a,before)

    def test_initialization_and_duplicate_bar_never_invent_orders(self):
        self.a['research']={'qualified':True,'selected':{'instrument':'X'},'reason':'test','candidates':[]}
        act(self.book,self.a,self.s,self.now,initial=True)
        act(self.book,self.a,self.s,self.now)
        self.assertEqual(self.a['orders'],0)
        # New closed bar creates a decision, repeated same candle cannot buy twice.
        self.m['bars'].append({'t':self.m['bars'][-1]['t']+3600,'o':200,'h':210,'l':198,'c':205,'v':10000})
        act(self.book,self.a,self.s,self.now)
        self.assertEqual(self.a['orders'],1)
        act(self.book,self.a,self.s,self.now)
        self.assertEqual(self.a['orders'],1)

    def test_missing_position_quote_preserves_position_and_flags_stale(self):
        buy(self.book,self.a,self.m,self.now)
        p=deepcopy(self.a['position']);cash=self.a['cash']
        self.s['spot']={};act(self.book,self.a,self.s,self.now)
        self.assertEqual(self.a['position'],p);self.assertEqual(self.a['cash'],cash)
        self.assertTrue(self.a['mark_stale']);self.assertIn('BLOCKED',self.a['last_decision'])

    def test_futures_cannot_execute(self):
        a=self.book['accounts']['DUO-041']
        a['research']={'qualified':True,'selected':{'instrument':'X'},'reason':'unvalidated simulator'}
        act(self.book,a,self.s,self.now)
        self.assertEqual(a['orders'],0);self.assertIsNone(a['position'])
        self.assertIn('BLOCKED',a['last_decision'])

    def test_holdout_does_not_select_another_asset_after_veto(self):
        m2=deepcopy(self.m);m2['id']='Y';self.s['spot']['Y']=m2
        def result(*args):
            if result.n==0:r={'train':{'net_pct':10},'qualified':False}
            else:r={'train':{'net_pct':5},'qualified':True}
            result.n+=1
            return r
        result.n=0
        with patch('project_ten.paired.evaluate',side_effect=result):r=research_spot(self.a,self.s,self.now)
        self.assertEqual(r['selected']['instrument'],'X');self.assertFalse(r['qualified'])

    def test_backtest_cannot_see_beyond_its_window(self):
        bars=deepcopy(self.m['bars'])
        a=screen('sma_trend',bars,150,350)
        for b in bars[350:]:b['c']*=20
        self.assertEqual(a,screen('sma_trend',bars,150,350))

    def test_stale_quote_cannot_trigger_order(self):
        self.m['quote_at']=self.now-121
        self.a['research']={'qualified':True,'selected':{'instrument':'X'},'reason':'test','candidates':[]}
        self.a['last_bars']['X']=self.m['bars'][-2]['t']
        act(self.book,self.a,self.s,self.now)
        self.assertEqual(self.a['orders'],0)
        self.assertIn('BLOCKED',self.a['last_decision'])

if __name__=='__main__':unittest.main()
