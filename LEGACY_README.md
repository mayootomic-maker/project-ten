# Deployed Project Ten

Dashboard: https://mayootomic-maker.github.io/project-ten/

Cloud workflow: https://github.com/mayootomic-maker/project-ten/actions/workflows/virtual-market-daily.yml

Two manual cloud executions passed on 2026-10-11, including real-price acquisition, 16 tests, state validation, ledger persistence, and Pages publishing. Automatic schedule: 00:29, 04:29, 08:29, 12:29, 16:29, 20:29 UTC. Schedules can be delayed; no claim of uninterrupted execution is made. All 100 strategies use independent simulated CHF 100 portfolios. Decisions run once per completed daily candle. No broker credentials or real-money order endpoints exist.

---

# PROJECT TEN / AGENT COMMAND

**A working, open-source-style research simulator with 100 identifiable agents.**

**100% paper-only. No exchange/broker API credentials, no real-money order capability.** Python standard library only, so there is nothing to `pip install`. Runs with Python 3.10+ on Windows, Linux and macOS. Designed to be browsed on a phone or computer.

## Quick start — 60 seconds

This deployment starts with real Kraken price data and simulated money. No synthetic performance is published. The optional `demo` command is for local tests only and produces explicitly synthetic results.

1. Extract the entire ZIP. Do not try to run it inside ZIP preview software.
2. On Windows, double-click **`Start-ProjectTen-Windows.bat`**. On Mac/Linux, open a terminal in the extracted folder and run `python3 -m project_ten serve`.
3. Open **http://127.0.0.1:8765** in a browser on the same computer. Click **Agents**, browse 100 named avatars, inspect decisions, fees, trades, and historical screening. **Laboratory** shows testing methods and quarantined research proposals.
4. To regenerate the synthetic demo later: `python -m project_ten demo --force` (overwrites current virtual state).

## START LIVE PAPER TRADING (real prices, zero real money)

**Recommended starting point:** On Windows, double-click `Start-Live-Paper-Windows.bat`; on Mac/Linux, run `sh Start-Live-Paper-Mac-Linux.sh`. These launch an **hourly market-data check** and the dashboard; keep that computer powered on and the terminal open. Or use:

```bash
python -m project_ten watch
```

For a **single market evaluation** (for example, in a scheduled cloud job), run `python -m project_ten live`. Use `python -m project_ten serve` separately to browse the latest saved results.

`live` automatically downloads current public Kraken daily history and current bid/ask quotes. On its **first run**, it screens 100 agents, and opens **100 independent CHF 100-equivalent virtual accounts** plus **one shared CHF 100-equivalent portfolio**. All balances start at CHF 100, with **zero claimed forward trades**. It does not retroactively execute historical orders. On the *next completed daily candle* (and only when the command executes), all 100 independent agents can make a modeled buy/sell (qualification gates apply to the separate shared portfolio) at the then-current public bid/ask, charging simulated fees/slippage. Run `live` daily or install the included GitHub Actions schedule (six quote checks per day). When there is no new completed bar, `live` refreshes current marks and does **not** create duplicate trades.

The dashboard automatically refreshes its local or published JSON every 90 seconds, but the cloud data source updates only when the GitHub workflow or local command actually runs. A fresh website **does not imply** continuous trading or second-by-second quotes. Mode, last observed quote time and number of forward evaluations are displayed explicitly.

**Cannot be launched continuously from this chat:** the local runtime cannot reach Kraken, and no GitHub repository has been deployed. Internet access is needed when you execute `live` on a computer/GitHub-hosted runner. This package does not touch real money or broker credentials. It also cannot turn an underage account into a live exchange account.

**GitHub cloud activation:** Make a private repository, upload the extracted project *including the `.github` hidden folder*, enable Actions write permissions, and run the `Project Ten — daily virtual research` workflow once manually from Actions. It self-initializes with fresh public prices and starts a real-price paper ledger. Afterwards the cloud checks every four hours (00:29, 04:29, 08:29, 12:29, 16:29 and 20:29 UTC), with **at most one new strategy decision per completed daily bar**. Pages is deployed explicitly by Actions rather than relying on a push-triggered build. Missed evaluations are logged and skipped, never replayed as hindsight fills. A public Pages website exposes your research results to everyone.

### Replace the demo with REAL public price history

In a terminal inside the project folder:

```bash
python -m project_ten sync
python -m project_ten init --force
python -m project_ten serve
```

- `sync` downloads completed **Kraken BTC/USD, ETH/USD, SOL/USD daily candles** and public Kraken best bid/ask snapshots, plus a **reference CHF/USD** rate from Frankfurter for initial CHF 100 → USD conversion. **No account or trading access is required.**
- `init --force` builds a new **frozen** 100-agent research snapshot, applies a training / holdout split, three chronological training subwindow checks, a doubled-cost failure-stress run, and initializes all virtual accounts. It intentionally begins with **zero forward trades**. This prevents fake forward results and data snooping.
- Each agent has a personal CHF 100 equivalent **virtual account**. The single **shared CHF 100 equivalent virtual portfolio** may allocate to up to three independently qualified strategies, one per asset. The 100 personal virtual balances are independent experiments and are **not** a combined CHF 10,000 bank account.
- Future trading is simulated **only when a new daily candle is complete**, using publicly observed bid/ask prices **at the moment the next evaluation actually runs**. No hindsight fills at yesterday's opening price are allowed.
- After initialization, run `python -m project_ten sync` followed by `python -m project_ten run` on subsequent days. Run `python -m project_ten audit` to verify the hash-linked log. The system rejects duplicate days and stops if it missed more than one full daily processing interval.

**Honest accounting limitations:** This is a conservative *model*, not an exchange execution emulator. It does not know queue position, actual available depth, price impact, maker queue, exchange-specific minimum quantity rules, deposit/withdrawal fees, FX conversion execution fees, or taxes. It uses a frozen reference conversion rate, not daily CHF FX P&L. Signals are calculated from completed bars. A forward quote-based fill is a modeled fill, **not a real confirmed exchange or Alpaca paper fill**. Explicit additional fees/slippage are charged, but economic realism can never be guaranteed.

## Interface

- **Overview:** Shared account balance, net P/L, maximum drawdown, capital allocation, screening pipeline, featured agents, recent shared actions.
- **Agents:** Search, sort and filter 100 distinct named / numbered agent identities with consistent family emblems and individual geometric sigils.
- **Agent detail:** Plain-language numerical explanation of the latest signal, current virtual holdings, independent profit/loss, fee total, maximum drawdown, trade history and historical train/holdout/stress results.
- **Laboratory:** Reject/qualify decisions, known modeling assumptions, asset benchmark results and **12 quarantined strategy proposals** generated from training history only. Proposed strategies are **never silently deployed**.
- **Journal:** Model execution records, rejected attempts, and CSV export. `python -m project_ten audit` independently checks chain consistency.

The UI uses no external fonts, JavaScript libraries or CDNs. Static HTML/CSS/JS only, responsive on desktop and mobile. Black-and-white design with unique emblems, **no random AI-generated avatars**.

## What the 100 agents really are

There are six rule families across three assets and multiple parameters: SMA trend, channel-based entry, momentum, RSI reversal, Z-score reversion and volatility-filtered trend. Each runs **long or cash**, **without leverage or short selling**. These are candidate hypotheses, not trained AI models, and are not claimed to make money.

Research selection: initial training with three chronological subwindow checks → later holdout screening → 2x-cost stress veto → no more than one candidate per asset → forward-only simulated portfolio. Candidate overfitting is still a risk because testing many possibilities can produce random winners. A historical test does not establish predictive skill. The model estimates statistical uncertainty with an approximate HAC test and Holm correction on the training period, but this is exploratory, not a profitability guarantee.

The **research incubator** generates 12 proposed parameter changes based solely on training results. They stay visibly *untested* rather than self-promoting. No LLM is required or secretly monitoring the market.

## Execution costs and safety defaults

| Assumption | Model default |
| --- | ---: |
| Exchange fee (taker, per side) | 0.80% (conservative configured assumption, not a verified current venue tier) |
| Additional bid-ask spread (total) | 0.10%, **assumed** for historical replay |
| Extra slippage (each side) | 0.05%, **assumed** |
| Conservative minimum notional | USD 10.00, **not** a claim of venue minimum |
| Virtual initial shared capital | CHF 100 (converted once at reference FX) |
| Stress test | 2x fees, spread and slippage, random partial fills and rejects |
| Drawdown entry freeze | 25% from local peak; **not a stop-loss execution guarantee** |
| Shared exposure per asset | Up to ~28% of available equity when buying |
| Real-money order access | None, by design |

On forward runs the public bid/ask already contains the spread; **the code does not apply the modeled spread a second time**. On historical backtests only, the fixed spread assumption is used. Minimum order and lot-step parameters are *configurable model simplifications*; verify actual exchange rules separately.

## Optional: free unattended cloud execution + phone dashboard

A GitHub Actions workflow is included under `.github/workflows/virtual-market-daily.yml`.

1. Create a **private GitHub repository** and upload the project contents. Do not put passwords, keys, or funds in it.
2. Do not upload synthetic demo `state/` or `reports/` into the cloud repository. Use the clean **ProjectTen-Cloud-Deploy.zip** package; the workflow initializes real-price simulation on its first execution.
3. In your repository settings, enable Actions and allow workflow write permissions. The included workflow runs every **four hours at minute 29 UTC**, performs self-tests, updates public prices, evaluates agents at most once per completed daily bar, deploys a static dashboard through GitHub Actions, and commits the new state.
4. GitHub Actions **can be delayed or skipped**, and this app intentionally stops if it missed multiple days rather than forge historical fills. To keep a durable audit record, keep repository contents/state across runs and ensure no concurrent processing.
5. To access the dashboard on your phone for free, create a **public repository**, then select **Settings → Pages → Build and deployment → Source: GitHub Actions**. The workflow explicitly uploads and deploys the website; do not select a `/docs` branch source. `python -m project_ten publish` builds the static site in `docs/`. **Anyone can then see your research data**. If you prefer a private repository, use the repository files or run the local dashboard. Check GitHub's current Pages plan rules before choosing privacy.

These steps are **not automatically performed by downloading the ZIP**. The package contains a working local app and an optional cloud workflow, but no GitHub repository or cloud deployment has been created on your behalf.

## Developer / verification

```bash
python -m unittest discover -s tests -v
python -m project_ten audit
python -m project_ten report
python -m project_ten publish
```

Code layout: `project_ten/data.py` verifies incoming OHLC; `strategies.py` defines interpretable agents; `engine.py` simulates fees and risk; `research.py` screens without holdout parameter tuning; `portfolio.py` tracks 100 personal virtual accounts plus central capital; `incubator.py` proposes quarantined research; `storage.py` writes atomic state and verifies the audit chain; `app.py` serves the local read-only dashboard; `web/` contains the interface; `tests/` contains reproducible invariants.

### Official sources

- [Kraken Pro spot fees](https://www.kraken.com/features/fee-schedule) (consult current rates; this experiment uses a configured conservative fee assumption)
- [Kraken historical OHLC dataset](https://support.kraken.com/in/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data) (REST OHLC contains limited lookback; complete historical CSV files are provided separately)
- [Alpaca paper trading limitations](https://docs.alpaca.markets/us/v1.4.2/docs/paper-trading) (market impact, latency and order queue not fully represented)
- [GitHub scheduled workflow limitations](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows)

## Reality check

The dashboard is production-minded UI, but the research system is a **testable prototype**. It is not a production trading engine, has no verified live exchange fills, offers no profitability promise, and deliberately cannot submit real orders. The synthetic preview may show large individual returns because its price series are invented. **Never confuse that preview with evidence of a market edge.**

## Open on Android immediately (no Python required)

**`ProjectTen-Offline-Dashboard.html`** is a complete **offline, self-contained demonstration snapshot**. Open it with a browser or HTML viewer on Android or Windows. All 100 agents, charts, journal filters and profiles work without an internet connection. It contains the explicitly labeled synthetic demo, not current market prices. To refresh a snapshot after real-price runs, execute:

```bash
python -m project_ten export-offline
```

This generates a new fully self-contained HTML at the project root. To see ongoing updates without manually transferring HTML, configure the optional scheduled GitHub Pages site.

