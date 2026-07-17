# api — FastAPI dashboard backend (`aitrader/api.py`)

## What it is

Pure-infrastructure HTTP backend for **trader-ui**. It surfaces data the system
already holds (broker truth + journal + settings) and performs mechanical control
actions (close a position, cancel an order, edit settings).
It makes **no trading decisions** and encodes **no strategy** — the same hard
boundary as the MCP servers (CLAUDE.md §2). Endpoints the old (Alpaca/`/src/trader`)
system had but aitrader has no concept of (`strategies`, `reviews`, `methods`,
engine `actions`) return safe empties so the shared UI doesn't crash; those tabs
are inert. `/review` (singular) is **not** one of these — it is fully wired to
serve the agent's own recorded rationale; only the plural `/reviews` is the
inert stub (see the endpoint table below).

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

**Degraded-mode resilience (0.15.2).** `/status`'s orders fetch
(`list_all_open_orders()`) is deliberately **non-fatal** — a failure logs a
warning and serves account + positions + equity + `day_pl` with an empty
orders list (positions just miss protective-order enrichment that cycle)
rather than hanging the whole dashboard behind `_status_lock`. This was found
against a real outage: Alpaca's paper `/v2/orders` went unresponsive (~20s
timeout) while `/v2/account`/`/v2/positions` returned in 0.2s, and the
unguarded orders call took the entire endpoint down for every poller. Paired
with `brokers/alpaca.py enforce_http_timeout`, which mounts a urllib3 Retry
adapter on the alpaca-py session: `connect=3` (reopen a fresh socket when a
pooled keep-alive connection dropped after idle), `read=0` (a genuinely
unresponsive endpoint fails once, not with multiplying retries),
`allowed_methods={GET,HEAD,OPTIONS}` (so a slow order POST/cancel is never
silently re-sent), and a `(connect=5s, read=12s)` timeout tuple (was a single
30s). Net effect during an upstream outage: first uncached `/status` costs
~12s (one timeout), then serves from cache; account/positions/equity/P&L stay
live throughout, and the orders column self-heals once the endpoint recovers.

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
| `POST /sell?symbol=` | mechanical `close_position` (deterministic client tag); usually one order dict, or `{count, orders}` if the symbol held more than one distinct futures contract |
| `POST /cancel/{order_id}` | cancel one order |
| `GET /portfolio_history?period=&timeframe=` | equity curve from journal equity snapshots, windowed by `period` (ET-aware: 1D=since ET midnight, YTD=since ET Jan 1, else rolling N-day; `1A`/1Y=365; ALL=unbounded) |
| `GET /bars`, `GET /snapshot/{symbol}` | raw market data passthrough (from the node's broker) |
| `GET /benchmark?symbol=VTI&period=1D` | broker-INDEPENDENT benchmark series for the relative-performance overlay. Sourced from Yahoo's keyless v8 chart endpoint (NOT the broker), RTH-only, same `{symbol:[{t,o,h,l,c,v}]}` shape as `/bars`, keyed on chart period (server maps period→Yahoo range/interval), cached per (symbol,period) ~60s. Broker-sourced VTI made atrader (Alpaca tape) and itrader (IBKR feed) rebase to different bars and report different VTI%; a benchmark is one shared reference and an IBKR-only node has no Alpaca feed. Needs no broker connection. |
| `GET /trades?period=` | broker fills as transactions (period currently ignored) |
| `GET/PUT/DELETE /settings` | `settings.toml` ↔ UI `{default,current}` |
| `GET /journal?limit=&kind=&symbol=&since=` | the agent's notebook as a normalized feed: `{entries:[{id,time(ISO-UTC),kind,symbol,text,tags,meta}]}` — SHARED contract with the trader API so trader-ui renders both; aitrader maps `ts→time`, `kind→kind`, `body→text`, `meta={}` |
| `GET /log` | tail the latest ccloop agent session output |
| `GET /review?symbol=` | **real, working endpoint** — the agent's own recorded rationale for a symbol (position-of-record + that symbol's journal entries), pure read, no reviewer cognition; 404 if nothing recorded (see below) |
| `GET /strategies` `…/methods` `…/reviews` `POST /actions/{a}` | inert stubs (old-system concepts aitrader has no equivalent of) |

Position shape (`map_position`) defaults stop/limit/heat to 0 and `trail` to null,
then mechanical enrichers fill them from broker truth. `expiry` (0.7.1) is carried
through as-is (empty string when absent/non-futures) — two positions can share one
canonical symbol when a futures roll leaves an old-expiry contract open alongside a
new one (see `docs/broker-ibkr.md`'s held-contract resolution); without `expiry` the
dashboard/CLI had no way to show these apart from an unexplained duplicate row.
`enrich_positions_with_protective_orders` links standalone
protective stop/limit orders back to their position by symbol + opposite side (AND
matching `expiry` when the position carries one, 0.7.1 — otherwise a stop could
cross-attach to the wrong same-symbol futures contract) so the
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
from the broker's `get_classification`, cached process-wide since it's static
reference data. Each backend supplies the same `{sector, industry}` shape from its
own factual source: **IBKR** reads `reqContractDetails` (industry → sector, category
→ industry); **Alpaca** has no fundamental data in its API, so `AlpacaBroker.get_classification`
(0.4.0) reads Yahoo Finance's keyless quote-search endpoint
(`query1.finance.yahoo.com/v1/finance/search`) and exact-matches the symbol
(normalizing Alpaca's `BRK.B` dot to Yahoo's `BRK-B` dash). Without this, the
Alpaca node had no classification method at all — every call raised `AttributeError`
into `enrich_positions_with_sector`'s `except`, so the dashboard bucketed all
positions under "Unclassified". ETFs bucket as "ETF" (IBKR `stockType`, Alpaca
`quoteType`); forex/crypto/futures have no classification and stay null; network
failures return `{}` (degrade to "Unclassified", never error). This is a factual
reference lookup (like `asset_class`), not a screen or score — it stays on the infra
side of the hard boundary.

## History

- **0.7.1** (project 1.49.8, 2026-07-15) — `map_position`/`map_order` carry
  `expiry` through instead of dropping it; `enrich_positions_with_protective_orders`
  matches on `expiry` too when the position has one. `POST /sell` (mechanical
  `close_position`) can now return `{"count": N, "orders": [...]}` instead of a
  single order dict, when the symbol resolved to more than one distinct held
  futures contract — see `docs/broker-ibkr.md`'s held-contract resolution.
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
