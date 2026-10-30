# SPX SMA Monitor

Free, unofficial Yahoo Finance `^GSPC` 1-minute price collector and four-timeframe SMA analysis (20/10/5/1-minute; SMA 10/20/30/40/50). Each GitHub Actions run produces a Markdown summary and downloadable JSON/CSV artifacts. Use **Actions → SPX SMA hourly check → Run workflow** for a manual run.

**Limitations:** GitHub scheduled runs can be delayed, Yahoo intraday data can be delayed/blocked/missing, and incomplete 1-minute bars are discarded. This package does **not** yet deliver iPhone push notifications or modify your ChatGPT automation. The GitHub workflow runs at UTC hours that cover both EDT and EST, so some checks will be outside the regular session. Verify results before trading.

**Full alignment:** all five SMA slopes agree and their strict numeric ordering agrees. 20-minute aggregation discards the short final 10-minute bar; the 1-minute bars must be contiguous. More than 50 completed bars are required per timeframe.
