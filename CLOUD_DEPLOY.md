# Cloud deployment

Repository: https://github.com/mayootomic-maker/project-ten
Dashboard: https://mayootomic-maker.github.io/project-ten/

GitHub Pages source: GitHub Actions. Workflow `virtual-market-daily.yml` requests hourly runs at minute 17 UTC. It runs all tests, fetches real public feeds, updates paired research/trading workers, verifies accounting and report consistency, commits persistent ledgers, and deploys the Pages artifact. The workflow concurrency group serializes all writers.

Real-money execution is disabled. Futures and unverified DEX executions are blocked. Ten futures trading partners remain in cash while their research workers collect observations. See PAIRED_SYSTEM.md for remaining coverage and runtime limits.

State and reports from the old experiment remain untouched; `docs/legacy/` is its frozen dashboard. New paired portfolios start separately at CHF 100 each.
