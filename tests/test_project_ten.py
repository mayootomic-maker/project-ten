import unittest
import math
import random
import time
from copy import deepcopy
from project_ten.demo import generate
from project_ten.data import validate, require_recent_completed, MarketDataError
from project_ten.strategies import candidates, signal
from project_ten.engine import Costs,execute,event_append,verify_chain,backtest
from project_ten.research import evaluate, holm_pvalues
from project_ten.incubator import propose
from project_ten.portfolio import make_book, advance, advance_at_quotes, observe_quotes, make_public_state

class ProjectTenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market=generate(520)

    def test_stale_market_candles_rejected(self):
        last_day=self.market['BTC'][:90]
        latest=last_day[-1]['t']
        self.assertIs(require_recent_completed(last_day, latest+86400+100),last_day)
        with self.assertRaises(MarketDataError):
            require_recent_completed(last_day, latest+2*86400+1)
        with self.assertRaises(MarketDataError):
            require_recent_completed(last_day, latest+86399)

    def test_exactly_100_unique_strategies(self):
        pool=candidates(100)
        self.assertEqual(len(pool),100)
        self.assertEqual(len({p.id for p in pool}),100)
        self.assertEqual(len({(p.asset,p.family,p.n,p.m) for p in pool}),100)

    def test_missing_bar_fails_closed(self):
        rows=deepcopy(self.market['BTC'][:90]);del rows[17]
        with self.assertRaises(MarketDataError):validate(rows)

    def test_invalid_price_and_duplicates_rejected(self):
        rows=deepcopy(self.market['BTC'][:90]);rows[4]['h']=0
        with self.assertRaises(MarketDataError):validate(rows)
        rows=deepcopy(self.market['BTC'][:90]);rows[3]=rows[2]
        with self.assertRaises(MarketDataError):validate(rows)

    def test_cannot_buy_more_than_available_cash(self):
        cash,qty,e=execute(side='buy',mid=100,cash=100,qty=0,notional=200,
                           cfg=Costs(),rng=random.Random(1))
        self.assertEqual(e['status'],'filled')
        self.assertGreaterEqual(cash,0)
        self.assertGreaterEqual(qty,0)
        self.assertLessEqual(cash+qty*e['price'],100)

    def test_minimum_order_enforced(self):
        cash,qty,e=execute(side='buy',mid=100,cash=100,qty=0,notional=5,
                           cfg=Costs(),rng=random.Random(1))
        self.assertEqual(e['status'],'rejected')
        self.assertEqual(e['reason'],'below_min_notional')
        self.assertEqual(cash,100)

    def test_fee_drags_profit(self):
        cfg=Costs(spread=0,slippage=0,min_order_usd=1)
        cash,qty,e=execute(side='buy',mid=100,cash=100,qty=0,notional=95,cfg=cfg,rng=random.Random(1))
        cash,qty,e=execute(side='sell',mid=100,cash=cash,qty=qty,notional=200,cfg=cfg,rng=random.Random(2))
        self.assertLess(cash,100)

    def test_no_future_knowledge(self):
        s=candidates(1)[0];bars=deepcopy(self.market[s.asset])
        r1=backtest(s,bars,210,300)
        for x in bars[300:]:x['c']*=10
        r2=backtest(s,bars,210,300)
        self.assertEqual(r1['curve'],r2['curve'])
        self.assertEqual(r1['fills'],r2['fills'])

    def test_audit_detects_mutation(self):
        e=[];event_append(e,'order',{'side':'buy'},1700000000)
        self.assertTrue(verify_chain(e))
        e[0]['data']['side']='sell'
        with self.assertRaises(ValueError):verify_chain(e)

    def test_holm_correction(self):
        corrected=holm_pvalues([('a',.01),('b',.02),('c',.8)])
        self.assertAlmostEqual(corrected['a'],.03)
        self.assertGreaterEqual(corrected['b'],.03)

    def test_research_selection_and_incubator_frozen(self):
        subset={k:v[:410] for k,v in self.market.items()}
        research=evaluate(subset,12)
        self.assertEqual(len(research['agents']),12)
        proposals=propose(research,8)
        self.assertGreater(len(proposals),0)
        self.assertTrue(all(p['id'] not in {a['id'] for a in research['agents']} for p in proposals))

    def test_forward_no_duplication_and_shared_capital(self):
        study={k:v[:410] for k,v in self.market.items()}
        research=evaluate(study,12)
        book=make_book(research,self.market,120,1.2)
        advance(book,research,self.market,410)
        self.assertEqual(book['meta']['forward_days'],1)
        with self.assertRaises(ValueError):advance(book,research,self.market,410)
        self.assertGreaterEqual(book['shared']['cash'],0)
        self.assertTrue(verify_chain(book['audit']))
        self.assertEqual(len(make_public_state(research,book)['agents']),12)

    def test_real_quote_forward_has_no_backdated_fill(self):
        study={k:v[:410] for k,v in self.market.items()}
        research=evaluate(study,12)
        book=make_book(research,study,120,1.2,dataset='REAL PRICE / VIRTUAL MONEY')
        book['meta']['last_bar']=study['BTC'][-2]['t']
        now=int(time.time())
        quotes={k:{'bid':v[-1]['c']*.999,'ask':v[-1]['c']*1.001,'at':now} for k,v in study.items()}
        # Synthetic dataset is already historical so latest bar is complete.
        advance_at_quotes(book,research,study,quotes)
        self.assertEqual(book['meta']['last_bar'],study['BTC'][-1]['t'])
        self.assertEqual(book['meta']['forward_days'],1)
        with self.assertRaises(ValueError):advance_at_quotes(book,research,study,quotes)
        quotes['BTC']['at']-=3600
        with self.assertRaises(ValueError):advance_at_quotes(book,research,study,quotes)

    def test_observe_public_quotes_does_not_invent_trades(self):
        study={k:v[:410] for k,v in self.market.items()}
        research=evaluate(study,9)
        book=make_book(research,study,120,1.2,dataset='REAL PRICE / VIRTUAL MONEY')
        book['meta']['last_bar']=study['BTC'][-1]['t']
        now=int(time.time())
        quotes={k:{'bid':v[-1]['c']*.999,'ask':v[-1]['c']*1.001,'at':now} for k,v in study.items()}
        before=deepcopy(book)
        observe_quotes(book,research,quotes)
        self.assertEqual(book['meta']['forward_days'],0)
        self.assertEqual(len(book['audit']),0)
        self.assertEqual(book['shared']['trades'],0)
        self.assertEqual(book['shared']['curve'],before['shared']['curve'])
        self.assertEqual(book['meta']['quote_at'],now)
        self.assertEqual(book['meta']['last_bar'],before['meta']['last_bar'])
        quotes['ETH']['at']-=300
        with self.assertRaises(ValueError):observe_quotes(book,research,quotes)

    def test_cloud_skips_missed_days_without_backdated_orders(self):
        from unittest.mock import patch
        import project_ten.__main__ as main
        subset={k:v[:410] for k,v in self.market.items()}
        research=evaluate(subset,9)
        book=make_book(research,subset,120,1.2,dataset='KRAKEN REAL PRICES / VIRTUAL MONEY')
        book['meta']['last_bar']=subset['BTC'][-4]['t']
        now=int(time.time())
        quotes={k:{'bid':v[-1]['c']*.999,'ask':v[-1]['c']*1.001,'at':now}
                for k,v in subset.items()}
        with patch.object(main,'load_book',return_value=book), \
             patch.object(main,'load_json',return_value=research), \
             patch.object(main,'load_csv',side_effect=lambda path:subset[path.stem]), \
             patch.object(main,'ticker',side_effect=lambda asset:quotes[asset]), \
             patch.object(main,'save_book'), patch.object(main,'_save_reports'):
            main.cmd_run(None)
        self.assertEqual(book['meta']['skipped_days'],2)
        self.assertEqual(book['meta']['forward_days'],1)
        self.assertEqual(book['meta']['last_bar'],subset['BTC'][-1]['t'])
        self.assertEqual(sum(e['kind']=='missed_market_sessions' for e in book['audit']),1)
        self.assertTrue(verify_chain(book['audit']))

    def test_live_first_run_preserves_demo_and_second_run_is_idempotent(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import project_ten.__main__ as main
        import project_ten.storage as storage
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state';data=Path(folder)/'data';reports=Path(folder)/'reports'
            state.mkdir()
            # A minimal preserved synthetic book, with an intact audit trail.
            original={'meta':{'mode':'SYNTHETIC DEMO'},'audit':[]}
            storage.save_json(state/'book.json',original)
            storage.save_json(state/'research.json',{'agents':[]})
            study={k:v[:410] for k,v in self.market.items()}
            research=evaluate(study,9)
            now=int(time.time())
            quotes={k:{'bid':v[-1]['c']*.999,'ask':v[-1]['c']*1.001,'at':now} for k,v in study.items()}
            sync_calls=[];run_calls=[]
            def fake_sync(args):sync_calls.append(True)
            def fake_init(args):
                book=make_book(research,study,120,1.2,dataset='KRAKEN REAL PRICES / VIRTUAL MONEY')
                book['meta']['last_bar']=study['BTC'][-1]['t']
                storage.save_json(state/'research.json',research)
                storage.save_book(book)
            with patch.object(storage,'STATE',state),patch.object(main,'STATE',state),\
                 patch.object(main,'cmd_sync',fake_sync),patch.object(main,'cmd_init',fake_init),\
                 patch.object(main,'ticker',side_effect=lambda a:quotes[a]),\
                 patch.object(main,'_save_reports',lambda r,b:None),\
                 patch.object(main,'cmd_run',lambda args:run_calls.append(True)):
                main.cmd_live(None)
                started=storage.load_book()
                self.assertEqual(started['meta']['forward_days'],0)
                self.assertEqual(started['shared']['trades'],0)
                self.assertEqual(started['meta']['quote_at'],now)
                self.assertEqual(storage.load_json(state/'synthetic-demo-backup'/'book.json'),original)
                main.cmd_live(None)
            self.assertEqual(len(sync_calls),2)
            self.assertEqual(len(run_calls),1)


if __name__=='__main__':unittest.main()
