# Cloud deployment

Repository: https://github.com/mayootomic-maker/project-ten
Dashboard: https://mayootomic-maker.github.io/project-ten/

GitHub Pages source: GitHub Actions. Workflow `virtual-market-daily.yml` requests monitoring runs every five minutes (minutes 2, 7, 12, …, 57 UTC). It runs all tests, fetches real public feeds, updates paired research/trading workers, verifies accounting and report consistency, commits persistent ledgers, and deploys the Pages artifact. The workflow concurrency group serializes all writers.

Real-money execution is disabled. Futures and unverified DEX executions are blocked. Ten futures trading partners remain in cash while their research workers collect observations. See PAIRED_SYSTEM.md for remaining coverage and runtime limits.

State and reports from the old experiment remain untouched; `docs/legacy/` is its frozen dashboard. New paired portfolios start separately at CHF 100 each.


## Speed and research upgrade (2026-10-12)

Bulk quotes replace repeated per-pair requests. Pair metadata is cached for one hour; completed histories are reused only when they contain the latest expected closed candle. New candles extend stored history up to 2,000 rows per instrument/timeframe, and provider revisions fail closed. Heavy research is reused for unchanged candles and validation versions. Pipeline phase durations appear in the report. The visible dashboard refreshes its published snapshot every minute; it does not manufacture streaming fills.

Candidates now need at least three training entries, five holdout entries, positive net return and doubled-cost stress performance, and positive results in at least two of three later subwindows. These remain overlapping exploratory tests, not proof of an edge.

Prospective learning records signal-qualified shadow opportunities before their outcomes are known. Only later received quotes grade fixed four-candle outcomes after fees, spread and slippage. Same-instrument/policy opportunities do not overlap. Very late observations are excluded from calibration. These diagnostics never change portfolio balances or trade counts. With fewer than 20 usable observations they cannot influence asset ranking; beyond that, negative exploratory calibration can conservatively penalize a candidate. There is no guaranteed statistical independence, no positive promotion from shadow profits, and no LLM or news research.
