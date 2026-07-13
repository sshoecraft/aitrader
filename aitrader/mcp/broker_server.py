"""broker MCP — execution + market data + broker time facts (BRIEF §A.4.1).

This server OWNS the execution-broker connection (the §A.3 job). The EXECUTION
backend is settings.broker ∈ {ibkr, alpaca, myse} (default ibkr); when
settings.data_broker is set, a separate market-DATA broker fronts it (see
aitrader/brokers/router.py). The MCP calls the driver's primitive methods
directly — they return plain dicts; IBKR blocks via its connection pools.

PURE PRIMITIVES, ZERO cognition. Every tool answers a factual question or
performs a mechanical action. No EDGE screen, score, or buy/sell signal here —
that judgment is the agent's. `get_all_snapshots` hands over the WHOLE tradeable
universe's raw price+volume as data (CLAUDE.md §2) — it reports what *is* and ranks
NOTHING; the agent surfaces the movers by ranking that file itself in the sandbox.
No pre-chosen shortlist, no score, no buy/sell signal here.

Fuses: the connection enforces PAPER-ONLY (account id must start with DU/DF)
unless settings.toml sets allow_live = true (don't). No notional/buying-power caps.

Run: aitrader-broker-mcp  (stdio)
"""

__version__ = "0.10.2"

import os
import sys
import time
from datetime import date

from mcp.server.fastmcp import FastMCP

from aitrader import journal_db
from aitrader.asset_types import AssetType, clean_symbol
from aitrader.brokers.ibkr import IBKRBroker
from aitrader.brokers.router import BrokerRouter
from aitrader.brokers.clientid_lease import acquire_client_id, hold, release
from aitrader.config import settings
from aitrader.timeutil import epoch_to_iso, utcnow_iso

mcp = FastMCP("aitrader-broker")

_broker = None
# Paper-only fuse override — set allow_live = true in settings.toml only if you
# truly mean to leave paper. Default false.
ALLOW_LIVE = settings().allow_live


def build_data_broker():
    """Build + connect the optional market-DATA broker (settings.data_broker).

    Returns a connected data Broker, or None if data_broker is unset. Execution
    is ALWAYS IBKR; the data broker only fronts stock/crypto bars/snapshots
    (see aitrader/brokers/router.py). Raises on a configured-but-unreachable
    feed — the caller degrades to IBKR-only data rather than dying."""
    name = settings().data_broker
    if not name:
        return None
    if name == "alpaca":
        from aitrader.brokers.alpaca import AlpacaBroker
        from aitrader.credentials import load_alpaca_credentials
        api_key, secret_key = load_alpaca_credentials()
        b = AlpacaBroker(api_key, secret_key, paper=True,
                         data_feed=settings().alpaca_data_feed)
        b.connect()
        return b
    raise ValueError(f"Unknown data_broker: {name!r} (expected 'alpaca' or unset)")


def build_execution_broker():
    """Build + connect the EXECUTION broker per settings.broker ∈ {ibkr, alpaca,
    myse}. IBKR claims a clientId flock lease (held for this process's life;
    released on connect-failure); alpaca/myse just connect. Paper-only fuse per
    backend: IBKR refuses a non-DU/DF account unless allow_live; Alpaca connects
    to the paper endpoint unless allow_live."""
    name = settings().broker or "ibkr"

    if name == "ibkr":
        # Claim a unique clientId base via the cross-process flock lease, so this
        # broker coexists with the agent's MCP / the API on the one gateway (the
        # gateway can't tell us which ids are free). The agent pins 40; others
        # lease 110/140/… Released the instant this process exits.
        client_id, fd = acquire_client_id()
        try:
            # orders=1: a single orderId counter → globally-unique order IDs (no
            # cross-connection collision). data=8 keeps parallel bar fetches fast.
            b = IBKRBroker(client_id=client_id, allow_live=ALLOW_LIVE,
                           pool_sizes={"orders": 1, "status": 1, "data": 8})
            b.connect()
        except Exception:
            release(fd)  # connect failed — free the base, don't leak the lease
            raise
        hold(fd)         # connected — keep the lease for this process's life
        return b

    if name == "alpaca":
        from aitrader.brokers.alpaca import AlpacaBroker
        from aitrader.credentials import load_alpaca_credentials
        api_key, secret_key = load_alpaca_credentials()
        # paper=(not allow_live) is the paper-only fuse for the Alpaca backend.
        b = AlpacaBroker(api_key, secret_key, paper=not ALLOW_LIVE,
                         data_feed=settings().alpaca_data_feed)
        b.connect()
        return b

    if name == "myse":
        from aitrader.brokers.myse import MYSEBroker
        from aitrader.credentials import load_myse_credentials
        creds = load_myse_credentials()
        b = MYSEBroker(host=creds["host"], api_key=creds["api_key"])
        b.connect()
        return b

    raise ValueError(f"Unknown broker: {name!r} (expected ibkr|alpaca|myse)")


def broker():
    """Lazy singleton. Builds the execution broker (settings.broker) and, when
    settings.data_broker is set, a market-DATA broker in front of it. Returns a
    BrokerRouter: execution/account/orders/fills go to the execution broker;
    stock/crypto market data go to the data broker when configured. With NO data
    broker, the execution broker serves data too (the pure-Alpaca case). Raises
    if the execution broker can't connect or its account isn't paper."""
    global _broker
    if _broker is None:
        execution = build_execution_broker()

        # Optional SEPARATE market-data feed. A data-broker failure must NOT take
        # down execution: degrade to execution-broker-for-data and keep trading.
        data = None
        try:
            data = build_data_broker()
        except Exception as exc:
            import sys
            print(f"WARNING: data_broker unavailable, falling back to the "
                  f"execution broker for data: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)

        _broker = BrokerRouter(execution, data=data,
                               data_broker_types=settings().data_broker_types)
    return _broker


_backfill_done = False  # process-level: once handled, skip the semaphore stat


def maybe_backfill_equity(b):
    """Once per account, seed the journal equity curve from the broker's OWN
    portfolio history — so a fresh install's dashboard curve + day_pl aren't empty
    until the recorder accumulates points. Pure infra recording, no trade/decision
    (CLAUDE.md §2).

    Idempotency: a state-dir semaphore (`.equity_backfilled`), written only after a
    successful pass — so it runs exactly once per account. It SKIPS any timestamp the
    live recorder already wrote, so the broker's daily history and the recorder's
    recent 15-min points compose without duplicates (and a recorder tick racing in
    ahead of the first reconcile can't suppress the deep history). MUST be called only
    AFTER a successful broker data read (so a connected-but-not-serving broker can't
    trigger it), and MUST NOT raise — a hiccup cannot break the broker call that
    invoked it."""
    global _backfill_done
    if _backfill_done:
        return
    try:
        sem = os.path.join(settings().state_dir, ".equity_backfilled")
        if os.path.exists(sem):
            _backfill_done = True
            return
        conn = journal_db.get_db(settings().journal_db)
        try:
            # Backfill the broker's OWN equity history (longest daily window),
            # skipping any ts the live recorder already wrote so the two sources
            # compose without duplicates. A few recorder points racing in ahead of
            # the first reconcile must NOT suppress the deep history.
            seen = journal_db.equity_ts_set(conn)
            hist = b.get_portfolio_history(period="1A", timeframe="1D") or {}
            ts_list = hist.get("timestamp") or []
            eq_list = hist.get("equity") or []
            pl_list = hist.get("profit_loss") or []
            written = skipped = 0
            for i, (epoch, eq) in enumerate(zip(ts_list, eq_list)):
                if eq is None:
                    continue
                iso = epoch_to_iso(epoch)
                if iso in seen:
                    skipped += 1
                    continue
                pl = pl_list[i] if i < len(pl_list) else None
                journal_db.equity_write(conn, ts=iso, equity=float(eq),
                                        realized_pnl=pl, notes="broker backfill")
                written += 1
            _stamp(sem, f"backfilled {written} rows from {b.execution.name}"
                        f" (skipped {skipped} already present)")
            _backfill_done = True
        finally:
            conn.close()
    except Exception as exc:
        # leave the semaphore + flag unset → retried on the next successful data call
        print(f"equity backfill skipped (will retry): {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)


def _stamp(path, note):
    """Write the backfill semaphore (self-documenting: when + what)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f"{utcnow_iso()}  {note}\n")


_last_tx_sync = 0.0  # monotonic seconds of the last transactions sync
TX_SYNC_MIN_INTERVAL = 45.0  # throttle: at most one fill sync per this many seconds


def _classify_exit(order):
    """Factual exit-mechanism label from the order TYPE — never an opinion.
    A stop is a stop-out; a resting sell limit is a take-profit; anything else is
    a manual/market close. This reports HOW the exit fired, not whether it was
    good. Returns None if the order is unknown."""
    if not order:
        return None
    otype = str(order.get("type") or order.get("order_type") or "").lower()
    if "stop" in otype:      # stop / stop_limit / trailing_stop
        return "stopped out"
    if "limit" in otype:
        return "take profit"
    return "manual"


def sync_transactions(b):
    """Sync the broker's fill stream into the journal `transactions` ledger so the
    agent can read its own trade history by symbol + timeframe. Pure infra
    recording (a fill is a FACT, like a quote) — ZERO cognition, no P&L.

    Unlike the one-time equity backfill this runs INCREMENTALLY every reconcile,
    so it is throttled to one pass per TX_SYNC_MIN_INTERVAL and pulls only fills
    at/after the newest it already has (the idempotent upsert de-dups the small
    overlap). First pass backfills the ~30d the broker retains.

    `reason` is attached best-effort and degrades to null — never blocks:
      - the agent's own recorded intent (orders_of_record.intent, joined via the
        order's client_tag) when present — its prose in its own words, or
      - a factual exit label read off the order type (stopped out / take profit /
        manual) for sells.
    MUST be called only AFTER a confirmed-good broker data read, and MUST NOT
    raise — a sync hiccup cannot break the broker call that invoked it."""
    global _last_tx_sync
    now_mono = time.monotonic()
    if now_mono - _last_tx_sync < TX_SYNC_MIN_INTERVAL:
        return
    try:
        conn = journal_db.get_db(settings().journal_db)
        try:
            latest = journal_db.tx_latest_time(conn)
            # Re-pull from the start of the latest day we have (bounded overlap),
            # or the broker default (~30d) on first run; the upsert de-dups.
            after = latest[:10] if latest else None
            fills = b.get_fill_activities(after=after) or []
            if not fills:
                _last_tx_sync = now_mono
                return
            # One orders read per sync (not per fill) → client_tag + type per order.
            try:
                orders = b.get_orders(status="all", limit=500) or []
            except Exception:
                orders = []
            by_id = {str(o.get("id")): o for o in orders if o.get("id") is not None}

            now_iso = utcnow_iso()
            written = 0
            for f in fills:
                fill_id = f.get("id")
                symbol = f.get("symbol")
                side = f.get("side")
                if not fill_id or not symbol or not side:
                    continue
                qty = f.get("qty") or f.get("quantity")
                price = f.get("price") or f.get("fill_price")
                txn_time = (f.get("transaction_time") or f.get("time")
                            or f.get("executed_at"))
                if qty is None or price is None or not txn_time:
                    continue
                order_id = f.get("order_id")
                order = by_id.get(str(order_id)) if order_id is not None else None
                order_ref = order.get("order_ref") if order else None

                # reason: the agent's own intent first, else the factual exit label.
                reason = None
                if order_ref:
                    rec = journal_db.order_get(conn, order_ref)
                    if rec and rec.get("intent"):
                        reason = rec.get("intent")
                if reason is None and str(side).lower() == "sell":
                    reason = _classify_exit(order)

                journal_db.tx_upsert(
                    conn, now_iso, fill_id=str(fill_id), symbol=symbol,
                    side=side, qty=float(qty), price=float(price),
                    transaction_time=txn_time, order_id=(str(order_id) if order_id else None),
                    order_ref=order_ref, fill_type=f.get("type"),
                    asset_type=f.get("asset_type"), reason=reason)
                written += 1
            _last_tx_sync = now_mono
        finally:
            conn.close()
    except Exception as exc:
        # leave _last_tx_sync unset → retried on the next successful data call
        print(f"transactions sync skipped (will retry): {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)


def clean_symbols(x):
    """Sanitize a symbols arg that may be a list OR a comma-separated string;
    returns a clean list with empties dropped."""
    if isinstance(x, str):
        x = x.split(",")
    return [clean_symbol(s) for s in x if clean_symbol(s)]


def parse_asset_type(s):
    """Convert a string asset type to AssetType, or None. Accepts the enum
    values: stock, crypto, forex, futures, options."""
    if s is None:
        return None
    if isinstance(s, AssetType):
        return s
    return AssetType(clean_symbol(str(s)).lower())


# ── connection / account ──────────────────────────────────────────────────

@mcp.tool()
def broker_status() -> dict:
    """Connect if needed and report connection health + the account id (which
    encodes paper-vs-live: DU/DF = paper). Call this first to verify the broker
    is reachable before relying on other tools."""
    try:
        b = broker()
        acct = b.get_account()
        acct_id = acct.get("account") or acct.get("account_id") or acct.get("id")
        maybe_backfill_equity(b)  # one-time, only after this confirmed-good data read
        return {"connected": True, "account": acct_id,
                # Paper is guaranteed whenever the live fuse is off — the adapter
                # refuses a non-paper account unless allow_live. Broker-agnostic
                # (do NOT infer paper from an IBKR-only DU/DF account-id prefix —
                # that mislabels e.g. an Alpaca paper account 'PA…' as live).
                "paper": not ALLOW_LIVE,
                "allow_live": ALLOW_LIVE,
                # The execution broker (account/orders/fills), and the broker
                # serving stock/crypto market data. With no separate data_broker
                # the execution broker serves data too, so data_feed == broker.
                "broker": b.execution.name,
                "data_feed": b.data_feed_name()}
    except Exception as exc:
        return {"connected": False, "error": f"{type(exc).__name__}: {exc}"}


@mcp.tool()
def get_account() -> dict:
    """Account snapshot: cash, equity, buying power, portfolio value, account id."""
    b = broker()
    acct = b.get_account()
    maybe_backfill_equity(b)  # one-time, only after this confirmed-good data read
    sync_transactions(b)      # incremental (throttled), after this good data read
    return acct


@mcp.tool()
def get_portfolio_history(period: str = "1D", timeframe: str = "1D",
                          date_end: str = None) -> dict:
    """Portfolio equity history. period e.g. '1D','1W','1M'; timeframe e.g.
    '1Min','1D'; date_end optional 'YYYY-MM-DD' anchor."""
    return broker().get_portfolio_history(period=period, timeframe=timeframe, date_end=date_end)


@mcp.tool()
def get_positions() -> dict:
    """All open positions (broker truth) as {count, positions: [...]} — the
    same shape at 0, 1, or many. Each position: symbol, qty, avg price, market
    value, unrealized P&L, asset class."""
    b = broker()
    pos = b.get_positions()
    maybe_backfill_equity(b)  # one-time, only after this confirmed-good data read
    sync_transactions(b)      # incremental (throttled), after this good data read
    return {"count": len(pos), "positions": pos}


@mcp.tool()
def get_currency_balances() -> dict:
    """Non-USD currency cash balances (forex residue) as {count, balances}."""
    bals = broker().get_currency_balances()
    return {"count": len(bals), "balances": bals}


# ── orders & execution ────────────────────────────────────────────────────

@mcp.tool()
def get_orders(status: str = None, after: str = None, until: str = None,
               limit: int = None) -> dict:
    """List orders with optional filters (status/after/until/limit) as
    {count, orders: [...]} — the same shape at 0, 1, or many. Each order
    surfaces 'order_ref' = your client tag, for idempotent reconcile."""
    orders = broker().get_orders(status=status, after=after, until=until, limit=limit)
    return {"count": len(orders), "orders": orders}


@mcp.tool()
def get_order(order_id: str) -> dict:
    """Get a single order by broker order id."""
    return broker().get_order(order_id)


@mcp.tool()
def get_open_orders_for_symbol(symbol: str) -> dict:
    """Open orders for one symbol as {count, orders: [...]}."""
    orders = broker().get_open_orders_for_symbol(clean_symbol(symbol))
    return {"count": len(orders), "orders": orders}


@mcp.tool()
def place_market_order(symbol: str, qty: float, side: str, tif: str = "day",
                       asset_type: str = None, client_tag: str = None) -> dict:
    """Place a market order. side = 'buy'|'sell'. Pass a DETERMINISTIC
    client_tag (your idempotency key) — it is stamped on the order's ref so a
    relaunched you recognizes it. Record the tag in the journal first."""
    return broker().place_market_order(clean_symbol(symbol), qty, side, tif=tif,
                                       asset_type=parse_asset_type(asset_type),
                                       client_tag=client_tag)


@mcp.tool()
def place_limit_order(symbol: str, qty: float, side: str, limit_price: float,
                      tif: str = "day", asset_type: str = None,
                      outside_rth: bool = False, client_tag: str = None) -> dict:
    """Place a limit order at limit_price. side='buy'|'sell'. client_tag =
    idempotency key (see place_market_order)."""
    return broker().place_limit_order(clean_symbol(symbol), qty, side, limit_price, tif=tif,
                                      asset_type=parse_asset_type(asset_type),
                                      outside_rth=outside_rth, client_tag=client_tag)


@mcp.tool()
def place_stop_order(symbol: str, qty: float, side: str, stop_price: float,
                     tif: str = "day", asset_type: str = None,
                     client_tag: str = None) -> dict:
    """Place a stop-market order triggering at stop_price."""
    return broker().place_stop_order(clean_symbol(symbol), qty, side, stop_price, tif=tif,
                                     asset_type=parse_asset_type(asset_type),
                                     client_tag=client_tag)


@mcp.tool()
def place_stop_limit_order(symbol: str, qty: float, side: str, stop_price: float,
                           limit_price: float, tif: str = "day",
                           asset_type: str = None, outside_rth: bool = False,
                           client_tag: str = None) -> dict:
    """Place a stop-limit order (stop trigger + limit)."""
    return broker().place_stop_limit_order(clean_symbol(symbol), qty, side, stop_price, limit_price,
                                           tif=tif, asset_type=parse_asset_type(asset_type),
                                           outside_rth=outside_rth, client_tag=client_tag)


@mcp.tool()
def place_bracket_order(symbol: str, qty: float, side: str, limit_price: float,
                        stop_loss: float, take_profit: float, tif: str = "day",
                        stop_limit_price: float = None, client_tag: str = None) -> dict:
    """Place a bracket (entry limit + stop-loss + take-profit). All three legs
    carry your client_tag. The bracket prices are YOUR chosen numbers — this is
    plumbing, not a strategy; nothing here computes a stop or target for you."""
    return broker().place_bracket_order(clean_symbol(symbol), qty, side, limit_price, stop_loss,
                                        take_profit, tif=tif,
                                        stop_limit_price=stop_limit_price,
                                        client_tag=client_tag)


def resolve_order_id(order_id):
    """Weak local models mangle long hex ids — a dropped char turned the AMD
    stop's ...c5700 into ...c700 and locked the position out of modify/cancel
    for a whole night. Strip parser junk (backticks/quotes/trailing dots); if a
    UUID-shaped id doesn't match an open order exactly, resolve it by UNIQUE
    first-group prefix against the live open orders. Non-UUID ids (IBKR ints)
    and unresolvable ids pass through so the broker reports the real error."""
    oid = str(order_id).strip().strip('`"\'').rstrip('.')
    # Fuzzy-resolve only UUID-shaped ids ("-") or the journal's bare hex-prefix
    # display form (has a-f, so it can never be an IBKR integer id).
    if "-" not in oid and not any(c in "abcdef" for c in oid.lower()):
        return oid
    try:
        open_ids = [str(o.get("id")) for o in broker().list_all_open_orders()]
    except Exception:
        return oid
    if oid in open_ids:
        return oid
    head = oid.split("-", 1)[0]
    if len(head) >= 8:
        matches = [i for i in open_ids if i.startswith(head)]
        if len(matches) == 1:
            return matches[0]
    return oid


@mcp.tool()
def modify_order(order_id: str, stop_price: float = None, limit_price: float = None,
                 qty: float = None, symbol: str = None) -> dict:
    """Modify an existing order's price(s) and/or qty in place."""
    return broker().modify_order(resolve_order_id(order_id), stop_price=stop_price,
                                 limit_price=limit_price, qty=qty, symbol=symbol)


@mcp.tool()
def cancel_order(order_id: str, timeout: float = 8, poll_interval: float = 0.5) -> dict:
    """Cancel an order by id; waits up to timeout for confirmation."""
    return broker().cancel_order(resolve_order_id(order_id), timeout=timeout,
                                 poll_interval=poll_interval)


@mcp.tool()
def global_cancel() -> dict:
    """Cancel ALL open orders at the broker. Blunt instrument — your choice."""
    return broker().global_cancel()


@mcp.tool()
def close_position(symbol: str, client_tag: str = None) -> dict:
    """Flatten a position by submitting the offsetting order. client_tag stamps
    the closing order's ref."""
    return broker().close_position(clean_symbol(symbol), client_tag=client_tag)


@mcp.tool()
def wait_for_fill(order_id: str, timeout: float = 300, poll_interval: float = 2) -> dict:
    """Block (up to timeout) until an order fills; returns the filled order dict
    or null. Lives here (not the scheduler) because polling needs the broker
    connection this server owns."""
    return broker().wait_for_fill(resolve_order_id(order_id), timeout=timeout,
                                  poll_interval=poll_interval)


@mcp.tool()
def get_fill_activities(after: str = None) -> dict:
    """Recent fills/executions as {count, fills: [...], since}.

    after: ISO timestamp; DEFAULT = the last 4 days. Reconcile needs the fills
    since your last wake, not the account's life story — an unbounded pull
    overflows into a spill file you then have to read back. For deeper
    history use transactions_read (the ledger keeps everything, with reasons)
    or pass an explicit earlier `after`."""
    if not after:
        import datetime
        after = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=4)).isoformat()
    fills = broker().get_fill_activities(after=after)
    return {"count": len(fills), "fills": fills, "since": after}


@mcp.tool()
def get_historical_executions(symbol: str = None, side: str = None, days: int = 7) -> dict:
    """Historical executions up to `days` back (IBKR reqExecutions) as
    {count, executions: [...]}."""
    ex = broker().get_historical_executions(symbol=clean_symbol(symbol), side=side, days=days)
    return {"count": len(ex), "executions": ex}


# ── market data ───────────────────────────────────────────────────────────

@mcp.tool()
def get_tradeable_assets(asset_type: str = "stock") -> dict:
    """The LIST of tradeable symbols for an asset class — what exists, NOT a
    ranked or filtered shortlist. Surveying/filtering it is your job.

    Source: Alpaca for stock/crypto when a data feed is configured (its full
    universe), else IBKR. Note: a symbol in Alpaca's list is not guaranteed
    tradeable on IBKR (the execution venue); confirm with a snapshot/order.
    Returns {count, assets: [...]}."""
    assets = broker().get_tradeable_assets(asset_type=parse_asset_type(asset_type) or AssetType.STOCK)
    return {"count": len(assets), "assets": assets}


@mcp.tool()
def get_snapshot(symbol: str, asset_type: str = None) -> dict:
    """Current quote/snapshot for one symbol (latestTrade/dailyBar/prevDailyBar).

    For a LIVE stock/crypto quote incl. pre/after-hours, pass
    asset_type='stock' or 'crypto' → routes to the Alpaca feed. WITHOUT
    asset_type it goes to IBKR, whose paper feed returns empty/zeros pre-open.
    Same dict shape either way, so always pass asset_type for stocks/crypto."""
    return broker().get_snapshot(clean_symbol(symbol), asset_type=parse_asset_type(asset_type))


@mcp.tool()
def get_snapshots(symbols: list | str, asset_type: str = None) -> dict:
    """Current snapshots for several symbols -> {symbol: snapshot}.

    `symbols` may be a list (["ES","NQ"]) OR a comma-separated string
    ("ES,NQ,GC,CL") — both work; the string is split on commas.

    For LIVE stock/crypto quotes incl. pre/after-hours, pass asset_type='stock'
    or 'crypto' → Alpaca feed. WITHOUT asset_type it goes to IBKR (empty/zeros
    pre-open on paper). Same shape either way, so always pass asset_type."""
    symbols = clean_symbols(symbols)
    return broker().get_snapshots(symbols, asset_type=parse_asset_type(asset_type))


@mcp.tool()
def get_bars(symbols: list, asset_type: str = None, timeframe: str = "1Day",
             start: str = None, limit: int = None) -> dict:
    """Historical bars -> {symbol: [bar,...]}. timeframe e.g. '1Min','5Min',
    '1Hour','1Day'. Raw OHLCV — compute whatever you want from it in the sandbox.

    For LIVE stock/crypto bars incl. pre/after-hours, pass asset_type='stock' or
    'crypto' → routes to the Alpaca full-tape feed. WITHOUT asset_type it goes to
    IBKR, whose paper feed returns nothing pre-open. Bar shape (t/o/h/l/c/v) is
    identical regardless of source, so always pass asset_type for stocks/crypto."""
    return broker().get_bars(clean_symbols(symbols), asset_type=parse_asset_type(asset_type),
                             timeframe=timeframe, start=start, limit=limit)


@mcp.tool()
def get_bars_csv(symbols: list, asset_type: str = None, timeframe: str = "1Day",
                  start: str = None, limit: int = None) -> dict:
    """Bars for MANY symbols -> ONE CSV on disk, returned as {path, count, symbols,
    columns, as_of} instead of raw JSON. Use this instead of get_bars whenever you
    want more than a handful of symbols — a few dozen names x 90 days of daily
    bars is enough JSON to blow out your context; this writes the same data to
    disk and hands you a path + row count, the same pattern as
    get_all_snapshots/get_type_snapshots. Long format, one row per symbol per
    bar: symbol, t, o, h, l, c, v.

    Same routing/arguments as get_bars: pass asset_type='stock'/'crypto' for the
    live Alpaca feed; an omitted asset_type goes to IBKR. Read it in the sandbox:
        import pandas as pd
        df = pd.read_csv(PATH)
        df[df.symbol == 'XOM'].sort_values('t')
    """
    import csv
    data = broker().get_bars(clean_symbols(symbols), asset_type=parse_asset_type(asset_type),
                             timeframe=timeframe, start=start, limit=limit)
    cols = ["symbol", "t", "o", "h", "l", "c", "v"]
    rows = []
    for sym, bars in (data or {}).items():
        for bar in (bars or []):
            rows.append({
                "symbol": sym,
                "t": bar.get("t", ""),
                "o": bar.get("o", ""),
                "h": bar.get("h", ""),
                "l": bar.get("l", ""),
                "c": bar.get("c", ""),
                "v": bar.get("v", ""),
            })
    os.makedirs(settings().state_dir, exist_ok=True)
    path = os.path.join(settings().state_dir, "bars.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return {"path": path, "count": len(rows), "symbols": len(data or {}),
            "columns": cols, "timeframe": timeframe, "as_of": utcnow_iso()}


def snapshot_type_to_csv(asset_type: str = "stock") -> dict:
    """Shared engine: one asset type's whole-universe snapshot -> CSV on disk.
    Returns {path, count, asset_type, as_of, columns[, notes]}. Serves both
    get_all_snapshots (argless = every open type) and get_type_snapshots."""
    import csv
    at = parse_asset_type(asset_type) or AssetType.STOCK
    b = broker()
    universe = b.get_tradeable_assets(asset_type=at)
    symbols = [a["symbol"] for a in universe if a.get("symbol")]
    # Stocks survey on the consolidated (15-min delayed) tape so volume and
    # traded-today mean the real market, not IEX's ~4% keyhole; single-symbol
    # quotes/bars stay real-time on alpaca_data_feed.
    kw = {"feed": settings().alpaca_survey_feed} if at == AssetType.STOCK else {}
    snaps = b.get_snapshots(symbols, asset_type=at, **kw)

    cols = ["symbol", "price", "pct_1d", "day_volume", "day_notional", "rel_vol",
            "day_open", "day_high", "day_low", "prev_close",
            "pct_intraday", "gap_pct", "range_pos", "last_trade_ts"]
    rows = []
    today_str = utcnow_iso()[:10]
    for sym, s in snaps.items():
        db = s.get("dailyBar") or {}
        pdb = s.get("prevDailyBar") or {}
        lt = s.get("latestTrade") or {}
        lt_t, db_t = str(lt.get("t") or ""), str(db.get("t") or "")

        # Alpaca's snapshot dailyBar rolls to the new session on the symbol's
        # FIRST consolidated print of that session, not at the bell — right
        # after the open (or in extended hours) db can still BE the prior
        # session while latestTrade is already live. A bar dated before today
        # is not today's bar: its o/h/l/v are unknown-for-today (NOT
        # yesterday's relabeled as today's), and ITS close — not
        # prevDailyBar's, which would then be two sessions back — is the
        # correct previous close. Emitting blank beats emitting yesterday's
        # data as today's: downstream fields go empty instead of confidently
        # wrong (day_high/day_low no longer disagree with a live price).
        bar_is_today = bool(db_t) and db_t[:10] == today_str
        if bar_is_today:
            day_o, day_h, day_l, dvol = db.get("o"), db.get("h"), db.get("l"), db.get("v")
            prev_c = pdb.get("c")
        else:
            day_o = day_h = day_l = dvol = None
            prev_c = db.get("c")

        price = lt.get("p") or db.get("c")
        # A thin pair's latestTrade can be months stale (LTC/BTC surveyed as
        # +1175% "1-day" off an ancient print): a trade dated before the current
        # daily bar is not today's price — use the bar close instead.
        if lt_t and db_t and lt_t[:10] < db_t[:10] and db.get("c"):
            price = db.get("c")
        if price is None or float(price) <= 0:
            continue
        # Even once the bar HAS rolled to today, the vendor's own dailyBar
        # aggregate for the in-progress session can lag the very latest tick
        # by a few seconds (worst on thin/leveraged/preferred names) — so a
        # genuinely-live price can still print outside [day_low, day_high]
        # for a moment. We already know this print is today's (bar_is_today
        # above, plus the staleness guard just before this); today's true
        # high is therefore AT LEAST this price and today's true low AT MOST
        # this price — not a guess, just carrying a fact we already have.
        if bar_is_today:
            price_f = float(price)
            if day_h is not None and price_f > day_h:
                day_h = price_f
            if day_l is not None and price_f < day_l:
                day_l = price_f
        pvol = pdb.get("v")
        # Crypto venue volume is fractional COINS (e.g. 0.4 BTC) — int() floors
        # it to 0; keep the fraction so a thin venue reads as thin, not absent.
        day_volume = "" if not dvol else (
            round(dvol, 6) if at == AssetType.CRYPTO else int(dvol))
        rows.append({
            "symbol": sym,
            "price": round(float(price), 6),
            "pct_1d": round((float(price) - prev_c) / prev_c * 100.0, 3) if prev_c else "",
            "day_volume": day_volume,
            # Dollars actually traded (price × units): true for stock (shares)
            # and crypto (coins), and comparable across rows where raw units
            # are not (1.4B PEPE units ≈ $4k; 1.26 BTC ≈ $80k). Futures need
            # the contract multiplier (their rows carry `notional` exposure
            # instead) and forex bars have no venue volume — both stay empty
            # rather than hold a false number.
            "day_notional": (round(float(price) * dvol, 2)
                             if (dvol and at in (AssetType.STOCK, AssetType.CRYPTO))
                             else ""),
            "rel_vol": round(dvol / pvol, 3) if (dvol and pvol) else "",
            "day_open": day_o if day_o is not None else "",
            "day_high": day_h if day_h is not None else "",
            "day_low": day_l if day_l is not None else "",
            "prev_close": prev_c if prev_c is not None else "",
            # Derived FACTS (pure arithmetic) so ranking lenses besides the
            # completed 1-day move are one call: today's move ex-gap
            # (split-immune), the overnight gap, and where price sits in
            # today's range (0=low, 1=high). Blank whenever the bar hasn't
            # rolled to today (bar_is_today above) — there is no today's
            # range yet to report.
            "pct_intraday": (round((float(price) - day_o) / day_o * 100.0, 3)
                             if day_o else ""),
            "gap_pct": (round((day_o - prev_c) / prev_c * 100.0, 3)
                        if (day_o and prev_c) else ""),
            "range_pos": (round((float(price) - day_l) / (day_h - day_l), 2)
                          if (day_h is not None and day_l is not None
                              and day_h > day_l) else ""),
            # When the print predated the bar (stale — price fell back to the
            # bar close above) this carries the BAR's ts: the freshness the
            # row's price actually reflects.
            "last_trade_ts": (db_t if (lt_t and db_t and lt_t[:10] < db_t[:10])
                              else lt_t) or db_t or "",
        })

    # Futures rows carry contract sizing — the agent MUST size by NOTIONAL, not
    # contract count: one ES is price × 50 ≈ $380k of exposure, MES is price × 5.
    # Without this the price column is meaningless for risk on a futures row.
    if at == AssetType.FUTURES:
        from aitrader.futures import SPECS as FUTURES_SPECS, MARGIN_ESTIMATES
        cols = cols + ["multiplier", "notional", "est_margin"]
        for r in rows:
            mult = FUTURES_SPECS.get(r["symbol"], {}).get("multiplier")
            r["multiplier"] = mult if mult is not None else ""
            r["notional"] = round(float(r["price"]) * mult) if (mult and r["price"] != "") else ""
            r["est_margin"] = MARGIN_ESTIMATES.get(r["symbol"], "")

    os.makedirs(settings().state_dir, exist_ok=True)
    path = os.path.join(settings().state_dir, f"snapshots_{at.value}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    result = {"path": path, "count": len(rows), "asset_type": at.value,
              "as_of": utcnow_iso(), "columns": cols}
    if at == AssetType.CRYPTO:
        result["notes"] = ("day_volume/rel_vol are Alpaca's OWN venue only, in coin "
                           "units (quote-derived bars can show zero volume) — NOT the "
                           "coin's global market volume; do not read them as market "
                           "liquidity. day_notional (price × coins) is the venue's "
                           "dollar turnover — the cross-coin comparable activity "
                           "number.")
    return result


@mcp.tool()
def get_all_snapshots(asset_type: str = None) -> dict:
    """PULL THE WHOLE TAPE. Call with NO arguments as your SECOND call of every
    cycle (right after broker_status): it snapshots EVERY asset type that is
    open right now (stock / crypto / forex / futures — options is worked through
    chains) to one CSV per type, and returns every file:
        {as_of, open_types, results: {stock: {path, count, ...},
                                      forex: {path, count, ...}, ...}}
    A type that fails carries {error: "..."} instead — paste that error verbatim
    in its survey row and move on; it never blocks the other types. Passing an
    asset_type refreshes just that one type (same as get_type_snapshots).

    The CSVs are for YOU to rank in the sandbox — this tool ranks, filters, and
    scores NOTHING (pure data per CLAUDE.md §2). It returns paths, NOT rows: a
    full equity universe is ~12k names, far too big for context. e.g.:
        import pandas as pd
        df = pd.read_csv(PATH)
        liquid = df[(df.price > 5) & (df.day_volume > 1_000_000)]
        liquid.sort_values('pct_1d', ascending=False).head(20)
    Your OWN liquidity floor, your OWN metric — a penny stock up 300% is noise;
    a large-cap up 3% on heavy volume is the signal canned feeds hid.

    CSV columns: symbol, price, pct_1d (last vs prior close, %), day_volume,
    rel_vol (day vs prior-day volume), day_open, day_high, day_low, prev_close,
    pct_intraday (today's move ex-gap, split-immune), gap_pct (overnight
    repricing), range_pos (0=day low .. 1=day high),
    last_trade_ts (when the row's price actually printed); futures rows add
    multiplier, notional, est_margin (size futures by NOTIONAL, never contract
    count). The vendor's daily bar rolls to the new session on a symbol's
    FIRST print of that session, not at the bell — until a name has traded
    today, day_open/day_high/day_low/day_volume/rel_vol/pct_intraday/gap_pct/
    range_pos are BLANK for it (today's range genuinely isn't known yet) and
    prev_close is the last completed session's close, so pct_1d reads a flat
    0% rather than a stale prior-day move. last_trade_ts still reflects a
    genuinely live print (e.g. a pre-market trade) even while those other
    columns are blank for the same row — filter on the column you're ranking
    by (blank already excludes via rank_instruments) rather than assuming a
    fresh last_trade_ts certifies the whole row. On an IEX node day_volume is
    IEX share count — a fraction of consolidated tape; calibrate floors to the
    data in front of you.

    CRYPTO volume caveat: day_volume/rel_vol are Alpaca's OWN venue only, in
    COIN units (quote-derived bars can show zero volume with valid prices) —
    they say NOTHING about a coin's global market liquidity; judge crypto
    liquidity from spread and price structure, never this column."""
    at = parse_asset_type(asset_type) if asset_type else None
    if at is not None:
        return snapshot_type_to_csv(at)
    avail = broker().get_available_types()
    open_types = [t for t, is_open in avail.items()
                  if is_open and t != "options"]
    results = {}
    for t in open_types:
        try:
            results[t] = snapshot_type_to_csv(parse_asset_type(t))
        except Exception as e:
            results[t] = {"error": f"{type(e).__name__}: {e}"}
    return {"as_of": utcnow_iso(), "open_types": open_types, "results": results}


@mcp.tool()
def get_type_snapshots(asset_type: str = "stock") -> dict:
    """Refresh ONE asset type's whole-universe snapshot CSV mid-cycle
    ('stock'|'crypto'|'forex'|'futures'). Same CSV, columns, and caveats as
    get_all_snapshots — see it for the ranking guidance. Returns
    {path, count, asset_type, as_of, columns[, notes]}."""
    return snapshot_type_to_csv(parse_asset_type(asset_type) or AssetType.STOCK)


def _rank_multi_lens(rows, at, path, age, lenses, n, min_price, min_volume,
                     fresh_only, exclude_held, num):
    """Several named ranked cuts off ONE shared filter pass, instead of one
    rank_instruments call per cut — see rank_instruments(lenses=...). Each
    lens is '<by>' or '<by>:<direction>' (direction defaults 'up'), same
    vocabulary as the single-lens `by`/`direction` args. min_price/min_volume/
    fresh_only/exclude_held apply identically to every lens; `no_data` is
    tallied per lens (it depends on that lens's own `by` column), everything
    else is shared."""
    import datetime
    lens_list = clean_symbols(lenses)
    n = max(1, min(int(n), 100))
    shared_excluded = {"min_price": 0, "min_volume": 0, "stale": 0, "held": 0}
    filters = {"min_price": min_price, "min_volume": min_volume,
               "fresh_only": fresh_only, "exclude_held": exclude_held}
    if not rows:
        empty = {"count": 0, "movers": [], "excluded": dict(shared_excluded, no_data=0)}
        return {"asset_type": at.value, "csv_age_seconds": age, "path": path,
                "universe": 0, "filters": filters,
                "lenses": {lens: dict(empty) for lens in lens_list}}

    held = set()
    if exclude_held:
        for p in broker().get_positions():
            held.add(str(p.get("symbol", "")).replace("/", "").upper())

    today = datetime.date.today().isoformat()
    kept = []
    for r in rows:
        if min_price and (num(r.get("price")) or 0) < min_price:
            shared_excluded["min_price"] += 1
            continue
        if min_volume and (num(r.get("day_volume")) or 0) < min_volume:
            shared_excluded["min_volume"] += 1
            continue
        ts = str(r.get("last_trade_ts", ""))[:10]
        if fresh_only and ts and ts < today:
            shared_excluded["stale"] += 1
            continue
        if exclude_held and r.get("symbol", "").replace("/", "").upper() in held:
            shared_excluded["held"] += 1
            continue
        kept.append(r)

    lens_results = {}
    for lens in lens_list:
        by, _, direction = lens.partition(":")
        direction = direction or "up"
        if by not in rows[0]:
            raise ValueError(f"lens {lens!r}: 'by' must be one of {list(rows[0])}")
        no_data = 0
        out = []
        for r in kept:
            metric = num(r.get(by))
            if metric is None:
                no_data += 1
                continue
            out.append((metric, r))
        reverse = (direction != "down")
        if direction == "abs":
            out.sort(key=lambda t: abs(t[0]), reverse=True)
        else:
            out.sort(key=lambda t: t[0], reverse=reverse)
        movers = [{k: (num(v) if num(v) is not None else v) for k, v in r.items()}
                  for _, r in out[:n]]
        lens_results[lens] = {"count": len(movers), "by": by, "direction": direction,
                              "excluded": dict(shared_excluded, no_data=no_data),
                              "movers": movers}

    # Distinct symbols across ALL requested lenses combined (a name that tops
    # both the gainers and the notional lens counts once, not twice) — the
    # number GATE must reconcile its own row count against, so an omission is
    # a checkable mismatch instead of something only caught by hand-counting
    # the survey against the table after the fact.
    unique_movers = len({m["symbol"] for lr in lens_results.values() for m in lr["movers"]})

    result = {"asset_type": at.value, "csv_age_seconds": age, "path": path,
              "universe": len(rows), "filters": filters, "lenses": lens_results,
              "unique_movers": unique_movers}
    if at == AssetType.CRYPTO:
        result["notes"] = ("crypto day_volume counts coins traded on Alpaca's OWN "
                           "venue — not market liquidity; a coin-unit volume floor "
                           "removes the whole class. Comparable activity is "
                           "day_notional (dollars traded) or rel_vol (vs the pair's "
                           "own average).")
    return result


def rank_snapshot_csv(asset_type, n, by, direction, min_price, min_volume,
                      fresh_only, exclude_held, lenses=None):
    """Core of rank_instruments — plain function so it is testable directly.
    `lenses`, if given, ignores by/direction and returns several named ranked
    cuts in one call instead of one — see _rank_multi_lens / rank_instruments."""
    import csv as csvmod
    import datetime
    at = parse_asset_type(asset_type) or AssetType.STOCK
    path = os.path.join(settings().state_dir, f"snapshots_{at.value}.csv")
    if not os.path.exists(path):
        snapshot_type_to_csv(at)
    age = int(datetime.datetime.now().timestamp() - os.path.getmtime(path))
    rows = list(csvmod.DictReader(open(path)))

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    if lenses:
        return _rank_multi_lens(rows, at, path, age, lenses, n, min_price,
                                min_volume, fresh_only, exclude_held, num)

    # ---- single-lens path: unchanged from pre-1.49.0 behavior ----
    # Per-cause exclusion tally (first failing check claims the row) so an
    # empty result names its own cause: count=0 with excluded.min_volume=68
    # reads as "your floor", not "a dead tape".
    excluded = {"no_data": 0, "min_price": 0, "min_volume": 0,
                "stale": 0, "held": 0}
    if not rows:
        return {"count": 0, "movers": [], "csv_age_seconds": age, "path": path,
                "universe": 0, "excluded": excluded}
    if by not in rows[0]:
        raise ValueError(f"'by' must be one of {list(rows[0])}")

    held = set()
    if exclude_held:
        for p in broker().get_positions():
            held.add(str(p.get("symbol", "")).replace("/", "").upper())

    today = datetime.date.today().isoformat()
    out = []
    for r in rows:
        metric = num(r.get(by))
        if metric is None:
            excluded["no_data"] += 1
            continue
        if min_price and (num(r.get("price")) or 0) < min_price:
            excluded["min_price"] += 1
            continue
        if min_volume and (num(r.get("day_volume")) or 0) < min_volume:
            excluded["min_volume"] += 1
            continue
        ts = str(r.get("last_trade_ts", ""))[:10]
        # empty ts = freshness UNKNOWN (IBKR rows carry no trade ts) — keep;
        # only a ts that is present AND pre-today is a known-stale print.
        if fresh_only and ts and ts < today:
            excluded["stale"] += 1
            continue
        if exclude_held and r.get("symbol", "").replace("/", "").upper() in held:
            excluded["held"] += 1
            continue
        out.append((metric, r))

    reverse = (direction != "down")
    if direction == "abs":
        out.sort(key=lambda t: abs(t[0]), reverse=True)
    else:
        out.sort(key=lambda t: t[0], reverse=reverse)
    n = max(1, min(int(n), 100))
    # JSON numbers, not CSV strings — numeric where parseable, verbatim else.
    movers = [{k: (num(v) if num(v) is not None else v) for k, v in r.items()}
              for _, r in out[:n]]
    result = {"count": len(movers), "asset_type": at.value, "by": by,
              "direction": direction, "csv_age_seconds": age,
              "universe": len(rows), "excluded": excluded,
              "filters": {"min_price": min_price, "min_volume": min_volume,
                          "fresh_only": fresh_only, "exclude_held": exclude_held},
              "movers": movers}
    if at == AssetType.CRYPTO:
        result["notes"] = ("crypto day_volume counts coins traded on Alpaca's OWN "
                           "venue — not market liquidity; a coin-unit volume floor "
                           "removes the whole class. Comparable activity is "
                           "day_notional (dollars traded) or rel_vol (vs the pair's "
                           "own average).")
    return result


@mcp.tool()
def rank_instruments(asset_type: str = "stock", n: int = 20, by: str = "pct_1d",
                     direction: str = "up", min_price: float = 0,
                     min_volume: float = 0, fresh_only: bool = True,
                     exclude_held: bool = True, lenses: list | str = None) -> dict:
    """Rank the whole-tape snapshot CSV by a RAW FACT at parameters YOU choose
    and return the top n rows inline — a mechanical sort/filter, nothing more.
    It scores nothing, prefers nothing, and there is no house shortlist: the
    metric, floors, and depth are your arguments, and the full CSV stays on
    disk for any compound cut this tool can't express.

    The lens is YOURS — `by` any CSV column, each a different fact:
      pct_1d       completed 1-day move (includes the overnight gap)
      pct_intraday today's move since the open (ex-gap, split-immune)
      gap_pct      the overnight repricing alone
      rel_vol      today's volume vs yesterday's (unusual participation)
      range_pos    where price sits in today's range (0=low .. 1=high)
      day_volume   raw units traded (shares; venue-coins for crypto)
      day_notional dollars actually traded (price × units) — the cross-row
                   comparable activity number (stock + crypto)
    direction: up or down (losers/laggards — shorts and fades are trades
    too) or abs (biggest either way; no quote marks around any of the
    three). For a signed metric (pct_1d, pct_intraday, gap_pct) this is
    bullish vs bearish; for an unsigned magnitude (day_volume, day_notional,
    rel_vol) up/down is just largest-first vs smallest-first — not a
    directional signal.

    asset_type: stock, crypto, forex, or futures (reads the step-0 CSV;
      pulls fresh only if missing — csv_age_seconds reports the data's age).
    n: rows to return (1-100). min_price / min_volume: your floors. min_volume
      counts UNITS: consolidated shares for stocks, but Alpaca-venue COINS for
      crypto (BTC prints ~1 coin/day there) — a floor in dollars belongs on
      day_notional, not day_volume.
    fresh_only: drop rows whose last trade predates today (stale prints).
    exclude_held (default True): drop symbols you already hold — your positions
      are in front of you from reconcile; this list is for what you DON'T own.
      Pass false to rank the full tape including your names.

    Returns {count, universe, excluded, csv_age_seconds, filters, movers: [...]}
    — an inline JSON array of row objects, same shape at 0, 1, or many rows.
    `excluded` counts the rows each of your filters removed: count=0 with a
    large excluded.min_volume means your floor emptied the list, not the tape.

    lenses: get SEVERAL ranked cuts in ONE call instead of one. Each entry
      is `<by>` or `<by>:<direction>` (direction defaults up), same by/
      direction vocabulary as above — pass a list of these, or one
      comma-joined value (same convention as `symbols` elsewhere: list OR
      comma-string both work). No quote characters belong inside an entry
      itself — a value is just letters, a colon, and a comma between
      entries. Constitution step 3(c)'s required cut is four entries:
      pct_1d up, pct_1d down, day_notional up, rel_vol up. When set,
      `by`/`direction` above are ignored; min_price/min_volume/fresh_only/
      exclude_held still apply, identically, to every lens (one shared filter
      pass). Returns {asset_type, universe, csv_age_seconds, path, filters,
      unique_movers, lenses: {<lens>: {count, by, direction, excluded,
      movers}, ...}} instead of the single-lens shape — each lens's
      `excluded` is the same shared min_price/min_volume/stale/held counts
      plus that lens's own no_data tally. `unique_movers`: the DISTINCT
      symbol count across every lens combined (a name topping two lenses
      counts once) — write this number down; GATE reconciles its own row
      count against it, so a dropped name is a checkable mismatch, not
      something only caught by hand-comparing the survey to the table after
      the fact. This is the floored, multi-lens cut constitution step 3(c)
      requires every survey — one call covers it."""
    return rank_snapshot_csv(asset_type, n, by, direction, min_price,
                             min_volume, fresh_only, exclude_held, lenses)


@mcp.tool()
def get_option_chain(symbol: str, expiry_range_days: int = 60) -> dict:
    """Option chain (expiries/strikes) for a symbol — raw data, no selection."""
    return broker().get_option_chain(clean_symbol(symbol), expiry_range_days=expiry_range_days)


@mcp.tool()
def get_option_greeks(symbol: str, expiry: str, strike: float, right: str) -> dict:
    """Greeks for one option (right = 'C'|'P')."""
    return broker().get_option_greeks(clean_symbol(symbol), expiry, strike, right)


# ── broker time facts ─────────────────────────────────────────────────────

@mcp.tool()
def get_available_types() -> dict:
    """What is tradeable RIGHT NOW per asset class -> {stock,crypto,forex,
    futures,options: bool} (keys present = types THIS broker supports). Broker
    truth (crypto 24/7, futures/forex own hours, options = regular session)."""
    return broker().get_available_types()


@mcp.tool()
def get_market_session() -> str:
    """Current US stock session: 'regular' | 'extended' | 'closed'."""
    return broker().get_market_session()


@mcp.tool()
def get_session_close(target_date: str = None) -> dict:
    """Today's (or target_date 'YYYY-MM-DD') stock session close as UTC ISO.
    Half-day aware. null if not a trading day."""
    d = date.fromisoformat(target_date) if target_date else date.today()
    close = broker().get_session_close(d)
    return {"date": d.isoformat(), "session_close_utc": close.isoformat() if close else None}


# ── currency housekeeping ─────────────────────────────────────────────────

@mcp.tool()
def flatten_currency(currency: str, min_usd: float = 20.0) -> dict:
    """Flatten a single non-USD currency balance back to USD."""
    return broker().flatten_currency(currency, min_usd=min_usd)


@mcp.tool()
def flatten_all_residual_currencies(min_usd: float = 20.0) -> dict:
    """Flatten every residual non-USD currency back to USD. Returns
    {count, results: [...]}."""
    res = broker().flatten_all_residual_currencies(min_usd=min_usd)
    return {"count": len(res), "results": res}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
