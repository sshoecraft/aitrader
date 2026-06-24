"""broker MCP — execution + market data + broker time facts (BRIEF §A.4.1).

This server OWNS the execution-broker connection (the §A.3 job). The EXECUTION
backend is settings.broker ∈ {ibkr, alpaca, myse} (default ibkr); when
settings.data_broker is set, a separate market-DATA broker fronts it (see
aitrader/brokers/router.py). The MCP calls the driver's primitive methods
directly — they return plain dicts; IBKR blocks via its connection pools.

PURE PRIMITIVES, ZERO cognition. Every tool answers a factual question or
performs a mechanical action. No EDGE screen, score, or buy/sell signal here —
that judgment is the agent's. A FACTUAL movers feed (`get_top_movers`, ranked by
raw % change with no opinion) IS allowed as data per CLAUDE.md §2: it reports what
is *moving*, never what is *good*; the agent confirms on bars and decides.

Fuses: the connection enforces PAPER-ONLY (account id must start with DU/DF)
unless settings.toml sets allow_live = true (don't). No notional/buying-power caps.

Run: aitrader-broker-mcp  (stdio)
"""

__version__ = "0.6.0"

import os
import sys
from datetime import date

from mcp.server.fastmcp import FastMCP

from aitrader import journal_db
from aitrader.asset_types import AssetType
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
        b = AlpacaBroker(api_key, secret_key, paper=True)
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
        b = AlpacaBroker(api_key, secret_key, paper=not ALLOW_LIVE)
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


def parse_asset_type(s):
    """Convert a string asset type to AssetType, or None. Accepts the enum
    values: stock, crypto, forex, futures, options."""
    if s is None:
        return None
    if isinstance(s, AssetType):
        return s
    return AssetType(str(s).lower())


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
    return acct


@mcp.tool()
def get_portfolio_history(period: str = "1D", timeframe: str = "1D",
                          date_end: str = None) -> dict:
    """Portfolio equity history. period e.g. '1D','1W','1M'; timeframe e.g.
    '1Min','1D'; date_end optional 'YYYY-MM-DD' anchor."""
    return broker().get_portfolio_history(period=period, timeframe=timeframe, date_end=date_end)


@mcp.tool()
def get_positions() -> list:
    """All open positions (broker truth). Each: symbol, qty, avg price, market
    value, unrealized P&L, asset class."""
    b = broker()
    pos = b.get_positions()
    maybe_backfill_equity(b)  # one-time, only after this confirmed-good data read
    return pos


@mcp.tool()
def get_currency_balances() -> list:
    """Non-USD currency cash balances (forex residue)."""
    return broker().get_currency_balances()


# ── orders & execution ────────────────────────────────────────────────────

@mcp.tool()
def get_orders(status: str = None, after: str = None, until: str = None,
               limit: int = None) -> list:
    """List orders with optional filters (status/after/until/limit). Each order
    dict surfaces 'order_ref' = your client tag, for idempotent reconcile."""
    return broker().get_orders(status=status, after=after, until=until, limit=limit)


@mcp.tool()
def get_order(order_id: str) -> dict:
    """Get a single order by broker order id."""
    return broker().get_order(order_id)


@mcp.tool()
def get_open_orders_for_symbol(symbol: str) -> list:
    """Open orders for one symbol."""
    return broker().get_open_orders_for_symbol(symbol)


@mcp.tool()
def place_market_order(symbol: str, qty: float, side: str, tif: str = "day",
                       asset_type: str = None, client_tag: str = None) -> dict:
    """Place a market order. side = 'buy'|'sell'. Pass a DETERMINISTIC
    client_tag (your idempotency key) — it is stamped on the order's ref so a
    relaunched you recognizes it. Record the tag in the journal first."""
    return broker().place_market_order(symbol, qty, side, tif=tif,
                                       asset_type=parse_asset_type(asset_type),
                                       client_tag=client_tag)


@mcp.tool()
def place_limit_order(symbol: str, qty: float, side: str, limit_price: float,
                      tif: str = "day", asset_type: str = None,
                      outside_rth: bool = False, client_tag: str = None) -> dict:
    """Place a limit order at limit_price. side='buy'|'sell'. client_tag =
    idempotency key (see place_market_order)."""
    return broker().place_limit_order(symbol, qty, side, limit_price, tif=tif,
                                      asset_type=parse_asset_type(asset_type),
                                      outside_rth=outside_rth, client_tag=client_tag)


@mcp.tool()
def place_stop_order(symbol: str, qty: float, side: str, stop_price: float,
                     tif: str = "day", asset_type: str = None,
                     client_tag: str = None) -> dict:
    """Place a stop-market order triggering at stop_price."""
    return broker().place_stop_order(symbol, qty, side, stop_price, tif=tif,
                                     asset_type=parse_asset_type(asset_type),
                                     client_tag=client_tag)


@mcp.tool()
def place_stop_limit_order(symbol: str, qty: float, side: str, stop_price: float,
                           limit_price: float, tif: str = "day",
                           asset_type: str = None, outside_rth: bool = False,
                           client_tag: str = None) -> dict:
    """Place a stop-limit order (stop trigger + limit)."""
    return broker().place_stop_limit_order(symbol, qty, side, stop_price, limit_price,
                                           tif=tif, asset_type=parse_asset_type(asset_type),
                                           outside_rth=outside_rth, client_tag=client_tag)


@mcp.tool()
def place_bracket_order(symbol: str, qty: float, side: str, limit_price: float,
                        stop_loss: float, take_profit: float, tif: str = "day",
                        stop_limit_price: float = None, client_tag: str = None) -> dict:
    """Place a bracket (entry limit + stop-loss + take-profit). All three legs
    carry your client_tag. The bracket prices are YOUR chosen numbers — this is
    plumbing, not a strategy; nothing here computes a stop or target for you."""
    return broker().place_bracket_order(symbol, qty, side, limit_price, stop_loss,
                                        take_profit, tif=tif,
                                        stop_limit_price=stop_limit_price,
                                        client_tag=client_tag)


@mcp.tool()
def modify_order(order_id: str, stop_price: float = None, limit_price: float = None,
                 qty: float = None, symbol: str = None) -> dict:
    """Modify an existing order's price(s) and/or qty in place."""
    return broker().modify_order(order_id, stop_price=stop_price,
                                 limit_price=limit_price, qty=qty, symbol=symbol)


@mcp.tool()
def cancel_order(order_id: str, timeout: float = 8, poll_interval: float = 0.5) -> dict:
    """Cancel an order by id; waits up to timeout for confirmation."""
    return broker().cancel_order(order_id, timeout=timeout, poll_interval=poll_interval)


@mcp.tool()
def global_cancel() -> dict:
    """Cancel ALL open orders at the broker. Blunt instrument — your choice."""
    return broker().global_cancel()


@mcp.tool()
def close_position(symbol: str, client_tag: str = None) -> dict:
    """Flatten a position by submitting the offsetting order. client_tag stamps
    the closing order's ref."""
    return broker().close_position(symbol, client_tag=client_tag)


@mcp.tool()
def wait_for_fill(order_id: str, timeout: float = 300, poll_interval: float = 2) -> dict:
    """Block (up to timeout) until an order fills; returns the filled order dict
    or null. Lives here (not the scheduler) because polling needs the broker
    connection this server owns."""
    return broker().wait_for_fill(order_id, timeout=timeout, poll_interval=poll_interval)


@mcp.tool()
def get_fill_activities(after: str = None) -> list:
    """Recent fills/executions, optionally after an ISO timestamp."""
    return broker().get_fill_activities(after=after)


@mcp.tool()
def get_historical_executions(symbol: str = None, side: str = None, days: int = 7) -> list:
    """Historical executions up to `days` back (IBKR reqExecutions)."""
    return broker().get_historical_executions(symbol=symbol, side=side, days=days)


# ── market data ───────────────────────────────────────────────────────────

@mcp.tool()
def get_tradeable_assets(asset_type: str = "stock") -> list:
    """The LIST of tradeable symbols for an asset class — what exists, NOT a
    ranked or filtered shortlist. Surveying/filtering it is your job.

    Source: Alpaca for stock/crypto when a data feed is configured (its full
    universe), else IBKR. Note: a symbol in Alpaca's list is not guaranteed
    tradeable on IBKR (the execution venue); confirm with a snapshot/order."""
    return broker().get_tradeable_assets(asset_type=parse_asset_type(asset_type) or AssetType.STOCK)


@mcp.tool()
def get_snapshot(symbol: str, asset_type: str = None) -> dict:
    """Current quote/snapshot for one symbol (latestTrade/dailyBar/prevDailyBar).

    For a LIVE stock/crypto quote incl. pre/after-hours, pass
    asset_type='stock' or 'crypto' → routes to the Alpaca feed. WITHOUT
    asset_type it goes to IBKR, whose paper feed returns empty/zeros pre-open.
    Same dict shape either way, so always pass asset_type for stocks/crypto."""
    return broker().get_snapshot(symbol, asset_type=parse_asset_type(asset_type))


@mcp.tool()
def get_snapshots(symbols: list | str, asset_type: str = None) -> dict:
    """Current snapshots for several symbols -> {symbol: snapshot}.

    `symbols` may be a list (["ES","NQ"]) OR a comma-separated string
    ("ES,NQ,GC,CL") — both work; the string is split on commas.

    For LIVE stock/crypto quotes incl. pre/after-hours, pass asset_type='stock'
    or 'crypto' → Alpaca feed. WITHOUT asset_type it goes to IBKR (empty/zeros
    pre-open on paper). Same shape either way, so always pass asset_type."""
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(",") if s.strip()]
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
    return broker().get_bars(symbols, asset_type=parse_asset_type(asset_type),
                             timeframe=timeframe, start=start, limit=limit)


@mcp.tool()
def get_top_movers(top_n: int = 20) -> dict:
    """The day's top % gainers and losers in US stocks RIGHT NOW — the market-movers
    list a trader watches (like CNBC's), straight from the data vendor. DATA ONLY:
    ranked by RAW % change, with NO edge, score, or buy/sell opinion — gainers can be
    great setups OR knives; that judgment is yours. Use it to find what is actually
    moving, then pull 5/15-min bars (asset_type='stock') to confirm clean directional
    structure (not a choppy fakeout) before acting. Returns
    {gainers:[{symbol,pct_change,price,change}], losers:[...], as_of}."""
    r = broker()
    feed = getattr(r, "data", None) or getattr(r, "execution", r)
    fn = getattr(feed, "get_top_movers", None)
    if fn is None:
        return {"error": "no movers feed on this node (needs an Alpaca data feed)",
                "gainers": [], "losers": []}
    return fn(top_n=top_n)


@mcp.tool()
def get_option_chain(symbol: str, expiry_range_days: int = 60) -> dict:
    """Option chain (expiries/strikes) for a symbol — raw data, no selection."""
    return broker().get_option_chain(symbol, expiry_range_days=expiry_range_days)


@mcp.tool()
def get_option_greeks(symbol: str, expiry: str, strike: float, right: str) -> dict:
    """Greeks for one option (right = 'C'|'P')."""
    return broker().get_option_greeks(symbol, expiry, strike, right)


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
def flatten_all_residual_currencies(min_usd: float = 20.0) -> list:
    """Flatten every residual non-USD currency back to USD."""
    return broker().flatten_all_residual_currencies(min_usd=min_usd)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
