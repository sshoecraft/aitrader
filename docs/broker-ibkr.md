# IBKR Broker Driver (`aitrader/brokers/`)

Clean-room port of the IBKR broker driver from `/src/trader` for the §A.3 job:
the new standalone broker OWNS ITS OWN connection (the old driver assumed the
engine's Command module owned the IBKR connection and pumped `wait()`).

## Files
- `ibkr_connection.py` — one `IBKRConnection` = one ib_async `IB()` on its own
  daemon worker thread + persistent asyncio loop. The thread IS the ib_async
  callback pump (`run_forever()`); the socket reader delivers events with no
  polling. A 5s supervisor task confirms health and reconnects on drop.
  **Paper-only fuse** (`assert_paper`): after connect/reconnect, verifies every
  managed account id starts with `DU`/`DF` (paper). Non-paper raises
  `PaperOnlyError` and refuses, unless `allow_live=True`.
- `ibkr_pool.py` — `IBKRConnectionPool`: N connections, method-aware routing
  (`run`/`run_pinned`/`scatter_run`/`pin`). Threads `allow_live` to each
  connection. `merge_by_id` dedupes scatter results.
- `ibkr.py` — `IBKRBroker(Broker)`. Three pools (orders/status/data). Methods
  decorated with `@route_to(...)` dispatch their body onto the right pool via a
  thread-local `self.ib`. `pool_mode=True` is the default; `pool_mode=False` is
  a test path with a single directly-assigned `IB()`.
- `aitrader/futures.py` — pure data (`SPECS`, `TICK_SIZES`) + `round_to_tick`,
  needed by the order-placement methods. No cognition.

## Connection / construction
`IBKRBroker(host=None, port=None, client_id=None, pool_mode=True,
pool_sizes=None, connect_stagger_ms=250, connect_timeout=30,
idle_pump_seconds=None, allow_live=False, extended_hours=False,
secrets_path=None)`. When host/port/client_id are omitted they load from
`aitrader.credentials.load_ibkr_credentials()`. `allow_live` defaults False and
flows to every connection's paper fuse.

Lifecycle: `connect()` starts the pools, waits ready (paper fuse runs here),
validates the portfolio. `reconnect()` forces reconnect. `wait()` yields CPU
(each connection pumps its own loop). `stop()` stops all pools.

## Idempotency (BRIEF §5)
Every `place_*` and `close_position` accepts `client_tag=None`, stamped onto
`Order.orderRef` via `apply_order_ref`. Bracket orders tag all three legs.
`normalize_order` surfaces it back as `order_ref`.

## Hard boundary (BRIEF §2) — what was stripped
This driver is pure primitives. From the old file the following were dropped as
cognition / non-primitive: `get_market_movers` (scanner = ranked shortlist),
`get_news` (native to Claude). The DB-backed forex-position reconstruction
(`trader.db`) was replaced with pure IBKR account-value reconstruction
(`get_forex_cash_positions`, forex branch of `verify_position_for_sell`). The
Alpaca clock dependency in `get_market_session` was removed in favor of pure
time math (a cross-broker layering smell — but the holiday awareness silently
went with it, so both live nodes called July 3 2026 "open"; restored in 1.3.0
via IBKR's OWN calendar, see "Session gate" below); the
`get_setting("extended_hours")` lookup became the `extended_hours` constructor
flag. The unused `pround` import was dropped.

## Availability gate (1.4.0) — forex/futures from real contract hours
The 1.3.0 gate fixed only the STOCK flag; forex/futures in
`get_available_types` were still Sun-5PM-to-Fri-5PM weekday arithmetic and
overreported on CME holiday halts (July 3 2026: Globex halts 12:00 CT but the
math said open until 17:00 ET). Now both flags come from the LIVE trading
windows of a representative contract — forex: EUR/USD IDEALPRO; futures:
front-month ES (the same proxy pattern as SPY for the stock session).
`class_windows_from_gateway` pulls contract-details `tradingHours` (NOT
liquidHours — the overnight Globex session is tradeable) and
`parse_trading_hours` (module-level, pure) converts the exchange-local
`YYYYMMDD:HHMM-YYYYMMDD:HHMM` / legacy `YYYYMMDD:HHMM-HHMM` / `:CLOSED`
entries into UTC windows using the details' own `timeZoneId` (US/Central for
CME). `class_open_now` evaluates now-in-window per call with windows cached
per (class, ET date) in `class_windows_by_date`; gateway failure returns the
caller's weekday-math answer and is never cached. Crypto stays `not
is_paper()` (Paxos is live-only); options stay `session == "regular"`.

## Session gate (1.3.0) — holiday-aware get_market_session
`get_market_session` / `get_available_types` are now routed-async and gate the
9:30-close clock math on **today's session close from SPY liquidHours** (broker
truth): a date the gateway confirms has no session is `closed` outright (no
extended windows on holidays), half-days end the regular session at the real
early close, and only when the gateway CANNOT answer (10s `wait_for`, failure
never cached) does it degrade to the old holiday-blind weekday math. One
gateway query per ET date, cached in `session_close_by_date` (None = confirmed
no-session day). Plumbing rule that shaped this: routed methods must not call
other `@route_to` methods (pool re-entry returns a raw coroutine; non-pool mode
nests `asyncio.run`) — so the bodies live in undecorated helpers
`market_session_now()` / `session_close_from_gateway()` that both routed
wrappers await directly.

## Classification (`get_classification`)
`get_classification(symbol)` returns `{"sector": ..., "industry": ...}` from the
contract's `reqContractDetails` (IBKR `industry` → sector, `category` → industry).
Equity-only (`isinstance(contract, Stock)`); forex/crypto/futures/options return
`{}`. ETFs/funds have no industry — their `stockType` ("ETF"/"FUND") becomes the
sector so they bucket as "ETF"/"Fund" rather than "Unclassified". This is a factual
reference lookup of a security's published classification —
on the infra side of the boundary, like `asset_class`, NOT a screen or score. The
API (`enrich_positions_with_sector`) caches results process-wide.

## Forex & futures (symbols, universe, market data)
**Symbol form.** Canonical is slash (`EUR/USD`); IBKR contracts are concatenated
6-char pairs (`EURUSD`) built by `resolve_forex_pair_name` + `FOREX_CASH_MAP`.
`make_contract` calls `normalize_pair_symbol` (in `asset_types`) first, so TWS
dot notation (`EUR.USD`) is accepted — but only when both sides are ISO currency
codes, so equity share classes (`BRK.B`) are never mangled. Inversion for CAD/JPY
(`USDCAD`/`USDJPY`) and cash-balance position reconstruction are unchanged from
the port (`is_forex_inverted`, `forex_convert_for_order`, `get_forex_cash_positions`).

**Universe enumeration (1.9.0).** `get_tradeable_assets(FOREX)` returns the major
IDEALPRO pairs (`FOREX_UNIVERSE`, 12 pairs); `get_tradeable_assets(FUTURES)`
returns every `FUTURES_SPECS` contract. This is the COMPLETE list the broker
offers (raw infra enumeration, BRIEF §2) — never ranked or filtered. It mirrors
`SUPPORTED_CRYPTO`. Before 1.9.0 both returned `[]` (the old trader backfilled
the universe via its screener's `[screener] forex_universe` setting — deleted
here as cognition without replacing the enumeration, so the agent had nothing to
survey). `FOREX_UNIVERSE` directions are chosen to match IDEALPRO's standard pair
so each qualifies and round-trips through `normalize_position`.

**Market-data type (1.9.0).** `get_snapshot`/`get_snapshots` call
`reqMarketDataType(3)` so an account without a real-time subscription (paper, or
unsubscribed forex/futures feeds) returns DELAYED quotes instead of an all-zeros
snapshot; a live subscription still serves real-time. `get_snapshot` polls
briefly for the first streaming tick rather than a single fixed 1s sleep that
often read before any tick landed.

## Market calendar
The driver does NOT import `market_calendar`. The relationship is the reverse:
the resolver calls `broker.get_session_close(target_date)` (self-contained here
via SPY liquidHours). Expected resolver interface in `aitrader/market_calendar`:
`session_close_today(broker=None)`, `on_market_open(broker)`,
`resolve_and_cache(target_date, broker)`, `query_broker(broker, target_date)` —
each calling `broker.get_session_close(target_date) -> datetime|None`.
