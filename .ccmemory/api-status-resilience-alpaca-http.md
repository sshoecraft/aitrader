---
name: api-status-resilience-alpaca-http
description: aitrader 0.15.2: /status orders fetch is non-fatal (degrades when Alpaca /v2/orders hangs); alpaca HTTP session has connect-retry + (5s,12s) timeout,…
metadata:
  type: project
---

If the aitrader dashboard `/status` hangs but `/health` is fine and equity reads
fail intermittently, suspect a **single degraded broker REST endpoint**, not the
whole broker. 2026-06-18: Alpaca's paper `/v2/orders` went unresponsive (direct
fresh-connection `GET /v2/orders` timed out ~20s) while `/v2/account` and
`/v2/positions` returned in 0.2s. Diagnose by hitting the raw Alpaca REST
endpoints directly with urllib + a timeout (keys in
`~/.config/aitrader/secrets.toml`: `alpaca_api_key`/`alpaca_secret_key`) — a fresh
connection isolates upstream slowness from our code.

**Two bugs this exposed (fixed 0.15.2):**
1. `api.py compute_status()` called `list_all_open_orders()` UNGUARDED, so one hung
   sub-call took down all of `/status`; and `/status` holds `_status_lock`, so every
   poller (UI + snapshot cron + manual curl) queued behind it → looked permanently
   hung even right after a restart. Fix: the open-orders fetch is now non-fatal
   (try/except → `orders=[]`, logged); account/positions/equity/day_pl still serve.
   Pattern: in `/status`, only account+positions are critical; everything else
   (orders, available_types, classification) must be best-effort.
2. `brokers/alpaca.py enforce_http_timeout` now also mounts a urllib3 Retry adapter
   on the alpaca-py `_session`: `connect=3` (reopen a fresh socket when a pooled
   keep-alive connection was dropped after idle — a separate long-lived-process
   hang mode), `read=0` (do NOT retry read timeouts — a hung endpoint should fail
   once, not multiply the wait), `allowed_methods={GET,HEAD,OPTIONS}` so an order
   POST/cancel is NEVER silently re-sent. Timeout is now `(connect=5s, read=12s)`,
   was a single 30s (`HTTP_TIMEOUT_SEC` is now that tuple).

Net during an Alpaca orders outage: first uncached `/status` ~12s (one timeout)
then 3s-cached; orders column empty until upstream recovers, then auto-repopulates.
Deploy via [[api-service-deploy-path]]. See [[api-multibroker-and-version-drift]].</body>
