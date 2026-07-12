# Market Calendar Resolver (`aitrader/market_calendar.py`)

NYSE session-close resolver with multi-tier fallback, plus (0.3.0) the
per-class week-ahead schedule. Pure infra — answers the factual questions
"when does the US stock session close on date D?", "is there a session at
all?", and "when does each asset class open/close over the next N days?".
No thresholds, no opinions (BRIEF §2).

## Provenance
Clean-room port of `/src/trader/trader/market_calendar.py` (0.1.0,
2026-06-15); only the clock dependency changed (`trader.clock` →
`aitrader.timeutil`). In the old monolith the resolver usually ran with the
live broker in-process, so tier 1 did the work; in aitrader's split-MCP
architecture the scheduler process has no broker connection and always calls
with `broker=None`, which makes tier 2 (the rules library) the load-bearing
tier — and made the 0.1.0 holiday bug (below) live.

## Three-tier resolution (`resolve_and_cache`)
1. **Broker** — `broker.get_session_close(target_date)` (IBKR SPY liquidHours /
   Alpaca `/v2/calendar`) when the caller passes a broker. Authoritative.
2. **Library** — `pandas_market_calendars` NYSE schedule. Offline, rule-driven,
   knows holidays and half-days. Returns the close, or **NOT_TRADING_DAY**
   (a module sentinel) when the date has no session, or None when the library
   itself is unavailable.
3. **Hardcoded weekday 16:00 ET** — last-resort guard, only when tiers 1 and 2
   are UNAVAILABLE. Wrong on half-days and weekday holidays; logs loudly.

Per-process cache `session_close_cache: {date: (close|None, source)}` with
source ∈ {broker, library, fallback}; a non-broker answer upgrades to broker
truth the next time a broker query succeeds. `(None, "library")` = confirmed
non-trading day, cached for the date.

## History
- **0.1.0** — initial port.
- **0.2.0 (package 1.24.0, 2026-07-03)** — holiday fix: `query_library`
  previously returned None BOTH for "no session on this date" and "library
  failed", so `resolve_and_cache` fell through to tier 3 and fabricated a
  16:00 ET close on every weekday holiday (found live on 2026-07-03, the
  observed Independence Day: `market_status` emitted a contradictory
  `session_close_utc` and `wait_until_session_close` would sleep to 16:00 on
  a closed market). The NOT_TRADING_DAY sentinel makes a library-confirmed
  holiday a FINAL None answer. Note: the broker tier still conflates "broker
  says no session" with "broker query failed" (both None from
  `get_session_close`) — harmless today because the library tier follows and
  disambiguates, but a known asymmetry.

## Per-class week-ahead schedule (0.3.0, package 1.43.0)

`week_schedule(days)` → the session-start orientation fact: for each of
stock / futures / forex / crypto, whether it is open right now (by the
clock), every session span in the window (UTC + compact ET strings rendered
server-side), the class's NEXT open, and — for stock, when the library
answers — the window's closed weekdays (the "is Friday a holiday" answer).
Sources per class, each labeled in the payload (`source`):
- **stock/options** — `pandas_market_calendars` NYSE (holidays + half-days);
  rule fallback = weekday 09:30–16:00 ET, holiday-blind.
- **futures** — `pandas_market_calendars` CME_Equity (Globex: Sunday
  18:00 ET opens, holiday-aware); rule fallback = (D−1) 18:00 ET → D
  17:00 ET weekdays.
- **forex** — rule only: one continuous Sun 17:00 ET → Fri 17:00 ET week
  (the daily 17:00 pause is below this resolution).
- **crypto** — 24/7 clock; whether THIS broker offers crypto at all is
  `get_available_types`' job (IBKR paper: no).

Born from a live failure: itrader, flat on a Saturday, planned "redeploy
Monday 09:30" and would have slept through Sunday evening's futures/forex
opens — the toolset's only forward-looking schedule fact was NYSE next_open.

## Consumers
- Scheduler MCP `_regular_session_bounds` → `market_status`,
  `wait_until_session_close` (always `broker=None`); `get_market_schedule` →
  `week_schedule` (0.3.0).
- Broker drivers do NOT import this module; the relationship is the reverse
  (the resolver queries `broker.get_session_close`). The drivers' own
  holiday-aware session gates (package 1.24.0) query their broker calendars
  directly and keep their own per-date cache.
