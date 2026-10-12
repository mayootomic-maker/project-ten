import unittest
from unittest.mock import patch
from copy import deepcopy
from project_ten.paired import create_book
from project_ten.paired_learning import learn, summary, rank_adjustment
from project_ten.paired_feeds import fetch_spot_one, refresh_quotes
from project_ten.paired_signals import evaluate
from test_paired import market, snapshot

class SpeedLearningTests(unittest.TestCase):
    def setUp(self):
        self.now=2000001600
        self.m=market(self.now);self.s=snapshot(self.m,self.now)
        self.a=create_book({'rate':1.2},self.now)['accounts']['DUO-001']
        self.a['research']={'selected':{'instrument':'X'}}

    def test_record_precedes_outcome_and_never_changes_portfolio(self):
        cash=self.a['cash']
        learn(self.a,self.s,self.now)
        self.assertEqual(len(self.a['learning']['pending']),1)
        self.assertEqual(summary(self.a)['samples'],0)
        self.assertEqual(self.a['orders'],0);self.assertEqual(self.a['cash'],cash)
        due=self.now+4*3600
        self.m['quote_at']=due;self.m['bid']*=1.05;self.m['ask']*=1.05
        learn(self.a,self.s,due)
        self.assertEqual(summary(self.a)['samples'],1)
        self.assertGreater(summary(self.a)['mean_shadow_net_pct'],0)
        self.assertEqual(self.a['orders'],0);self.assertEqual(self.a['cash'],cash)

    def test_no_duplicate_or_overlapping_shadow_entries(self):
        learn(self.a,self.s,self.now)
        learn(self.a,self.s,self.now)
        self.m['bars'][-1]['t']+=3600;self.m['quote_at']+=3600
        learn(self.a,self.s,self.now+3600)
        self.assertEqual(len(self.a['learning']['pending']),1)

    def test_future_quote_and_late_exit_cannot_train_calibration(self):
        learn(self.a,self.s,self.now)
        due=self.now+4*3600
        learn(self.a,self.s,due-1)
        self.assertEqual(summary(self.a)['samples'],0)
        self.m['quote_at']=due+7200
        learn(self.a,self.s,due+7200)
        self.assertEqual(summary(self.a)['samples'],0)
        self.assertEqual(summary(self.a)['late_outcomes'],1)

    def test_small_samples_never_change_ranking(self):
        learn(self.a,self.s,self.now)
        self.assertEqual(rank_adjustment(self.a,'X'),0)

    def test_bulk_quote_refresh_uses_one_request_and_updates_all_timeframes(self):
        m2=deepcopy(self.m);m2['id']='X@240';self.s['spot'][m2['id']]=m2
        row={'b':['200'],'a':['201']}
        with patch('project_ten.paired_feeds.kraken',return_value={'XUSD':row}) as call:
            refresh_quotes(self.s)
        call.assert_called_once()
        self.assertEqual(self.s['spot']['X']['bid'],200)
        self.assertEqual(self.s['spot']['X@240']['ask'],201)

    def test_history_cache_skips_network_only_for_latest_complete_candle(self):
        spec={'wsname':'XBT/USD','lot_decimals':8,'ordermin':'.0001','costmin':'.5','status':'online'}
        tick={'b':['199.7'],'a':['199.8'],'v':[0,10000],'p':[0,200]}
        with patch('project_ten.paired_feeds.kraken') as request:
            data=fetch_spot_one('X',spec,tick,self.now,60,self.m)
        request.assert_not_called();self.assertEqual(data['bars'],self.m['bars'])

    def test_more_than_one_lucky_holdout_entry_required(self):
        e=evaluate('sma_trend',self.m['bars'],self.a['policy'])
        self.assertFalse(e['qualified'])
        self.assertEqual(len(e['validation_folds']),3)
        self.assertEqual(e['validation_version'],3)

    def test_future_dated_quote_cannot_create_learning_evidence(self):
        self.m['quote_at']=self.now+1
        learn(self.a,self.s,self.now)
        self.assertEqual(summary(self.a)['pending'],0)

    def test_learning_penalty_requires_mature_instrument_specific_evidence(self):
        learn(self.a,self.s,self.now)
        memory=self.a['learning'];policy=self.a['policy']['fingerprint']
        memory['completed']=[{'policy':policy,'instrument':'X','usable_for_calibration':True,'net_return_pct':-1.} for _ in range(19)]
        self.assertEqual(rank_adjustment(self.a,'X'),0)
        memory['completed'].append({'policy':policy,'instrument':'X','usable_for_calibration':True,'net_return_pct':-1.})
        self.assertLess(rank_adjustment(self.a,'X'),0)
        self.assertEqual(rank_adjustment(self.a,'OTHER'),0)
        self.assertEqual(self.a['orders'],0)

    def test_historical_venue_floor_cannot_create_impossible_fills(self):
        from project_ten.paired_signals import screen
        result=screen('sma_trend',self.m['bars'],130,500,policy=self.a['policy'],
            execution={'capital':120.,'min_qty':1000000.,'qty_step':.01,'min_cost':10})
        self.assertEqual(result['orders'],0)
        self.assertAlmostEqual(result['net_pct'],0)

if __name__=='__main__':unittest.main()
