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
time math; the `get_setting("extended_hours")` lookup became the
`extended_hours` constructor flag. The unused `pround` import was dropped.

## Classification (`get_classification`)
`get_classification(symbol)` returns `{"sector": ..., "industry": ...}` from the
contract's `reqContractDetails` (IBKR `industry` → sector, `category` → industry).
Equity-only (`isinstance(contract, Stock)`); forex/crypto/futures/options return
`{}`. ETFs/funds have no industry — their `stockType` ("ETF"/"FUND") becomes the
sector so they bucket as "ETF"/"Fund" rather than "Unclassified". This is a factual
reference lookup of a security's published classification —
on the infra side of the boundary, like `asset_class`, NOT a screen or score. The
API (`enrich_positions_with_sector`) caches results process-wide.

## Market calendar
The driver does NOT import `market_calendar`. The relationship is the reverse:
the resolver calls `broker.get_session_close(target_date)` (self-contained here
via SPY liquidHours). Expected resolver interface in `aitrader/market_calendar`:
`session_close_today(broker=None)`, `on_market_open(broker)`,
`resolve_and_cache(target_date, broker)`, `query_broker(broker, target_date)` —
each calling `broker.get_session_close(target_date) -> datetime|None`.
