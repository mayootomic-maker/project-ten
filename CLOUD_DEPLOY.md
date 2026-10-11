# PROJECT TEN — CLOUD DEPLOYMENT

## Deployment outcome

- Public Kraken spot market data for BTC/USD, ETH/USD, SOL/USD.
- 100 distinct virtual agent accounts (CHF 100-equivalent each), plus one **shared CHF 100 virtual portfolio**. These are separate experiments, not CHF 10,000 of actual capital.
- Virtual fees and modeled spread/slippage. Never submits exchange or brokerage orders.
- Free GitHub Actions schedule: **every four hours at minute 29 UTC**, subject to GitHub's scheduler reliability.
- Agent strategies evaluate **once per completed UTC daily candle**, not every four hours.
- Public, phone-friendly GitHub Pages site with individual agent details. Data freshness, missed days and paper-only execution are indicated.
- Persistent JSON ledger committed back into the repository. Missed days are logged and skipped; no retroactive fills.

## Start from Android (no PC required)

1. Open <https://github.com/new> in a mobile browser and sign in.
2. Name the new repository **`project-ten-cloud`** (or another unused name). Choose **Public** if you want a free phone-accessible GitHub Pages site. Everything published in the project and dashboard is readable by anyone. **Never store passwords, tokens or private financial details in it.** Check **Add a README** and click **Create repository**.
3. Return to this ChatGPT conversation and provide the new repository URL. The connected GitHub app can be used to add the project's source files. If connected GitHub permissions do not cover this newly created repo, update the app's repository access via GitHub Settings.
4. After the project files are committed, open your new repository: **Settings → Pages → Build and deployment → Source → GitHub Actions**. (GitHub Free Pages requires a public repository.)
5. Open **Actions → Project Ten | cloud paper research → Run workflow** and select the default branch. The first successful run must download Kraken prices, initialize research without synthetic demo trades, save the ledger and deploy the dashboard.
6. In the same workflow run, open the **dashboard** deployment link, or visit `https://YOUR-USERNAME.github.io/project-ten-cloud/` (change the owner/repository if different). Bookmark it on Android.

### Alternative when the PC becomes available

Extract the clean cloud ZIP, create a new Git repository inside it and push it to the *new* empty GitHub repository. Never replace an unrelated existing repository. Then complete steps 4–6 above. Do not upload the old ZIP as one GitHub file; GitHub Actions must see each source file and the hidden `.github/workflows/` folder.

## Expected first-run behavior

1. Run Python unit tests and stop if any fail.
2. Fetch OHLC history and bid/ask from unauthenticated Kraken public API, plus an indicative CHF/USD FX reference.
3. Screen 100 fixed strategies on historical periods and create fresh simulated balances. **No past trades are falsely presented as live results.**
4. Save state, agent status, audit and dashboard JSON to repository.
5. Deploy the static dashboard as a Pages artifact. The first run normally displays **zero forward trades** until at least one new completed daily candle is available.

If the market-data API or workflow fails, no new quote or trade is fabricated. Check the Actions run log; the public dashboard warns when prices are stale. An occasional missed run is skipped, not replayed against fake past prices.

## Limits

- This is a research prototype, not a verified profitable strategy or real order execution.
- The model uses a frozen reference FX rate and assumed slippage, and doesn't model taxes, available exchange depth, every minimum lot size, or exact execution impact.
- GitHub Actions is not real-time infrastructure: triggers may be delayed or missed.
- The dashboard is public on a free public repo, even if its URLs aren't shared with others.
- GitHub Actions free-tier usage and limits can change. The scheduled workload is designed to be relatively lightweight, but no unconditional lifetime-free guarantee exists.

## Technical commands

```
python -m unittest discover -s tests -q
python -m project_ten live
python -m project_ten audit
python -m project_ten publish
```

No exchange API keys, brokerage access, or trading permissions are required. The whole cloud system is **paper-only**.
