---
name: holiday-aware-session-gate
description: 1.24-1.25: session+availability were holiday-blind weekday math; now gated on broker calendar/contract hours, cached per ET date; route_to must not r…
metadata:
  type: project
---

# Holiday-blind market sessions — root cause + 1.24.0/1.25.0 fixes (2026-07-03)

## Symptom
On Friday 2026-07-03 (Independence Day observed, NYSE closed — July 4 fell on a
Saturday) BOTH live nodes (itrader/IBKR, atrader/Alpaca) reported the stock
market open and surveyed a dead market on stale July-2 quotes. After the stock
fix deployed, futures/forex still overreported around CME's holiday halt.

## Root cause (three layers)
1. `get_market_session` on BOTH drivers was pure weekday + 9:30-16:00 ET time
   math, zero holiday awareness; `get_available_types` derives `stock` from it;
   constitution step 2 tells the agent "Don't assume market hours — use the
   tool". The old /src/trader IBKR driver consulted **Alpaca's clock** here; the
   clean-room port removed that cross-broker call "in favor of pure time math"
   (documented in docs/broker-ibkr.md) and holiday awareness silently went with
   it. The ABC then CODIFIED the blindness ("Pure time-math check — no API
   calls"). Lesson: when stripping a layering smell, check what correctness it
   was carrying.
2. Holiday-aware plumbing existed but unused for open/closed: Alpaca
   `/v2/calendar`, IBKR SPY liquidHours (`get_session_close`), Alpaca `/v2/clock`
   (never called anywhere; only MYSE asks its own `/clock`).
3. `market_calendar.query_library` conflated "holiday" (empty schedule) with
   "library failed" (both None) → tier 3 fabricated a weekday-16:00 close on
   holidays, so `market_status` emitted a contradictory `session_close_utc` and
   `wait_until_session_close` would sleep to 16:00 on a closed day.

## Fixes
**1.24.0 — stock session (both drivers).** Gate the clock math on today's close
from the broker's OWN calendar (alpaca.py 0.5.0 `/v2/calendar`; ibkr.py 1.3.0
SPY liquidHours), cached per ET date in `session_close_by_date` (None =
confirmed no-session; failures never cached). Holiday = `closed` outright (no
extended windows); half-days end regular at the true early close. Calendar
unreachable → legacy weekday math. market_calendar 0.2.0: `NOT_TRADING_DAY`
sentinel; confirmed holiday caches `(None, "library")` — tier 3 only fires when
tiers are UNAVAILABLE. ABC broker.py 2.4.0 docstrings REQUIRE the gate.

**1.25.0 — IBKR forex/futures availability (ibkr.py 1.4.0).** Both flags now
come from the LIVE `tradingHours` windows of representative contracts (forex:
EUR/USD IDEALPRO; futures: front-month ES — same proxy pattern as SPY).
`parse_trading_hours` (module-level, pure) handles modern
`YYYYMMDD:HHMM-YYYYMMDD:HHMM`, legacy `date:HHMM-HHMM,…`, and `:CLOSED` forms
in the details' own `timeZoneId` (US/Central for CME). `class_open_now`
evaluates now-in-window; cache `class_windows_by_date` per (class, ET date);
failure → weekday-math fallback, never cached. Alpaca/MYSE have no
forex/futures.

## IBKR plumbing rules (load-bearing for future edits)
- A `@route_to` method must NEVER call another `@route_to` method: pool
  re-entry (TLS set) returns the raw coroutine of an async body; non-pool mode
  nests `asyncio.run` → RuntimeError. Shared logic lives in UNDECORATED helpers
  (`market_session_now`, `session_close_from_gateway`,
  `class_windows_from_gateway`, `class_open_now`) that routed wrappers await.
- The legacy `pool_mode=False` + sync `IB.connect()` path CANNOT make
  post-connect gateway calls through the route wrapper's `asyncio.run`: the
  connection binds to the connect-time loop; a second loop's awaits deadlock
  (validate_portfolio hangs on connect). For live single-connection testing,
  use ONE `asyncio.run(main())` with `await ib.connectAsync(...)`, assign
  `b.direct_ib = ib`, and await the undecorated helpers directly.
- Interactive/test gateway connections from other users: pick a client id far
  from itrader's (pools ~40-70, API 80, interactive 110+); 993 worked.

## Router note
Time facts (`get_market_session`/`get_available_types`/`get_session_close`) are
NOT in `DATA_METHODS` → always served by the EXECUTION broker, so itrader gates
via IBKR and atrader via Alpaca even with data_broker set.

## Verified
1.24.0: 13/13 real-data checks (rules library + real failing API/gateway
calls). Deployed to both nodes same day — /status then showed stock:False on
the holiday. 1.25.0: live against the real paper gateway (port 4002, client id
993, read-only): futures window `Thu 18:00 → Fri 13:00 ET` (CME holiday halt
from the broker's own string), forex `Thu 17:15 → Fri 17:00 ET`,
`market_session_now` = closed from real SPY liquidHours, gate == window math,
no fallback consumed. Deploy per [[api-service-deploy-path]]. Related:
[[data-execution-broker-split]], [[shared-alpaca-account-external-flatten-risk]].
