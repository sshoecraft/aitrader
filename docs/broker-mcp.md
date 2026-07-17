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

## Client ID allocation (`aitrader/brokers/clientid_lease.py`)
The gateway assigns each connection a unique `clientId` and offers no way to
enumerate which are in use — the only signal is IBKR error 326 on a colliding
connect. Several broker processes can share one gateway (the agent's MCP, an
interactive/ad-hoc MCP, the dashboard API), so `broker()` calls
`acquire_client_id()` before constructing `IBKRBroker` to claim a distinct id.

- **Mechanism:** advisory `flock()` on `STATE_DIR/ibkr-clientids/<base>.lock`.
  A process locks the first free base and holds the fd open for its whole life
  — the kernel releases the lock the instant the holder dies (clean exit,
  crash, `kill -9`), so a lease can never go stale: no PID bookkeeping, no
  reclaim sweep, no PID-reuse race.
- **Roles (deterministic, no env/arg):** the **agent PINS client id 40**
  (`AGENT_CLIENT_ID`), detected by `cwd == settings().run_dir` — the agent's
  broker MCP runs in the run dir, interactive sessions don't. A stable id is
  required because IBKR ties an order's cancel/modify rights to the clientId
  that placed it, so the agent must keep 40 across relays to manage its own
  resting orders. **Interactive/ad-hoc sessions lease from 110+**
  (`INTERACTIVE_BASES = [110, 140, 170, 200, 230, 260, 290]`, spaced 30 so each
  owns a full pool slot: orders=base, status=base+10, data=base+20..27) and
  never touch 40. **The dashboard API hardcodes 80** (`api.py`) and does not
  lease at all — 80-100 is its reserved slot, absent from the pools.
- **Failure handling:** on a successful connect the caller `hold(fd)`s the
  lease for the process lifetime; on a connect failure it `release(fd)`s so the
  base isn't leaked to a process that never actually got online.

## Tools (31)
- Account: `broker_status`, `get_account`, `get_portfolio_history`,
  `get_positions`, `get_currency_balances`
- Orders/exec: `get_orders`, `get_order`, `get_open_orders_for_symbol`,
  `place_market_order`, `place_limit_order`, `place_stop_order`,
  `place_stop_limit_order`, `place_bracket_order`, `modify_order`,
  `cancel_order`, `global_cancel`, `close_position`, `wait_for_fill`,
  `get_fill_activities`, `get_historical_executions`
- Market data: `get_tradeable_assets`, `get_snapshot`, `get_snapshots`,
  `get_bars`, `get_bars_csv`, `get_option_chain`, `get_option_greeks`
  - `get_snapshots` and `get_bars` accept `symbols` as a list OR a
    comma-separated string (`"ES,NQ,GC,CL"`) — split at the MCP boundary so a
    model passing a comma-string doesn't hit a schema error (added 0.5.2; see
    `[[mcp-tools-tolerate-comma-strings]]`).
  - `get_bars_csv` (0.9.0) — same args/routing as `get_bars`, but writes
    long-format rows (symbol, t, o, h, l, c, v) to a CSV on disk and returns
    `{path, count, symbols, columns, as_of}` instead of raw JSON, mirroring
    `get_all_snapshots`/`get_type_snapshots`. Added after an itrader session
    pulled ~400 symbols × 90 days of bars via an unsanctioned side-channel
    (curl'd the dashboard's own internal API instead of a broker MCP tool)
    to avoid dumping raw JSON into context — this tool removes that
    motivation; the constitution's "BROKER/MARKET DATA — ONE PATH" rule
    closes the loophole itself. See `[[market-schedule-broker-scoping]]`'s
    sibling fix for the same session's other finding.
- Time facts: `get_available_types`, `get_market_session`, `get_session_close`
  — holiday- and half-day-aware since package 1.24.0: the session answer is
  gated on the broker's own calendar (Alpaca `/v2/calendar`; IBKR SPY
  liquidHours; MYSE `/clock`), cached per ET date, falling back to weekday
  time math only when the calendar is unreachable. Before 1.24.0 the stock
  answer was pure weekday math and reported holidays (e.g. observed July 4)
  as open. Since 1.25.0 IBKR's forex/futures flags are likewise gated on the
  live trading windows of representative contracts (EUR/USD IDEALPRO; ES
  front month), so CME holiday halts/early closes come from the broker too.
- Currency housekeeping: `flatten_currency`, `flatten_all_residual_currencies`

## Tool return shape convention — never return a bare list
The MCP SDK (fastmcp `_convert_to_content`) renders a Python `list` return as
**one content block PER ELEMENT**, not one block containing an array — so a
1-element list arrives at the model indistinguishable from a bare object (a
1-position `get_positions` looked to the model like "a single object, not a
list"; a 3-position return arrived as 3 loose JSON objects with no array
brackets anywhere). The model cannot tell "one row" from "wrong shape" from
that wire form. Every list-returning MCP tool in this codebase (8 on the
broker server: positions/orders/open-orders-for-symbol/balances/fills/
executions/assets/flatten-results) therefore returns a self-describing dict
instead: `{count, <plural-key>: [...]}` — one content block always, identical
shape at 0/1/many rows, `count == 0` is the only "no rows" form. **Never return
a bare list from an MCP tool** — any new collection-shaped tool follows the
same `{count, key: [...]}` convention. (`get_all_snapshots`/`rank_instruments`
already return dicts, so they were unaffected.)

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

**Mangled order-id tolerance (1.36.4).** A weak local model's tool-call parser
can drop characters from a long hex order id (an AMD stop's `...c5700` was
passed back as `...c700` — one character dropped — locking the position out of
`modify_order`/`cancel_order` for a night: rejected as "badly formed
hexadecimal UUID string" and the wrong id then got re-used verbatim from the
journal every cycle). `resolve_order_id()` in `broker_server.py` is applied in
`modify_order`, `cancel_order`, and `wait_for_fill` before the call reaches the
broker: it strips parser junk (backticks/quotes/trailing dots), and for
UUID-shaped ids (or the journal's bare hex-prefix display form) that don't
match an open order exactly, resolves by UNIQUE first-group prefix (≥8 chars)
against the live `list_all_open_orders()`. All-digit ids (IBKR integer ids) are
never fuzzed — an id like `"35"` must not resolve to `"356"`. Ambiguous or
unknown ids pass through untouched so the broker reports the real error.

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

## Transactions sync — the trade-history ledger (1.32.0)
`sync_transactions(b)` mirrors the broker's fill stream into the journal
`transactions` table so the agent can read its own trade history by symbol +
timeframe (`transactions_read`, on the journal MCP). Same "broker MCP writes
journal.db after a confirmed-good read" precedent as the equity backfill, but
**incremental, not once-per-account**:
- **Trigger:** called from `get_account` + `get_positions` (NOT `broker_status` — the
  readiness poll stays fast), after a successful read. Throttled to ≤1 pass / 45s
  (`_last_tx_sync` monotonic guard) so a reconcile burst doesn't re-hit the broker.
- **Incremental cursor:** pulls `get_fill_activities(after=<start of the latest day we
  already have>)`, so only new fills move; the idempotent `tx_upsert` (PK `fill_id`,
  ON CONFLICT COALESCE) de-dups the overlap. First pass backfills the ~30d the broker
  retains; the table then persists beyond that window.
- **reason (best-effort, degrades to null):** one `get_orders(status="all")` per sync
  gives `order_id → {order_ref, type}`. Entry reason = the agent's own `intent`
  (`orders_of_record` looked up by `order_ref`==`client_tag`); exit reason = a factual
  label off the order type (`stopped out`/`take profit`/`manual`). COALESCE means a
  later sync that can no longer classify an aged-out exit never wipes a found reason.
- **Zero cognition:** raw fills + a factual reason label. No FIFO, no realized-P&L, no
  scoring — the buy/sell sequence itself is what the agent reads.
- **Safety:** wrapped so a sync hiccup never breaks the broker read that invoked it.

## Fuses
- **Paper-only**: the connection's `assert_paper()` runs after every
  connect/reconnect; account id must start with `DU`/`DF` or it raises
  `PaperOnlyError` and refuses. Override only via `AITRADER_ALLOW_LIVE=1`
  (env) → `IBKRBroker(allow_live=True)`. Don't.
- **No notional/BP caps** — the agent owns all sizing.

## Universe snapshot for self-survey (DATA, not cognition)
`get_all_snapshots(asset_type)` (0.8.0) → pulls a raw snapshot for EVERY tradeable
name in a class in ONE call and WRITES it to `{state_dir}/snapshots_{asset}.csv`,
returning `{path, count, asset_type, as_of, columns}` — NOT the rows (a full equity
universe is ~12k names, far too big for context). Columns: `symbol, price, pct_1d,
day_volume, day_notional, rel_vol, day_open, day_high, day_low, prev_close,
prev_volume, prev_notional` (+ the
derived pct_intraday/gap_pct/range_pos/last_trade_ts). It ranks / filters /
scores NOTHING — the whole tape as data (CLAUDE.md §2); the agent reads the file in
its sandbox and ranks it ITSELF (its own liquidity floor, its own metric). Purely
orchestrates the already-routed `get_tradeable_assets` + `get_snapshots`, so it is
cross-asset for free (stock/crypto → Alpaca, forex/futures → IBKR). Note: on an
IEX-feed node `day_volume` is IEX share count (a fraction of consolidated volume),
so a volume floor is calibrated to the data's own distribution.

Previous-session liquidity (1.50.0) — `prev_volume` / `prev_notional`: the
COMPLETED prior session's units traded and its dollars traded (`prev_close ×
prev_volume`, stock/crypto only — futures need the multiplier, forex bars carry
no venue volume). Read off whichever bar IS the previous session's, exactly as
`prev_close` already is: `prevDailyBar` once today's bar has rolled, else the
`dailyBar` itself.

WHY they exist — the survey feed is `delayed_sip` (1.37.3), and its snapshot
`dailyBar` only rolls to today about 15 MINUTES INTO the session (it is a 15-min
delayed tape; before that it still serves the prior session's bar). So through
every pre-market survey and the first minutes of the session, `bar_is_today` is
False for the WHOLE universe, and the 1.48.1 guard correctly blanks
day_volume/day_notional/rel_vol/day_open/high/low and every derived range field
— measured live: 12,968 of 12,968 stock rows blank, and still only 47.5% rolled
17min after the open. That left `pct_1d` as the ONLY usable lens exactly when
the agent forms its morning watchlist — and a raw %-move ranking surfaces
sub-penny names with no fact to judge tradeability by, so the agent invented a
"sub-penny = uninvestable" price proxy of its own (journal id 464). Price is NOT
liquidity and the proxy is backwards in both directions: EOSER at $0.0425 traded
$2.2M the prior session while XOCT at $39.71 traded $36.8k and EVLVW at $0.007
traded $3.9k. `prev_*` is the one liquidity fact that is never blank pre-market
(that session is over), which restores a real discriminator. Still pure DATA per
CLAUDE.md §2 — a raw market fact like `prev_close`, no floor or opinion in code;
the agent chooses what to do with it.

Caveat — `min_volume` floors on `day_volume` (TODAY's), so before the roll it
excludes the entire universe (`excluded.min_volume == universe` means the floor,
not a dead tape). To cut by liquidity pre-market, rank `by` prev_notional /
prev_volume, or read them off a floorless cut's rows (a mover carries the whole
row). Deliberately NOT changed to silently fall back to prev_volume: the agent
journals the floors it used, and a floor whose basis shifts with the clock makes
that record ambiguous.

Row-building guards: a snapshot with no usable price (missing or `<= 0`, e.g.
IBKR's `-1` no-quote sentinel — bit SI futures) is skipped (1.35.0); and a
`latestTrade` dated BEFORE the current daily bar is a stale print, not today's
price — thin crypto crosses carry trades months old (LTC/BTC surveyed as +1175%
"1-day" off an ancient print, DOGE/USDT +238%) — so `price` falls back to the
bar close when the trade predates the bar (1.36.1). Freshness is compared on the
`t` date prefixes both brokers' `normalize_snapshot` shapes carry; a snapshot
without timestamps keeps the old trust-the-trade behavior.

Crypto volume semantics (1.36.2): Alpaca crypto data is Alpaca's OWN venue only
(v1beta3 stopped distributing third-party feeds), and its bars are quote-derived
when no venue trade printed — so zero/blank `day_volume` is normal and the
column is COIN units on a thin venue, NOT the coin's global market liquidity
(the agent was passing crypto "on low volume" off it). `day_volume` keeps its
fractional coin value (the old `int()` floor turned 0.4 BTC into 0 — BTC/USD
surveyed as volume 0), and the tool's docstring plus a `notes` field on every
crypto return spell out the semantics at call time.

`day_notional` (1.40.0) = price × day_volume in DOLLARS, populated for stock
(shares) and crypto (coins) — the cross-row comparable activity fact. Coin
units invert the activity ranking (1.4B PEPE units ≈ $4k while 1.26 BTC ≈
$80k); dollars restore it. Futures rows leave it empty (contracts need the
multiplier — futures rows already carry per-contract `notional` exposure) and
forex has no venue volume: the column never holds a false number. Added after
a transcript-verified afternoon of gemma surveying crypto with stock-template
floors (`min_price=1, min_volume=1e6`) that are structurally empty on venue
coin units — every cycle journaled "None meeting filters" against a tape
showing PEPE +6.7% / AAVE +5.6%. This venue-unit trap is BROKER-GENERIC:
IBKR crypto (live-only, via Paxos/Zero Hash) is also a single venue's tape in
coin units, so the guard keys on asset class, not broker.

1.37.0: `get_all_snapshots()` called with NO arguments pulls EVERY currently-open
type (it calls `get_available_types()` internally; options excluded) and returns
`{as_of, open_types, results: {type: {path, count, ...} | {error}}}` — per-type
errors inline, fail-open. The constitution chains this argless call to step 0
right after `broker_status` (the one call that never erodes), so the whole-tape
pull is infra-guaranteed every cycle instead of model-dependent; the model's
survey burden is reading files that already exist. `get_type_snapshots(asset_type)`
is the explicit single-type mid-cycle refresh (same engine, same columns/caveats).
The payload carries NO ranked names — a pre-ranked list would rebuild the
shortlist trap below.

1.38.0: `rank_instruments(asset_type, n, by, direction, min_price, min_volume,
fresh_only, exclude_held)` — the AGENT-invoked mechanical ranker over the same
CSV: sorts by any column (a raw fact) at parameters the agent chooses per
call, returns the rows inline as JSON. This is NOT the shortlist trap: nothing
is pre-picked — no call, no list; the lens (`by`), floors, depth, and side
(`direction=down` = losers/shorts) are all the agent's arguments, and the CSV
remains for compound cuts. Exists because the local model's sandbox codegen
mangles quoted one-liners (its ranking step failed continuously); derived fact
columns pct_intraday / gap_pct / range_pos (+ consolidated rel_vol) make
pre-move lenses one call. Deliberately not named "top movers" — the old junk
vendor tool had that name, and the neutral name doesn't preach chasing.

1.40.0 observability: the response adds `universe` (CSV row count) and
`excluded` — per-filter removal tallies `{no_data, min_price, min_volume,
stale, held}` (first failing check claims the row) — so `count=0` names its
own cause: a large `excluded.min_volume` reads as "your floor emptied the
list", never "dead tape". Crypto results also carry the venue-coins `notes`
caveat (parity with get_all_snapshots — the newer tool had lost the older
tool's guard). Still zero opinion: tallies and labels are facts about the
call the agent itself parameterized; the constitution (step 3b) is what
requires the FIRST call per type to be floorless and the survey artifact to
quote its top 3 — look first, filter after.

REPLACED (1.34.0) the canned `get_top_movers` / `get_most_actives` screener feeds.
Why: both handed the agent a pre-picked ~15-name shortlist, and the model did
whatever the list returned and nothing else — so the *list* was the strategy.
`get_top_movers` was all penny/warrant pumps (a $0.01→$0.02 warrant is +100%, and
— as this doc already noted — the vendor ranks by % and truncates, so the liquid
leaders never even appear to be filtered); `get_most_actives` was near-static
leveraged ETFs by raw volume. Both opus AND the local model churned the same 2–3
names because that shortlist was the only selection they had. Handing over the
WHOLE universe and pushing the ranking into the agent's sandbox is both more §2-pure
(infra ranks nothing) and the actual fix for the narrow-list churn. Verified live:
`get_all_snapshots("stock")` returned 12,731 names in ~7s; a sandbox `price>5 &
vol>1M` filter surfaced 82 liquid movers (OPEN/HPE/MARA/RIVN/NOK…) the old feeds
buried. See CHANGELOG 1.34.0.

1.49.0: `rank_instruments` gains `lenses` — get SEVERAL ranked cuts in ONE
call instead of one. Format: a comma-string (or list) of `<by>` or
`<by>:<direction>` entries (direction defaults `up`), e.g.
`lenses="pct_1d:up,pct_1d:down,day_notional:up,rel_vol:up"` — same
comma-string-tolerance convention as `symbols` elsewhere (list OR
comma-joined both work; see `[[mcp-tools-tolerate-comma-strings]]`).
Deliberately a FLAT list of short scalar strings rather than nested objects:
the local model's tool-call JSON breaks past short scalar args, which is the
same reason `rank_instruments` exists at all over "rank it in the sandbox".
Runs the shared filter pass (min_price/min_volume/fresh_only/exclude_held)
ONCE, then sorts per lens, returning `{..., unique_movers, lenses: {<lens>:
{count, by, direction, excluded, movers}, ...}}` — `unique_movers` is the
distinct symbol count across every lens combined (a name topping two lenses
counts once), which the constitution's step 3(c) uses to reconcile the GATE
table's row count against the survey. `lenses=None` (default) is the original
single-lens code path, untouched. Constitution step 3(c) makes one
floored, multi-lens call (the four entries above) mandatory every cycle — see
`[[rank-instruments-lenses-and-forced-floor]]`.

1.49.4: `rank_instruments`'s `exclude_held` filter was calling
`broker().get_positions()` fresh on every invocation — not once per cycle, once
per call (THE LOOP's step 3 makes 2-8 of these per cycle across open types). On
IBKR this occasionally fell into `recover_portfolio()`'s multi-second
`ib_async` cache-lag retry loop (up to 5×`asyncio.sleep(1.0)`), paid
independently by every single call. Fixed with `_held_symbols()`, a 60s-TTL
cache in front of the two `broker().get_positions()` call sites inside
`rank_snapshot_csv`/`_rank_multi_lens` ONLY — the public `get_positions` tool
(RECONCILE, order-fill confirmation) still always calls live, so nothing
safety- or fill-critical can observe stale data. A minute-stale held-set can
only affect whether an already-held name also shows up as a ranking
candidate. See CHANGELOG 1.49.4.

1.49.5: added `day_range_pct` (today's high-low spread as % of price) to the
snapshot CSV — itrader self-diagnosed that ranking by raw `pct_1d` structurally
buries mid-caps under penny-stock noise (a $4 name can swing a bigger % than a
$300 one on the same dollar move), and that this exact blindness hid its best
trade of the day (MPC) for five cycles. Same category as pct_intraday/gap_pct/
range_pos (1.40.0) — a cheap derived FACT, not a new tool and not a quality
score: `rank_instruments(by="day_range_pct")` just works, no wiring needed,
and the agent still floors/ranks/decides entirely on its own. See CHANGELOG
1.49.5.

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
