# Research: responsiveness, learning and credible trading evidence

Checked 2026-10-12. Conclusions below distinguish source findings from implementation choices. No claim that this system is highly intelligent or profitable has been established.

## What was actually slow

The latest scheduled run available during this audit began at 06:12:53 UTC, while the audit occurred after 12:36 UTC. The workflow remained active. The dashboard's last observation was from a manual run at 08:24:20 UTC. Thus the large delay was in scheduling/observations, not proof that Python calculations took hours. Requested cadence and achieved cadence must be shown separately. The exact cause of missing GitHub schedule events is not proven.

GitHub documents a five-minute minimum scheduled interval, delays under load, and possible dropped events. Implementation: request monitoring at minutes 2, 7, 12, …, 57, serialize writers, and report timestamp age and processing durations. This does not guarantee five-minute response or continuous uptime. The Pages custom-workflow build exemption allows this cadence, while platform quotas and rate limits still apply.

Sources:
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits

## Why more trading is not an intelligence upgrade

Bysik and Ślepaczuk's 2026 preprint evaluates hourly BTC/USDT forecasting with roughly 70,000 observations and 27 walk-forward folds. It reports that naive sign-based strategies fail after transaction costs, whereas cost-aware filters improve selected configurations. Model advantages are not uniformly statistically established. This is evidence to test cost-aware execution, not proof that copying the reported models or adding more trades will make our portfolios profitable. We have not replicated their experiments or implemented their XGBoost/LSTM/iTransformer models.

The official Kraken schedule currently lists a 0.80% spot taker fee at Tier 1. Our 0.8% per-side configuration therefore remains; actual account/pair promotions or later schedules could differ. Fees alone make a buy/sell round trip roughly 1.6% of notional before spread/slippage. A small predicted move can be economically useless. Candle range/ATR is a sizing input, not an expected-profit forecast.

Sources:
- https://arxiv.org/html/2606.00060v1
- https://www.kraken.com/features/fee-schedule

## Why a profitable holdout is not enough

Bailey, Borwein, López de Prado and Zhu analyze backtest overfitting and why selecting among many trials undermines simple holdout interpretation. Project Ten repeatedly screens overlapping windows and many hypotheses. Therefore its holdouts remain exploratory rather than independent evidence of an edge. No probability-of-backtest-overfitting estimator or full CSCV replication is implemented here.

Implementation choices, not thresholds supplied by that paper: require three training entries, five holdout entries, two positive later subwindows out of three, positive doubled-cost stress result, and drawdown constraints. Thresholds are preliminary engineering gates, not statistically calibrated confidence guarantees. Historical screening now includes risk sizing, exposure caps, venue floors and open-observed stops/targets. It still lacks intrabar execution reconstruction and historical venue/spread changes.

Source: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf

## Implemented responsiveness and actual statistical learning

- Bulk quote requests and hourly metadata caching reduce redundant requests.
- Candle histories are reused only when they include the latest expected completed candle. New history is merged and retained up to 2,000 rows per instrument/timeframe. Revisions fail closed.
- Historical research is cached for unchanged candles, policy and validation versions. Quotes and risk checks refresh each run.
- Pipeline fetch/research/quote-refresh durations are measured rather than guessed.
- Each spot pair records eligible shadow proposals before outcomes are known. Four-candle outcomes use the actual later quote after modeled costs, never a manufactured past fill. Same-instrument/policy proposals do not overlap. Excessively late observations are excluded from calibration.
- Shadow outcomes are diagnostics, never portfolio profits or trade counts. Fewer than 20 usable policy/instrument-specific outcomes cannot affect ranking. Afterwards, negative exploratory calibration can penalize a candidate; it cannot bypass validation or promote hypothetical profits into actual returns.
- Samples across markets/time remain dependent. The exploratory lower bound is not a formal independent-sample confidence guarantee. No learned edge exists until forward data support it.

## Free-hosting reality and remaining work

Cloudflare's free Workers limits currently include 10 ms of CPU per request/cron invocation, so it is not a drop-in replacement for our Python research job. We did not provision a Cloudflare account or external timer. GitHub Pages remains a static report, refreshed in the visible browser every minute. Futures executions and unverified DEX tokens remain blocked; no unattended LLM/web/news research has been added.

Next research milestones: longer retained histories, cash/equal-exposure buy-and-hold and risk-matched benchmarks, regime coverage, model calibration and drift tests, block-bootstrap uncertainty, stronger multiple-testing controls, realistic derivatives funding/liquidation simulation, and execution-depth data. These are not claimed as completed. Faster simulated activity or a higher backtest score alone would not establish success.

Source: https://developers.cloudflare.com/workers/platform/limits/
