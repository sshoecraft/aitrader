# api — FastAPI dashboard backend (`aitrader/api.py`)

## What it is

Pure-infrastructure HTTP backend for **trader-ui**. It surfaces data the system
already holds (broker truth + journal + settings) and performs mechanical control
actions (close a position, cancel an order, edit settings).
It makes **no trading decisions** and encodes **no strategy** — the same hard
boundary as the MCP servers (CLAUDE.md §2). Endpoints the old (Alpaca/`/src/trader`)
system had but aitrader has no concept of (`strategies`, `reviews`, `methods`,
`review`, engine `actions`) return safe empties so the shared UI doesn't crash;
those tabs are inert.

Run: `aitrader-api` → `uvicorn` on `settings.api_host:api_port` (default `:7099`).

## Connection model

The API owns its **own** execution-broker connection selected by
`settings.broker ∈ {ibkr, alpaca, myse}` (the same selector the MCP
`broker_server` uses), wrapped in a `BrokerRouter` with the optional
`settings.data_broker` so the dashboard shows the SAME prices the agent sees
(0.15.0 — before that `broker()` was hardwired to IBKR and 500'd/`connected:false`
on a non-IBKR node). For IBKR it pins **client_id 80** with tiny pools
(`orders/status/data = 1`) — deliberately separate from the autonomous agent
(client_ids 40–67); alpaca/myse just connect. A data-broker failure degrades to
the execution broker for data, never taking the dashboard down. A human action
here (e.g. a manual `/sell`) is just broker truth the agent reconciles on its
next cycle; no coordination channel is needed.

`/status` shows the agent's working orders via `Broker.list_all_open_orders()`:
on IBKR that's `reqAllOpenOrders` (each clientId otherwise sees only its own
orders); on shared-account brokers (Alpaca, MYSE) the ABC default
`get_orders(status="open")` already returns the whole account.

`/status` is cached for `STATUS_TTL` (~3s) behind a lock so concurrent dashboard
pollers don't each fire 4 broker calls — this also avoids IBKR Error 322
(too-many account-summary subscriptions).

## Time / timezone invariant (load-bearing)

Storage is **UTC**; display is **ET** (CLAUDE.md §6, `aitrader/timeutil.py`).
The API returns timestamps as raw UTC ISO strings (`utcnow_iso()`, plus journal
`ts` fields as stored) and the UI renders them. **Any selection by calendar date
must be done in the display calendar (ET), not UTC** — otherwise the filter
calendar and the display calendar disagree at the midnight boundary.

- `day_pl(current_equity)` — daily P&L = current equity minus the **first equity
  snapshot of the current ET trading day**. It computes ET midnight of the current
  ET day and converts that back to a UTC instant for the `equity_read(since=...)`
  filter, so the boundary matches the displayed (ET) day. Using a UTC date here
  (the original bug, fixed in 0.6.3) baselined off the wrong day in the ET evening
  — once past UTC midnight, "today" jumped a day and day P&L read ~0. See
  `CHANGELOG.md` [0.6.3].
- The `/sell` idempotency tag uses `utcnow().date()`; that is a deterministic tag,
  not a selection, so the UTC date there is harmless.

`/trades` accepts a `period` argument but **does not date-filter** — it returns
all broker fill activities as "transactions" (round-trip P&L pairing is not
reconstructed in v1). So unlike the `/src/trader` `/trades` endpoint, there is no
period-window timezone bug to fix here; `day_pl` was the only UTC-vs-ET selection.

## Endpoint surface (contract = `trader-ui/src/api.ts`)

| Endpoint | Purpose |
|---|---|
| `GET /health` | broker reachable? + version |
| `GET /status` | account + positions + orders + `heat` aggregate + `day_pl` (cached ~3s) |
| `POST /sell?symbol=` | mechanical `close_position` (deterministic client tag) |
| `POST /cancel/{order_id}` | cancel one order |
| `GET /portfolio_history?period=&timeframe=` | equity curve from journal equity snapshots, windowed by `period` (ET-aware: 1D=since ET midnight, YTD=since ET Jan 1, else rolling N-day; `1A`/1Y=365; ALL=unbounded) |
| `GET /bars`, `GET /snapshot/{symbol}` | raw market data passthrough |
| `GET /trades?period=` | broker fills as transactions (period currently ignored) |
| `GET/PUT/DELETE /settings` | `settings.toml` ↔ UI `{default,current}` |
| `GET /journal?limit=&kind=&symbol=&since=` | the agent's notebook as a normalized feed: `{entries:[{id,time(ISO-UTC),kind,symbol,text,tags,meta}]}` — SHARED contract with the trader API so trader-ui renders both; aitrader maps `ts→time`, `kind→kind`, `body→text`, `meta={}` |
| `GET /log` | tail the latest ccloop agent session output |
| `GET /strategies` `…/methods` `…/reviews` `…/review` `POST /actions/{a}` | inert stubs |

Position shape (`map_position`) defaults stop/limit/heat to 0 and `trail` to null,
then mechanical enrichers fill them from broker truth.
`enrich_positions_with_protective_orders` links standalone
protective stop/limit orders back to their position by symbol + opposite side so the
UI's per-position Stop/Limit columns populate from broker truth.
`enrich_positions_with_heat` computes **risk-at-stop as a fraction of equity** —
per position (the position's `heat`) and aggregated per asset class + total (the
top-level `heat` object the UI's HeatPanel renders: `total_heat`, `stock_heat`,
`crypto_heat`, `forex_heat`, `futures_heat`, `position_count`). Dollars at risk =
`|market_value|` when a position has **no** live protective stop (the whole position
is exposed — `market_value` already embeds the futures multiplier, so it's true
notional across asset classes; no stop = max heat), or the loss-if-stopped
(`|market_value| × max(0, distance_to_stop)/current`, floored at 0 so a profit-locked
stop reads as zero risk) when a live stop exists. This is **display-only
observability** derived from broker truth, in the same class as `to_stp` — NOT a
risk budget, cap, or gate, and the agent never sees it (it acts through MCP tools),
so it stays on the infra side of the hard boundary. The trader engine populates the
same panel from its risk engine; aitrader feeds the **shared** UI the same contract.
`enrich_positions_with_sector` fills each `us_equity` position's `sector`/`industry`
from the broker's IBKR contract classification (`IBKRBroker.get_classification`:
`reqContractDetails` industry → sector, category → industry), cached process-wide
since it's static reference data. ETFs bucket as "ETF" (from `stockType`);
forex/crypto/futures have no classification and stay null. This is a factual reference lookup (like `asset_class`), not a screen or
score — it stays on the infra side of the hard boundary.

## History

- **0.4.0** (project 0.15.0, 2026-06-18) — `broker()` honors `settings.broker`
  (ibkr|alpaca|myse) + optional `data_broker`, wrapped in a `BrokerRouter`,
  instead of being hardwired to IBKR. Fixes the Alpaca node, which had
  `connected:false` / `ibkr_port not found`. `Broker.list_all_open_orders` made
  portable via an ABC default (`get_orders(status="open")`); IBKR keeps its
  cross-client `reqAllOpenOrders` override. Package version drift (`__init__`
  stuck at 0.10.1 vs pyproject) synced to 0.15.0.
- **0.2.1** (project 0.9.0, 2026-06-16) — `/status` now returns a top-level `heat`
  aggregate and a real per-position `heat` (risk-at-stop ÷ equity), so the shared
  UI's HeatPanel renders for the aitrader engine instead of all-zeros. Display-only
  observability from broker truth; not a budget/gate (`enrich_positions_with_heat`).
- **0.1.1** (project 0.6.3, 2026-06-15) — `day_pl` baseline moved from the UTC
  calendar day to the ET trading day (display-calendar selection). Storage stays
  UTC; only the boundary computation moved into ET.
- **0.1.0** — initial dashboard backend matching the trader-ui contract.
