# Mobile app and continuous hosting

The GitHub Pages dashboard is an installable PWA with a manifest, launcher
icons, standalone display and offline saved verified observations. Install
from Android Chrome: menu → Add to home screen → Install. The App & alerts
tab explains setup. Visible pages check reports every 15 seconds; this is
display polling, not trading frequency.

## Notifications

Subscribe in ntfy Android or ntfy web push to the random channel supplied in
the conversation. Allow phone notifications. NTFY_TOPIC is a GitHub Actions
encrypted secret; it is absent from the public dashboard and repository.
The topic is unlisted, not authenticated: anyone knowing it can read or publish
messages. Keep it private.

The sender verifies the paper ledger chain and sends only recorded paper_buy
and paper_sell events. Messages show pair, side, asset, quantity, modeled
observed price, fee and event time. No rejected proposals, backtests or shadow
outcomes are sent as trades. Activation baselines historical fills. A setup
test explicitly says NO trade was made. Optional workflow_dispatch input
notification_test sends that test.

Accepted event hashes persist in state/notifications.json; failed batches
remain retryable. Delivery is at least once: crashes or git commit failures
after remote acceptance may cause duplicate alerts. Service acceptance is
testable; receipt on your phone requires your subscription and permissions.
Provider quotas and Android battery restrictions can delay delivery.

## Continuous runner: implemented, not deployed

GitHub scheduling is best effort. No continuously running host was provisioned.
Free Render services sleep after inactivity and have ephemeral disk. Free
Hugging Face compute is unsuitable for guaranteed continuous hosting. Oracle
Always Free compute is a candidate, subject to account verification, regional
capacity and idle-resource reclamation. No guaranteed free uptime is promised.
A separate hosting account and server access are still required.

Before activating a VM:

1. Disable GitHub execution. There must be only one writer for portfolios.
2. Import the latest main snapshot with existing data, state, reports and docs.
   Verify its ledger; preserve start times, money, audit and original results.
3. Place the snapshot on durable disk, e.g. /srv/project-ten/ledger. Put
   NTFY_TOPIC in a private environment file, never in git.
4. Build Dockerfile; run with restart unless-stopped, the durable
   /srv/project-ten/ledger:/ledger mount and private environment file. The
   default command polls every 60 seconds and serves docs on port 8080.
5. Provide HTTPS through a reverse proxy before mobile installation. Back up
   the disk. Verify multiple observations, restart recovery and phone receipt.
6. Switch to the verified VM dashboard URL. GitHub Pages is not automatically
   updated by this runner; it remains a frozen fallback without explicit
   mirroring. Do not run both writers on diverging copies of the ledger.

PROJECT_TEN_ROOT selects durable storage. --confirm-sole-runner is required;
missing portfolios are rejected to prevent silent resets. An OS file lock
prevents simultaneous local runners, but cannot coordinate different hosts.
The loop recalculates research for new candles, refreshes observed quotes,
fails closed on data errors, writes runtime_health.json and handles shutdown.
Individual JSON writes are atomic; the group of files is not transactional.
The verified authoritative book is saved first. Copy updated dashboard assets
to the durable docs directory when upgrading the host software.

## Sources checked 2026-10-12

- https://docs.ntfy.sh/publish/
- https://docs.ntfy.sh/subscribe/phone/
- https://render.com/docs/free
- https://huggingface.co/docs/hub/spaces-overview
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
