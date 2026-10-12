# Project Ten: 50 research/trading pairs

## Running scope

50 independent CHF 100 paper portfolios; each has a research worker and a trading worker. These are deterministic price/volume research pipelines, not 100 LLMs. No model API charges, no credentials and no live order endpoints.

Five desks × ten hypotheses: major crypto hourly, major crypto four-hour, liquid altcoins hourly, exchange-listed meme coins hourly, and futures research. Spot researchers compare several eligible instruments. The named hypotheses are moving-average trend, EMA trend, channel breakout, RSI reversal, volatility-band reversion, momentum, volume-confirmed breakout, trend pullback, compression breakout, and range bounce. No claim to know all strategies or outperform another system.

The requested schedule is hourly at minute 17 UTC. GitHub may delay, skip or disable schedules. Stops and targets are observed only when the job runs; they are not resting venue orders. No guaranteed 24/7 uptime, real-time monitoring, or guaranteed loss limit.

## Research to execution

Research ranks assets on chronological training performance only. The highest training candidate is frozen for seven days; a subsequent holdout and doubled-cost test may veto it. The researcher cannot search the holdout winners for a replacement. All candidate evidence is retained in the report. These are exploratory, repeated tests, not proof of an edge. Limited histories, survivorship and selection bias remain material limitations.

The trader waits for a new completed hourly/four-hour candle after initialization. No past signals are replayed as profitable forward trades. New quotes are fetched after research. Stale data, broad spreads, insufficient liquidity, failed validation, venue minimums and insufficient simulated cash reject an entry. Each order includes its account, price, fee and reason.

Position sizing uses a 1% equity risk budget, at most 25% exposure (10% on listed memes). ATR sizes stop/target distances but is not a prediction of future returns. Observed 10% drawdown freezes new entries. Estimated risk can be exceeded by gaps, missed jobs and failed exit restrictions.

## Cost and result accounting

The configured fee remains 0.8% per side; it is a conservative assumption rather than a verified current account fee tier. Current public bid/ask replaces assumed spread for forward orders, with additional assumed 0.05% slippage per side. Quantity precision and minimum quantity/notional use Kraken pair metadata plus a configured USD 10 floor.

Current equity = initial capital + realized/unrealized market movement − paid fees − modeled spread/slippage impact. Estimated liquidation costs are reported separately. FX is a frozen reference, not an executable conversion. Screening returns and actual forward paper returns appear separately. Cash is a valid outcome.

## Explicitly blocked or absent

- Ten futures pairs collect live perpetual-contract liquidity, funding indicators, open interest and basis, but cannot execute. Historical funding settlement, contract-specific leverage/margin/liquidation, derivatives candle research and execution simulation must be validated first. Their trading portfolios remain in cash.
- DEX meme coins cannot execute. Contract permissions, holder concentration, sellability, pool reserves, taxes/gas/MEV and liquidity-removal risks are unverified. Exchange-listed meme coins are not claimed to be safe; listing is not a rug-pull guarantee.
- No unattended LLM research, news/sentiment interpretation, options, stocks, bonds, FX trading, hedged arbitrage or proven cross-market allocation.
- The curated universe is not comprehensive and the hypotheses are not expert AI traders. More trades are not the success criterion.

## Persistence and migration

Original V1 state and reports remain untouched and its dashboard is frozen at `docs/legacy/`. The old experiment is paused. V2 starts new, separately timestamped ledgers in `state/paired_book.json`. Original losses are never overwritten, reclassified or included in new performance. Data, research snapshots, audit chain and output reports are committed by the single serialized workflow. No demo generation is invoked by the cloud workflow.

## Sources

- https://docs.kraken.com/api-reference/market-data/get-tickers
- https://docs.kraken.com/api-reference/instrument-details/get-instruments
- https://docs.kraken.com/api/docs/rest-api/get-tradable-asset-pairs
- https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.dexscreener.com/api/reference
