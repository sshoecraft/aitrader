---
name: equity-backfill-on-first-sync
description: 1.1.1: broker MCP maybe_backfill_equity backfills journal equity_snapshots from broker get_portfolio_history on first SUCCESSFUL data read, skipping…
metadata:
  type: project
---

aitrader auto-backfills the dashboard equity curve so a fresh install isn't flat
until the recorder accumulates points. **1.1.1** behavior (1.1.0's "adopt" was wrong):

- **Where:** `aitrader/mcp/broker_server.py:maybe_backfill_equity(b)` — NOT in
  `journal_db` (db.py stays pure storage; helper `equity_ts_set(conn)`). Called from
  `broker_status`/`get_account`/`get_positions` **after** a successful data read, so a
  connected-but-not-serving broker (IBKR mid-login) never triggers it. Never raises.
- **Runs once** via semaphore `<state_dir>/.equity_backfilled` (stamped only after
  success; content = ts + "backfilled N rows / skipped M"). On every later call/restart:
  semaphore present → instant no-op.
- **Composes, does NOT adopt:** on first run it ALWAYS backfills, **skipping any ts
  already in equity_snapshots**. Broker history = daily points (~1yr); recorder = 15-min
  recent — non-overlapping ts, so they merge with no dupes. The earlier "any existing
  rows → adopt" was wrong: the recorder timer fires every 15 min and beats the agent's
  first reconcile, which then suppressed the backfill (observed: adopted 12 rows, 3-hr
  curve). Dedup fixes it AND improves upgrades (they gain the deep history).
- **Source:** `broker.get_portfolio_history(period="1A", timeframe="1D")` → parallel
  `{timestamp[] epoch s, equity[], profit_loss[]}`; ts via `timeutil.epoch_to_iso`
  (`+00:00` form `equity_read` sorts on — see [[equity-snapshots-order-by-ts]]).
- **Verified on tester** (live Alpaca, broker=alpaca): 252 daily backfilled + 13 recorder
  rows, skipped 0, curve spans a full year; dashboard `/portfolio_history` serves 264 pts.
- Scope: equity only (trades read live via `/trades`; rationale unreconstructable).
  Force re-backfill: stop agent, delete the semaphore (dedup makes a re-run safe).
  Relates to [[equity-snapshot-recorder-cron]], [[aitrader-product-packaging-1.0]].</body>
