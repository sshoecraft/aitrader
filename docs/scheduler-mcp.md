# scheduler MCP

Pure blocking-wait mechanism. **Zero trading logic.** It decides nothing — it
sleeps until a time/condition the agent named, then returns, which resumes the
long-lived session in-place (BRIEF §A.4.2).

- Server: `aitrader/mcp/scheduler_server.py` (FastMCP, stdio) → `aitrader-scheduler-mcp`
- Time facts: `aitrader/market_calendar.py` (NYSE; broker tier when a broker is
  passed, else offline `pandas_market_calendars`; hardcoded 16:00 ET last resort).

## Tools (6)
| tool | blocks until | notes |
|---|---|---|
| `now` | — | `utc` (canonical) + `local` (host wall clock — use for journal prose) + `et` (NYSE session clock) |
| `market_status` | — | NYSE regular-session open?, today's close, next open |
| `wait_seconds(seconds)` | now + seconds | **floor-clamped** to `AITRADER_WAKE_FLOOR_SECONDS` (default 5) — the cadence fuse |
| `wait_until(iso_utc)` | a UTC time | already-past returns immediately |
| `wait_until_market_open` | next NYSE regular open | already-open returns immediately |
| `wait_until_session_close` | today's NYSE close | not-a-trading-day returns immediately |

Every wait returns `{waited_seconds, woke_reason, now_utc, now_et, ...}` where
`woke_reason ∈ {condition_met, already_past, already_open, ...}`. `market_status` also
returns `now_local` alongside `now_utc`/`now_et` (1.10.0 — the agent journals in local time;
ET is retained as the NYSE session clock, never a hardcoded global).

## Design decisions (deviations from BRIEF §A.4.2, with rationale)
1. **`wait_for_fill` is in the BROKER MCP, not here.** Polling an order needs the
   broker connection, which the broker MCP owns; two processes can't share one
   IBKR socket cleanly. Keeping it broker-side avoids a redundant connection.
2. **Chunked waits, not one long sleep.** Each wait loops `asyncio.sleep(1s)` so a
   multi-day weekend wait stays cancellable and process death is safe — the
   harness relaunches and the agent reconciles. (Also the hook point for a future
   broker-event early wake.)
3. **NYSE-clock only.** `market_status` is the stock clock. For what is
   *tradeable right now* across asset classes (crypto 24/7, futures/forex own
   hours) the agent reads the BROKER MCP's `get_available_types` /
   `get_market_session` — those are broker truth (actually holiday-aware since
   package 1.24.0); the scheduler is a scheduling aid, not a tradeability
   oracle.
4. **Holidays are final, not fallback (market_calendar 0.2.0).** The resolver's
   library tier distinguishes "no session on this date" (NOT_TRADING_DAY —
   final: `session_close_for` returns None, cached `(None, "library")`) from
   "library unavailable" (falls to the weekday-16:00 guard). Before 0.2.0 a
   weekday holiday fabricated a 16:00 close, so `market_status` emitted a
   contradictory `session_close_utc` and `wait_until_session_close` slept to
   16:00 on a closed day; both now resolve to no-session immediately.

## Status
Built and tested (2026-06-15) without a broker: 6 tools register; library-tier
calendar resolves correct NYSE open/close; `wait_seconds(1)` correctly clamps to
5s; chunked-wait cancellation path implemented.
