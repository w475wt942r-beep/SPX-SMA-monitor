# SPX Six-SMA Monitor setup

1. Replace repository files `spx_monitor.py`, `requirements.txt`, and `.github/workflows/main.yml` with those in this package (keep the same paths).
2. Install the **ntfy** iPhone app. Create a long random, unguessable topic name (e.g. a 32-character random string) and subscribe to it. A public ntfy.sh topic is not authenticated: anyone knowing the topic can publish to it. For privacy and stronger authentication use a private ntfy server instead.
3. In GitHub repository **Settings → Secrets and variables → Actions → New repository secret**, create `NTFY_TOPIC` with the exact topic name. Do not put it in your code.
4. In **Settings → Actions → General → Workflow permissions**, allow read and write permissions as needed for the workflow's `issues: write` permission. The workflow uses one GitHub issue as persistent signal state to prevent duplicate alerts. It does not send email or SMS.
5. Under **Actions → SPX Six-SMA Monitor → Run workflow**, test during regular trading hours. Check logs and the ntfy app. Outside market hours it intentionally exits without alerts.

**Limits:** GitHub Actions cron runs at most every 5 minutes and may be delayed. Yahoo Finance `^GSPC` intraday bars are unofficial and may be delayed or missing. This is not a real-time trading execution system. The code requires fresh 1-minute candles (8-minute maximum age), six SMA slopes aligned on both 5m and 10m, and only alerts when a new qualifying alignment appears. It checks slope direction, not SMA value ordering. U.S. market holidays are handled indirectly by data freshness, not an exchange holiday calendar. The 20m and 1m columns are informational. All timeframes use completed bars.
