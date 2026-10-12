# Project Ten · 50 research/trading pairs

[Dashboard](https://mayootomic-maker.github.io/project-ten/) · [Original V1 results](https://mayootomic-maker.github.io/project-ten/legacy/) · [Cloud workflow](https://github.com/mayootomic-maker/project-ten/actions/workflows/virtual-market-daily.yml)

Real public market prices; simulated money only. Fifty research workers and fifty trading workers form fifty independent CHF 100 portfolios. This is a zero-budget deterministic research prototype, not fifty LLM duos or proven trading expertise.

Forty pairs compare assets across major crypto (hourly and four-hour), liquid altcoins, and exchange-listed meme coins. Ten additional pairs observe perpetual futures liquidity, funding indicators, open interest and basis; their executions remain blocked until a funding/margin/liquidation simulator is validated. Unverified DEX tokens cannot trade.

The GitHub schedule requests hourly runs at minute 17 UTC. Jobs may be delayed/skipped; this is not continuous hosting. Each job rescans opportunities using 50 distinct decision policies. Research ranks training evidence, not holdout winners; entry context and maximum holding periods vary by policy. Rolling validation is exploratory and overlaps across runs. Holdout/cost-stress tests can veto a candidate; trading may remain in cash. New account performance starts at its actual creation timestamp.

## Run and verify

Python 3.13, standard library only. No API keys or broker credentials.

```bash
python -m unittest discover -s tests -q
python -m project_ten.paired
python scripts/verify_paired.py
```

State is in `state/paired_book.json`; report and public snapshot in `reports/paired_dashboard.json` and `docs/paired_dashboard.json`. The serialized cloud workflow preserves these in git and publishes `docs/` with GitHub Pages.

See [PAIRED_SYSTEM.md](PAIRED_SYSTEM.md) for hypotheses, accounting, gates, risk limits, blocked coverage, and source documentation. Existing V1 ledgers/reports remain intact; V1 trading is paused. No cloud step generates synthetic demonstrations.
