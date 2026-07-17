# broker data feed — the data/execution split (§A.3)

aitrader can serve **market data** (bars + snapshots + the tradeable list) from a
broker *different* from the one it **executes** on. The EXECUTION backend is
`settings.broker` ∈ {ibkr (default), alpaca, myse}; the optional market-data feed
is `settings.data_broker`. On the aitrader box that's `broker=ibkr` (paper account
`DU0000000`) + `data_broker=alpaca`; a pure-Alpaca box sets `broker=alpaca` and no
data_broker (the execution broker serves data too). `broker_server.
build_execution_broker()` constructs the backend (IBKR keeps the clientId lease;
alpaca/myse just connect). This mirrors `/src/trader`'s `broker` + `data_broker`
topology.

**Why.** IBKR's *paper* market data returns nothing before the opening auction
(and is subscription-gated), so the agent kept hitting "DATA FEED DEAD
PRE-MARKET" — empty bars/snapshots pre-open with no informed decision possible.
Alpaca's consolidated tape (SIP) + IEX snapshots cover pre/after-hours, so the
agent gets a live tape the moment it wakes. Nothing about *decisions* changes —
this is infrastructure: a better pipe for the same raw OHLCV the agent already
reasons over.

## Components

- `aitrader/brokers/alpaca.py` — `AlpacaBroker`, FULL data + execution on the
  `alpaca-py` SDK (0.13.0 added execution; was data-only in 0.11.0). Data methods
  + execution (account/positions, place/modify/cancel/bracket, fills) normalized
  to the SAME dict shapes `IBKRBroker` returns (`latestTrade/dailyBar/
  prevDailyBar`; `t/o/h/l/c/v`; orders carry `order_ref` = your `client_tag`).
  Used as the `data_broker` on aitrader, or as the execution `broker` on a
  pure-Alpaca box. No long-only enforcement (IBKR had one — a leftover
  `/src/trader` guard, removed in 1.5.0 — see docs/broker-ibkr.md; the two
  drivers now agree); options/bracket raise `NotImplementedError`.
- `aitrader/brokers/myse.py` — `MYSEBroker`, REST execution backend (stocks only,
  24/7 sim exchange). Same normalized shapes + `order_ref`.
- `aitrader/brokers/router.py` — `BrokerRouter`, a transparent proxy holding the
  execution broker + an optional data broker. `__getattr__` dispatches each call
  per `resolve(method, kwargs)`.
- `aitrader/mcp/broker_server.py::broker()` — builds IBKR (execution) + optional
  Alpaca (data via `build_data_broker()`) and returns the router. A data-broker
  build failure is caught and logged; the server proceeds IBKR-for-data so a dead
  feed never stops execution.

## Routing rules (`BrokerRouter.resolve`)

`DATA_METHODS = {get_bars, get_snapshot, get_snapshots, get_tradeable_assets}`.

1. No data broker configured → execution (IBKR), always.
2. Method ∉ `DATA_METHODS` → IBKR. **Account, positions, orders, fills,
   place/modify/cancel — all IBKR.** (`get_fill_activities` is deliberately NOT a
   data method: fills are account-of-record data and the account lives on IBKR.)
3. Data method with `asset_type` ∈ `data_broker_types` → data broker (Alpaca).
4. Anything else — including a data call with **omitted/unknown `asset_type`** →
   IBKR.

### One deliberate divergence from `/src/trader`
`/src/trader` routed a market-data call with **no** `asset_type` to the data
broker. aitrader does **not** — an omitted/unknown `asset_type` falls through to
IBKR. IBKR prices every asset class; Alpaca only stock + crypto. So a
futures/forex/options data call that forgets `asset_type` can never be silently
mis-served by Alpaca. The data feed is reached **only on an explicit stock/crypto
`asset_type`**. (`/src/trader` also put `get_fill_activities` in its data methods;
aitrader keeps fills on IBKR — see rule 2.)

## Config

- `settings.toml`: `data_broker = "alpaca"` (unset → IBKR serves data);
  `data_broker_types = ["stock", "crypto"]`.
- `secrets.toml`: `alpaca_api_key`, `alpaca_secret_key` (paper keys; the data API
  is read-only here). `aitrader.credentials.load_alpaca_credentials()` loads them.
- `alpaca-py>=0.30.0` is a base dependency so `make install` provisions it
  without a Makefile change. Installed/verified at `alpaca-py 0.43.4`.

## What the agent sees

Nothing new in the tool surface — same tool names, signatures, and dict shapes.
The only observable change: `get_bars`/`get_snapshot(s)` for stock/crypto return
**populated** data (incl. pre-market) instead of empty/zeros — **but only when the
agent passes `asset_type='stock'`/`'crypto'`** (see routing rule 4). The data-tool
docstrings tell it to, and spell out the consequence (omit → IBKR → empty
pre-open). They also note the tape (Alpaca) and execution venue (IBKR) can differ
slightly in last-price/symbol coverage.

### Design note — why the agent must pass asset_type (and we don't infer it)
We considered auto-routing by classifying the symbol when `asset_type` is omitted.
Rejected: it would duplicate IBKR `make_contract`'s heuristics (`FUTURES_SPECS`,
`SUPPORTED_CRYPTO`, forex-pair detection) inside the router and couple it to the
driver — and a bare futures ticker queried without `asset_type` would regress
(routed to Alpaca → empty instead of IBKR's resolved contract). The clean choice:
keep the router dumb, nudge the agent via the tool docstrings, and let it own the
call. If it omits `asset_type`, it gets IBKR — that's acceptable, not a bug.

## Status

Built + **LIVE-verified 2026-06-17 08:42 ET (pre-market)**: `get_snapshot('AAPL',
stock)` → live `latestTrade.p=299.26`; AAPL daily SIP bars (5), BTC/USD 1h bars,
73 tradeable crypto; router resolution (stock/crypto→Alpaca, account/orders/fills
+ no-asset_type→IBKR) and Alpaca execution refusals all pass. Activates on the
next ccloop relay after `make install` (the running session keeps its loaded
MCP). Revert: unset `data_broker` in `settings.toml`.

## Notes / caveats

- **SIP vs IEX.** `get_bars` (stock) defaults to the SIP consolidated feed for
  full-session coverage. If the Alpaca plan lacks recent-SIP, callers can bound
  `end` to a completed month or the adapter can be called with `feed=IEX`.
  Snapshots use the default (IEX) feed, which is what gives live pre-market.
- **Tape vs fills basis.** Bars/snapshots come from Alpaca; fills happen on IBKR.
  For stocks the basis difference is negligible; for crypto (different venues) it
  can be larger. Symbol coverage can also differ — a symbol in Alpaca's list
  isn't guaranteed tradeable on IBKR; confirm via snapshot/order.
- **`get_bars(start=...)` semantics differ by broker — don't tune to one.**
  Alpaca's `get_bars` returns bars only chronologically **FROM** `start` and
  gives **ZERO** bars if `start` is after the last available session (weekend/
  holiday/pre-open) — no backward padding. IBKR's `get_bars` instead converts
  `start` into a *duration* and pads it backward (`days_diff = (today -
  start).days + 5`), so even `start = today-midnight` returns recent sessions.
  This bit the dashboard's 1D VTI benchmark overlay: it worked on the IBKR node
  and returned empty on the Alpaca node on a non-trading day. If something works
  on one broker's data path and not the other, suspect `get_bars` windowing
  semantics first; widen the lookback rather than relying on either broker's
  padding behavior.
- **Alpaca has no crypto stop-market.** A plain stop order on a crypto symbol is
  rejected by the venue — only stop-limit is supported. `place_stop_order`
  (`aitrader/brokers/alpaca.py`) auto-routes crypto to `place_stop_limit_order`,
  with the limit price derived from the caller's stop price: `stop * 0.995` for
  a sell stop, `stop * 1.005` for a buy stop (same convention the crypto bracket
  path already used). The caller's `stop_price` argument is unchanged; the
  resulting order reads back as `type: stop_limit` on reconcile. This is a
  mechanical venue adaptation, not a strategy choice — trail a crypto stop via
  `modify_order` on the existing order, never by placing a second stop.
- **`modify_order` needs the order's OWN symbol to round crypto correctly.**
  Both Alpaca's and IBKR's `modify_order` round stop/limit prices per asset
  class — crypto needs far more decimal precision than a stock's 2dp. Alpaca
  looks up the order's symbol when the caller omits it; IBKR's crypto branch
  passes prices through raw rather than rounding. Before this was fixed in each
  broker independently, an omitted `symbol` on a crypto trail (common — the
  agent often calls `modify_order` with just `order_id`/`stop_price`) rounded a
  price like `1.165` to stock-style 2dp (`1.17`), a large enough jump on a thin
  crypto pair to trigger an immediate stop-out. Always pass `symbol` on a
  crypto `modify_order` call; omitting it risks stock-style rounding.
