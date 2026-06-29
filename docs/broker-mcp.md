# broker MCP

Execution + market data + broker time facts. **Pure primitives, zero cognition.**
This server OWNS the IBKR connection (the §A.3 job) and optionally fronts it with
a separate market-DATA feed.

- Server: `aitrader/mcp/broker_server.py` (FastMCP, stdio) → `aitrader-broker-mcp`
- Execution driver: `aitrader/brokers/ibkr.py` (`IBKRBroker`), connection in
  `ibkr_connection.py` + `ibkr_pool.py`. See `docs/broker-ibkr.md` for the driver.
- Data feed + routing: `aitrader/brokers/router.py` (`BrokerRouter`) +
  `aitrader/brokers/alpaca.py` (`AlpacaBroker`, data-only). See
  `docs/broker-data-feed.md` for the data/execution split.

## Connection ownership (§A.3)
`IBKRBroker(allow_live=False)` loads host/port/client_id from
`aitrader.credentials` (secrets.toml) and builds three connection pools
(`orders`, `status`, `data`), each an `IBKRConnection` with its **own daemon
thread + asyncio event loop running the ib_async pump**. The MCP calls driver
methods directly; the routing decorator dispatches them onto the right pool, runs
the (async) body on that connection's loop, and returns a plain dict. So tools
are written as simple synchronous calls. Construction + `connect()` happen lazily
on the first tool call; failures (no gateway, bad creds, non-paper account) are
surfaced as `{"connected": false, "error": ...}` by `broker_status`, never crash
the server.

## Tools (31)
- Account: `broker_status`, `get_account`, `get_portfolio_history`,
  `get_positions`, `get_currency_balances`
- Orders/exec: `get_orders`, `get_order`, `get_open_orders_for_symbol`,
  `place_market_order`, `place_limit_order`, `place_stop_order`,
  `place_stop_limit_order`, `place_bracket_order`, `modify_order`,
  `cancel_order`, `global_cancel`, `close_position`, `wait_for_fill`,
  `get_fill_activities`, `get_historical_executions`
- Market data: `get_tradeable_assets`, `get_snapshot`, `get_snapshots`,
  `get_bars`, `get_option_chain`, `get_option_greeks`
  - `get_snapshots` and `get_bars` accept `symbols` as a list OR a
    comma-separated string (`"ES,NQ,GC,CL"`) — split at the MCP boundary so a
    model passing a comma-string doesn't hit a schema error (added 0.5.2; see
    `[[mcp-tools-tolerate-comma-strings]]`).
- Time facts: `get_available_types`, `get_market_session`, `get_session_close`
- Currency housekeeping: `flatten_currency`, `flatten_all_residual_currencies`

## Market-data routing (data_broker) — the §A.3 data/execution split
`broker()` builds the IBKR execution broker and, when `settings.data_broker` is
set, an optional market-DATA broker, then returns a `BrokerRouter` wrapping both.
The router proxies each call: `get_bars`/`get_snapshot`/`get_snapshots`/
`get_tradeable_assets` with an **explicit** `asset_type` in `data_broker_types`
(default `["stock","crypto"]`) go to the data feed; everything else — account,
positions, orders, fills, place/modify/cancel, AND any data call with an
omitted/unsupported `asset_type` — goes to IBKR. Both backends return identical
dict shapes, so the agent's tool surface is unchanged. Why: IBKR's *paper* market
data returns nothing pre-open; Alpaca's tape covers pre/after-hours. Mirrors
`/src/trader` (`broker=ibkr` + `data_broker=alpaca`). A dead data feed degrades to
IBKR-for-data (logged) — it never takes down execution. `broker_status` reports
the active feed as `data_feed` (`"alpaca"` or `"ibkr"`). Full detail:
`docs/broker-data-feed.md`.

## Idempotency
Every `place_*` and `close_position` takes a `client_tag` → stamped on IBKR
`Order.orderRef`; brackets tag all three legs. Order dicts surface it back as
`order_ref`. Pair this with the journal's `order_record` (same tag) so a
relaunched agent recognizes its own in-flight orders (CLAUDE.md §6).

## Equity backfill on first sync (1.1.0)
`maybe_backfill_equity(b)` seeds the journal's `equity_snapshots` from the broker's
own `get_portfolio_history` (longest daily window) **once per account**, so a fresh
install's dashboard curve + `day_pl` aren't empty until the recorder accumulates
points. Pure infra recording (no trade/decision). Wiring:
- **Trigger:** called from `broker_status`/`get_account`/`get_positions` only **after**
  a successful data read — a connected-but-not-serving broker (IBKR mid-login) never
  triggers it.
- **Idempotency:** a state-dir semaphore `.equity_backfilled`, written only after a
  successful pass (so it runs once). It **skips any `ts` already in the table**, so the
  broker's daily history and the recorder's 15-min points compose without duplicates — a
  recorder tick racing ahead of the first reconcile can't suppress the deep history.
- **Safety:** never raises (a backfill hiccup can't break the broker call); on failure
  the semaphore stays unset to retry. Timestamps go through `timeutil.epoch_to_iso`
  (`+00:00` form `equity_read` sorts on — see the 0.15.3 ordering fix). `journal_db`
  stays pure storage (only added `equity_count`).
- Trade history needs no backfill (`/trades` reads fills live); rationale can't be
  reconstructed (agent intent).

## Fuses
- **Paper-only**: the connection's `assert_paper()` runs after every
  connect/reconnect; account id must start with `DU`/`DF` or it raises
  `PaperOnlyError` and refuses. Override only via `AITRADER_ALLOW_LIVE=1`
  (env) → `IBKRBroker(allow_live=True)`. Don't.
- **No notional/BP caps** — the agent owns all sizing.

## Factual movers feeds (DATA, not cognition)
Two vendor-published rankings, each ranked by a RAW market fact (CLAUDE.md §2
allows these — like a quote, a fact about price/volume):
- `get_top_movers(top_n)` → top % gainers/losers across the whole US tape,
  ranked by raw % change. Structurally dominated by low-float pump stocks: a
  $0.01→$0.02 warrant is +100% and crowds out the large-cap up 2%. So this feed
  CANNOT surface the liquid leaders driving an index — and a liquidity filter
  wouldn't help, because the vendor ranks by % and truncates (`top` caps ~50);
  the leaders never make the returned list to be filtered. Keep it for what it
  is: where small-cap/penny momentum shows up.
- `get_most_actives(top_n, by)` (1.20.0) → most-active stocks ranked by raw
  `volume` (shares) or `trades` (count). This is the LIQUID, large-cap side of
  the tape the % feed buries — the names the rally actually runs on. Returns
  `{actives:[{symbol, volume, trade_count}], by, as_of}`; carries NO price/%/
  direction (most-active ≠ moving up). The agent pulls bars/snapshots on these
  and decides what's moving with strength itself.

Both are pure pass-throughs to Alpaca's `ScreenerClient` and are Alpaca-only
(the MCP wrapper returns a graceful `error` if the node's feed lacks them).

## Deliberately absent (would be cognition)
No screen/score/signal that decides what is *good* — no edge/quality shortlist,
no confidence number, no buy/sell or indicator-gate. The movers feeds above rank
by a raw FACT (% move, volume), not by edge; that's the line. No "get news"
(native to Claude). `get_tradeable_assets` returns the raw LIST of what exists;
surveying it is the agent's job.

## Status
Built and **LIVE-verified (2026-06-15)** against paper account `DU0000000` via the
co-located gateway on this node (`127.0.0.1:4002`): `broker_status` →
`{connected: true, account: 'DU0000000', paper: true}`; account snapshot,
`available_types`, `market_session`, positions/orders all return; paper fuse
confirms `DU0000000` at the connection layer. Also driven end-to-end by `claude -p`
through the harness (reconcile + journal, rc=0). The gateway server itself lives in
the bundled `gateway/` subdir (IBC + GW, headless Xvfb, `ibgateway.service`; set up
by `./install.sh --broker ibkr`); this MCP is a pure client that dials
`ibkr_host:ibkr_port`.

**Data feed added + LIVE-verified (2026-06-17):** Alpaca data broker fronts
stock/crypto. Verified at 08:42 ET (pre-market) — `get_snapshot('AAPL')` returned
a live `latestTrade.p=299.26` where IBKR's paper feed returns empty pre-open;
daily SIP bars, BTC/USD hourly bars, and the 73-coin crypto universe all populate;
routing confirmed (stock/crypto data→Alpaca, account/orders/fills + no-asset_type
data→IBKR); Alpaca execution methods refuse. See `docs/broker-data-feed.md`.
