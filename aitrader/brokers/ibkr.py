"""IBKR broker driver using ib_async.

Wraps ib_async IB gateway connections. All methods normalize ib_async objects
to plain dicts. This is a PURE-PRIMITIVE driver (BRIEF §2 hard boundary): it
answers factual questions and performs mechanical actions only — no screeners,
no scoring, no entry/exit signals, no sizing, no risk checks.

Connection ownership (BRIEF §A.3): the broker holds three IBKRConnectionPools
(orders / status / data), each one or more ib_async IB() instances on dedicated
worker threads that own their own callback pump and reconnect supervision (see
ibkr_connection.py). Public methods are decorated with @route_to, which
dispatches the call body onto the right pool via a thread-local IB.

Idempotency (BRIEF §5): every order-placement method accepts an optional
client_tag that is stamped onto the IBKR Order.orderRef, so a relaunched agent
can recognize its own in-flight orders and never double-submit. orderRef is
surfaced back in get_order(s) dicts as 'order_ref'.

Paper-only fuse (BRIEF §7): enforced at the connection layer (ibkr_connection
.assert_paper). The broker passes allow_live (default False) through to it.
"""

import asyncio
import functools
import logging
import math
import threading
import time

__version__ = "1.4.0"

log = logging.getLogger(__name__)

try:
    from ib_async import (IB, Stock, Crypto, Forex, Future, Option,
                          LimitOrder, StopOrder, MarketOrder, Contract)
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    IB = None
    Stock = None
    Crypto = None
    Forex = None
    Future = None
    Option = None
    LimitOrder = None
    StopOrder = None
    MarketOrder = None
    Contract = None

from aitrader.asset_types import AssetType, normalize_pair_symbol
from aitrader.broker import Broker
from aitrader.brokers.ibkr_connection import is_paper_account
from aitrader.brokers.ibkr_pool import IBKRConnectionPool, merge_by_id
from aitrader.credentials import load_ibkr_credentials
from aitrader.futures import SPECS as FUTURES_SPECS, round_to_tick


def route_to(pool_attr, mode="single", pin_after=False, pinned_by=None,
             merge_id=None, timeout=60):
    """Decorator that routes a method's execution to a connection pool.

    The decorated method's body executes on the pool worker's loop thread,
    with self.ib bound (via threading.local) to that worker's IB instance.
    Method bodies may be sync (return a value) or async (return a coroutine,
    awaited on the worker's persistent loop with the result bridged back).

    Args:
        pool_attr: pool attribute name ('orders_pool','status_pool','data_pool')
        mode: 'single' — least-loaded connection
              'scatter' — every healthy connection, merge results
              'pinned' — connection pinned to a key from args/kwargs
        pin_after: if True, pin the serving connection by result['id']
        pinned_by: for mode='pinned', the kwarg name / positional index holding
            the pin key
        merge_id: for mode='scatter', dedupe dicts by this field
        timeout: per-call future timeout in seconds
    """
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Test / legacy mode: no pools, call directly.
            if not getattr(self, "pool_mode", False):
                result = method(self, *args, **kwargs)
                if asyncio.iscoroutine(result):
                    return asyncio.run(result)
                return result
            # Re-entry: this thread is already a pool worker (TLS set).
            if getattr(self.tls, "ib", None) is not None:
                return method(self, *args, **kwargs)
            pool = getattr(self, pool_attr)

            def runner(ib):
                self.tls.ib = ib
                try:
                    result = method(self, *args, **kwargs)
                except BaseException:
                    self.tls.ib = None
                    raise
                if asyncio.iscoroutine(result):
                    async def wrapped():
                        try:
                            return await result
                        finally:
                            self.tls.ib = None
                    return wrapped()
                self.tls.ib = None
                return result

            if mode == "scatter":
                results = pool.scatter_run(runner, timeout=timeout)
                if merge_id is not None:
                    return merge_by_id(results, merge_id)
                if results and all(isinstance(r, list) for r in results):
                    flat = []
                    for r in results:
                        flat.extend(r)
                    return flat
                return results[0] if results else None
            if mode == "pinned":
                if isinstance(pinned_by, int):
                    key = args[pinned_by] if pinned_by < len(args) else None
                else:
                    key = kwargs.get(pinned_by)
                    if key is None and args:
                        key = args[0]
                if key is None:
                    return pool.run(runner, timeout=timeout)
                return pool.run_pinned(key, runner, timeout=timeout)
            # mode == "single"
            extractor = None
            if pin_after:
                extractor = pin_key_from_result
            return pool.run(runner, timeout=timeout, pin_key_extractor=extractor)
        wrapper.route_pool_attr = pool_attr
        wrapper.route_mode = mode
        wrapper.route_pin_after = pin_after
        wrapper.route_pinned_by = pinned_by
        wrapper.route_merge_id = merge_id
        wrapper.route_timeout = timeout
        return wrapper
    return decorator


def pin_key_from_result(result):
    """Extract the broker order id from a placement result for pinning."""
    if isinstance(result, dict):
        return result.get("id")
    return None


# Crypto supported on IBKR via Paxos + Zero Hash
SUPPORTED_CRYPTO = ("BTC", "ETH", "LTC", "BCH", "SOL", "ADA", "XRP", "DOGE")

# IBKR ZEROHASH quantity decimal limits per coin
CRYPTO_QTY_DECIMALS = {
    "BTC": 8, "ETH": 6, "LTC": 6, "BCH": 6, "SOL": 6,
    "ADA": 1, "XRP": 6, "DOGE": 1,
}

TIF_MAP = {"day": "DAY", "gtc": "GTC", "opg": "OPG", "ioc": "IOC", "fok": "FOK"}


def normalize_tif(tif):
    """Map a time-in-force to IBKR's enum, CASE-INSENSITIVELY. An unknown TIF RAISES
    instead of silently falling back to DAY — mirrors the Alpaca adapter's tif_enum.
    The silent fallback was dangerous: uppercase "GTC" missed the lowercase-keyed
    TIF_MAP and became DAY, so a stop the agent asked to rest GTC expired at the close
    and left the position unprotected overnight."""
    key = str(tif or "day").strip().lower()
    if key not in TIF_MAP:
        raise ValueError(f"unknown time_in_force {tif!r}; valid: {', '.join(TIF_MAP)}")
    return TIF_MAP[key]

# Forex cash mapping: currency -> (IBKR pair, inverted)
# inverted=True means USD is base — to sell that currency, BUY the pair.
# inverted=False means the currency is base — to sell it, SELL the pair.
FOREX_CASH_MAP = {
    "EUR": ("EURUSD", False),
    "GBP": ("GBPUSD", False),
    "AUD": ("AUDUSD", False),
    "NZD": ("NZDUSD", False),
    "CHF": ("CHFUSD", False),
    "CAD": ("USDCAD", True),
    "JPY": ("USDJPY", True),
}

# Tradeable forex universe — the major IDEALPRO pairs in canonical base/quote
# form. Every entry round-trips through make_contract (-> concatenated IBKR
# pair) and normalize_position (-> back to this slash form). This is the
# COMPLETE list the broker offers (raw infra enumeration), NOT a ranked or
# filtered shortlist — the agent screens it by reasoning. Mirrors how
# SUPPORTED_CRYPTO enumerates crypto. Directions chosen to match IDEALPRO's
# standard pair (USD/JPY -> USDJPY, USD/CHF -> USDCHF), so they qualify cleanly.
FOREX_UNIVERSE = (
    "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
    "USD/JPY", "USD/CHF", "USD/CAD",
    "EUR/GBP", "EUR/JPY", "EUR/CHF", "GBP/JPY", "AUD/JPY",
)

# Map IBKR order types to broker-agnostic names
ORDER_TYPE_MAP = {
    "LMT": "limit",
    "MKT": "market",
    "STP": "stop",
    "STP LMT": "stop_limit",
}


def normalize_order_type(ibkr_type):
    """Convert IBKR order type string to a broker-agnostic type."""
    return ORDER_TYPE_MAP.get(ibkr_type, ibkr_type.lower())


def canonical_symbol(ibkr_symbol):
    """Convert IBKR space-notation share classes back to dot notation.

    IBKR uses 'BRK B', 'PBR A' — canonical form is 'BRK.B', 'PBR.A'. Only
    converts when there is exactly one space separating a 1-2 char alpha
    suffix (share class), not multi-word names.
    """
    parts = ibkr_symbol.split(" ")
    if len(parts) == 2 and len(parts[1]) <= 2 and parts[1].isalpha():
        return f"{parts[0]}.{parts[1]}"
    return ibkr_symbol


def safe_float(val, fallback=0):
    """Return val as float if valid, otherwise fallback.

    ib_async ticker fields return nan (not None) for unavailable data; the
    ``or`` operator doesn't catch nan because bool(nan) is True.
    """
    if val is None:
        return fallback
    try:
        f = float(val)
        if math.isnan(f):
            return fallback
        return f
    except (TypeError, ValueError):
        return fallback


def normalize_order(trade):
    """Convert ib_async Trade to a plain dict.

    Forex cash orders (secType=CASH) are un-inverted back to the XXX/USD
    position symbol with the original side and prices. The IBKR Order.orderRef
    (the agent's deterministic client tag) is surfaced as 'order_ref'.
    """
    order = trade.order
    contract = trade.contract
    symbol = canonical_symbol(contract.symbol)
    side = "buy" if order.action == "BUY" else "sell"
    stop_price = getattr(order, "auxPrice", None) or ""
    limit_price = getattr(order, "lmtPrice", None) or ""

    if contract.secType == "CASH":
        base = contract.symbol
        quote = contract.currency
        if base == "USD":
            symbol = f"USD/{quote}"
        else:
            symbol = f"{base}/{quote}"

    return {
        "id": str(order.orderId),
        "symbol": symbol,
        "side": side,
        "qty": str(order.totalQuantity),
        "filled_qty": str(trade.orderStatus.filled),
        "filled_avg_price": str(trade.orderStatus.avgFillPrice),
        "status": trade.orderStatus.status.lower(),
        "type": normalize_order_type(order.orderType),
        "time_in_force": order.tif,
        "order_class": "",
        "limit_price": str(limit_price),
        "stop_price": str(stop_price),
        "order_ref": getattr(order, "orderRef", "") or "",
        "created_at": str(trade.log[0].time) if trade.log else "",
    }


ASSET_CLASS_MAP = {
    "STK": "us_equity",
    "CRYPTO": "crypto",
    "CASH": "forex",
    "FUT": "futures",
    "OPT": "options",
}


def normalize_position(item):
    """Convert ib_async PortfolioItem to a plain dict.

    Uses ib.portfolio() which includes live market price and P&L, unlike
    ib.positions() which only has avgCost.
    """
    contract = item.contract
    qty = item.position
    avg_cost = item.averageCost
    market_price = item.marketPrice
    market_value = item.marketValue
    unrealized_pnl = item.unrealizedPNL
    sec_type = getattr(contract, "secType", "STK")

    multiplier = float(getattr(contract, "multiplier", 0) or 0) or 1.0
    if sec_type == "FUT" and multiplier > 1:
        avg_cost_per_unit = avg_cost / multiplier
    else:
        avg_cost_per_unit = avg_cost

    cost_basis = float(qty) * avg_cost
    plpc = unrealized_pnl / cost_basis if cost_basis else 0.0

    if sec_type == "CASH":
        sym = f"{contract.symbol}/{contract.currency}"
    else:
        sym = canonical_symbol(str(contract.symbol))

    result = {
        "symbol": sym,
        "qty": str(qty),
        "avg_entry_price": str(avg_cost_per_unit),
        "current_price": str(market_price),
        "market_value": str(market_value),
        "unrealized_pl": str(unrealized_pnl),
        "unrealized_plpc": str(plpc),
        "side": "long" if float(qty) > 0 else "short",
        "cost_basis": str(cost_basis),
        "asset_class": ASSET_CLASS_MAP.get(sec_type, "us_equity"),
    }
    if sec_type == "FUT":
        result["multiplier"] = multiplier
        result["expiry"] = getattr(contract, "lastTradeDateOrContractMonth", "")
    elif sec_type == "OPT":
        result["multiplier"] = multiplier
        result["asset_class"] = "options"
        result["expiry"] = getattr(contract, "lastTradeDateOrContractMonth", "")
        result["strike"] = float(getattr(contract, "strike", 0))
        result["right"] = getattr(contract, "right", "")
    return result


def normalize_fill(fill):
    """Convert ib_async Fill to a plain dict."""
    execution = fill.execution
    return {
        "id": str(execution.execId),
        "symbol": canonical_symbol(str(fill.contract.symbol)),
        "side": "buy" if execution.side == "BOT" else "sell",
        "qty": str(execution.shares),
        "price": str(execution.price),
        "transaction_time": str(execution.time),
        "order_id": str(execution.orderId),
        "type": "fill",
    }


def parse_trading_hours(hours_str, tz_name):
    """Parse an IBKR tradingHours/liquidHours string into UTC windows.

    Entries are ';'-separated; each is 'YYYYMMDD:CLOSED', the modern
    'YYYYMMDD:HHMM-YYYYMMDD:HHMM' range form (may span midnight; multiple
    ranges comma-separated), or the legacy 'YYYYMMDD:HHMM-HHMM,HHMM-HHMM'
    form where the date is stated once. Times are exchange-local in tz_name
    (the contract details' timeZoneId — e.g. US/Central for CME, US/Eastern
    for IDEALPRO). Returns [(start_utc, end_utc), ...]; unparseable ranges
    are skipped with a warning. Pure string→fact conversion, no opinions.
    """
    import re
    from datetime import datetime as dt, timezone, timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    windows = []

    def to_utc(date_s, time_s):
        return (dt.strptime(date_s + time_s, "%Y%m%d%H%M")
                .replace(tzinfo=tz).astimezone(timezone.utc))

    for entry in (hours_str or "").split(";"):
        entry = entry.strip()
        if not entry or entry.upper().endswith("CLOSED"):
            continue
        modern = re.findall(r"(\d{8}):(\d{4})-(\d{8}):(\d{4})", entry)
        if modern:
            for d1, t1, d2, t2 in modern:
                try:
                    windows.append((to_utc(d1, t1), to_utc(d2, t2)))
                except ValueError:
                    log.warning("[ibkr] bad trading-hours range in %r", entry)
            continue
        legacy = re.match(r"(\d{8}):(.+)", entry)
        if not legacy:
            log.warning("[ibkr] unparseable trading-hours entry %r", entry)
            continue
        day = legacy.group(1)
        for rng in legacy.group(2).split(","):
            m = re.match(r"(\d{4})-(\d{4})$", rng.strip())
            if not m:
                log.warning("[ibkr] unparseable trading-hours range %r", rng)
                continue
            try:
                start, end = to_utc(day, m.group(1)), to_utc(day, m.group(2))
            except ValueError:
                log.warning("[ibkr] bad trading-hours range in %r", entry)
                continue
            if end <= start:  # legacy overnight range wraps to the next day
                end += timedelta(days=1)
            windows.append((start, end))
    return windows


class IBKRBroker(Broker):
    """Interactive Brokers driver using ib_async.

    Pool mode (default) wires three IBKRConnectionPools (orders / status /
    data) and routes each public method to the appropriate pool. Methods
    access self.ib, a thread-local property pointing at the pool worker's own
    IB() instance during the call.

    Set pool_mode=False (tests) to keep self.ib as a directly-assigned
    attribute and execute method bodies in the caller's thread.
    """

    name = "ibkr"

    DEFAULT_POOL_SIZES = {"orders": 2, "status": 1, "data": 8}

    def __init__(self, host=None, port=None, client_id=None,
                 pool_mode=True, pool_sizes=None,
                 connect_stagger_ms=250, connect_timeout=30,
                 idle_pump_seconds=None, allow_live=False,
                 extended_hours=False, secrets_path=None):
        if not HAS_IB_INSYNC:
            raise ImportError(
                "ib_async is required for IBKR broker. Install ib_async."
            )
        # Connection config comes from aitrader.credentials by default. Explicit
        # host/port/client_id args override (used by tests / multi-account).
        if host is None or port is None or client_id is None:
            creds = load_ibkr_credentials(secrets_path)
            host = host if host is not None else creds["host"]
            port = port if port is not None else creds["port"]
            client_id = client_id if client_id is not None else creds["client_id"]

        self.host = host
        self.port = port
        self.client_id = client_id
        self.pool_mode = pool_mode
        self.connect_stagger_ms = connect_stagger_ms
        self.connect_timeout = connect_timeout
        self.allow_live = allow_live
        # extended_hours governs only whether get_available_types() reports
        # `stock` tradeable during the pre/after-hours window. It is a dumb
        # config toggle, not a trading opinion.
        self.extended_hours = extended_hours
        self.tls = threading.local()
        self.direct_ib = None  # test-mode direct IB; or first orders IB
        self.orders_pool = None
        self.status_pool = None
        self.data_pool = None
        # Per-ET-date session close from SPY liquidHours: datetime = close,
        # None = confirmed no session (holiday/weekend). Failed lookups are
        # never cached. Gates get_market_session; one gateway query per day.
        self.session_close_by_date = {}
        # Per-(class, ET date) UTC trading windows of the class's
        # representative contract (forex: EUR/USD IDEALPRO; futures: ES front
        # month). Same rules: failures never cached, one gateway query per
        # class per day. Gates the forex/futures availability answer.
        self.class_windows_by_date = {}

        if pool_mode:
            sizes = dict(self.DEFAULT_POOL_SIZES)
            if pool_sizes:
                sizes.update(pool_sizes)
            base = int(client_id)
            orders_ids = [base + i for i in range(sizes["orders"])]
            status_ids = [base + 10 + i for i in range(sizes["status"])]
            data_ids = [base + 20 + i for i in range(sizes["data"])]
            if max(data_ids) - base >= 32:
                raise ValueError(
                    f"pool config exceeds IBKR's 32-clientId ceiling "
                    f"(base={base}, max id={max(data_ids)})"
                )
            pumps = idle_pump_seconds or {}
            self.orders_pool = IBKRConnectionPool(
                host=host, port=port, client_ids=orders_ids, role="orders",
                connect_stagger_ms=connect_stagger_ms,
                connect_timeout=connect_timeout,
                idle_pump_seconds=pumps.get("orders"),
                allow_live=allow_live,
            )
            self.status_pool = IBKRConnectionPool(
                host=host, port=port, client_ids=status_ids, role="status",
                connect_stagger_ms=connect_stagger_ms,
                connect_timeout=connect_timeout,
                idle_pump_seconds=pumps.get("status"),
                allow_live=allow_live,
            )
            self.data_pool = IBKRConnectionPool(
                host=host, port=port, client_ids=data_ids, role="data",
                connect_stagger_ms=connect_stagger_ms,
                connect_timeout=connect_timeout,
                idle_pump_seconds=pumps.get("data"),
                allow_live=allow_live,
            )

    @property
    def ib(self):
        """Return the IB instance bound to the current call.

        Inside a pool dispatch the worker thread sets self.tls.ib before
        calling the method body — that takes precedence. Otherwise return the
        directly-assigned direct_ib (tests / legacy paths).
        """
        tls_ib = getattr(self.tls, "ib", None)
        if tls_ib is not None:
            return tls_ib
        return self.direct_ib

    @ib.setter
    def ib(self, value):
        self.direct_ib = value

    def connect(self):
        if self.pool_mode:
            try:
                self.orders_pool.start()
                self.status_pool.start()
                self.data_pool.start()
                ok = (self.orders_pool.wait_ready(timeout=60)
                      and self.status_pool.wait_ready(timeout=60)
                      and self.data_pool.wait_ready(timeout=60))
                if not ok:
                    raise ConnectionError(
                        "[ibkr] one or more pools failed to become ready"
                    )
                self.direct_ib = self.orders_pool.connections[0].ib
                self.orders_pool.run(
                    lambda ib: self.validate_portfolio_with(ib),
                    timeout=30,
                )
                log.info("[ibkr] pool-mode connected: orders=%d status=%d data=%d",
                         self.orders_pool.size, self.status_pool.size,
                         self.data_pool.size)
                return
            except Exception:
                # If any pool fails, the OTHER pools may have opened sockets
                # whose clientIds stay claimed until their workers stop. Stop
                # all so a retry doesn't hit IBKR error 326 (clientId in use).
                for pool in (self.orders_pool, self.status_pool, self.data_pool):
                    try:
                        if pool is not None:
                            pool.stop()
                    except Exception:
                        pass
                raise
        # Test / single-connection mode.
        self.direct_ib = IB()
        self.direct_ib.RequestTimeout = 30
        self.direct_ib.connect(self.host, self.port, clientId=self.client_id)
        asyncio.run(self.validate_portfolio())

    async def validate_portfolio_with(self, ib):
        """validate_portfolio bound to a specific IB (startup, one connection)."""
        prior_ib = getattr(self.tls, "ib", None)
        self.tls.ib = ib
        try:
            await self.validate_portfolio()
        finally:
            self.tls.ib = prior_ib

    async def validate_portfolio(self):
        """Check that portfolio data arrived after connecting.

        ib_async populates portfolio() from reqAccountUpdates during connect.
        If the subscription silently failed, portfolio is empty even with open
        positions. Detect that and retry once.
        """
        portfolio = self.ib.portfolio()
        if portfolio:
            log.info("Portfolio loaded: %d items", len(portfolio))
            return

        summary = {item.tag: item.value for item in await self.ib.accountSummaryAsync()}
        gross_pos = float(summary.get("GrossPositionValue", 0))

        if gross_pos < 5000:
            return

        log.warning(
            "Portfolio empty but $%.0f in positions — reqAccountUpdates may "
            "have failed, retrying", gross_pos,
        )
        for _ in range(10):
            await asyncio.sleep(0.5)
            if self.ib.portfolio():
                log.info("Portfolio loaded after retry: %d items",
                         len(self.ib.portfolio()))
                return

        log.warning("Portfolio still empty after wait — re-requesting account updates")
        await self.ib.reqAccountUpdatesAsync()
        for _ in range(10):
            await asyncio.sleep(0.5)
            if self.ib.portfolio():
                log.info("Portfolio loaded after re-subscribe: %d items",
                         len(self.ib.portfolio()))
                return

        log.error(
            "PORTFOLIO STILL EMPTY despite $%.0f in positions — positions "
            "will be invisible", gross_pos,
        )

    def ensure_connected(self):
        """Reconnect if connection dropped.

        Pool mode: each connection self-heals on its own worker thread; no-op.
        Test mode: original single-connection check.
        """
        if self.pool_mode:
            return
        if not self.ib.isConnected():
            self.connect()

    def reconnect(self):
        """Force every pool connection to reconnect (pool mode), or do the
        disconnect/sleep/connect cycle in test mode."""
        if self.pool_mode:
            self.orders_pool.reconnect_all()
            self.status_pool.reconnect_all()
            self.data_pool.reconnect_all()
            return
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        time.sleep(5)
        self.connect()

    def wait(self):
        """In pool mode each connection pumps its own ib_async loop on its own
        thread; this just yields CPU. Test mode pumps the single loop."""
        if self.pool_mode:
            time.sleep(0.05)
            return
        if not self.ib.isConnected():
            raise ConnectionError("IBKR connection lost")
        self.ib.sleep(0.1)
        if not self.ib.isConnected():
            raise ConnectionError("IBKR connection lost during wait")

    def stop(self):
        """Stop all pool connections. Used at shutdown."""
        if self.pool_mode:
            for pool in (self.orders_pool, self.status_pool, self.data_pool):
                if pool is not None:
                    pool.stop()

    def submit_async(self, method_name, *args, **kwargs):
        """Asynchronous broker dispatch. Returns a Future without blocking.

        Single-mode @route_to methods dispatch directly onto the pool's worker
        queue (zero extra threads). Non-pool mode, or scatter/pinned routes,
        fall back to the Broker ABC's threaded default.
        """
        if not self.pool_mode:
            return Broker.submit_async(self, method_name, *args, **kwargs)

        method = getattr(type(self), method_name, None)
        if method is None or not hasattr(method, "route_pool_attr"):
            return Broker.submit_async(self, method_name, *args, **kwargs)

        if method.route_mode != "single":
            return Broker.submit_async(self, method_name, *args, **kwargs)

        pool = getattr(self, method.route_pool_attr)
        underlying = method.__wrapped__
        pin_after = method.route_pin_after

        served = {"conn": None}

        def runner(ib):
            for c in pool.connections:
                if c.ib is ib:
                    served["conn"] = c
                    break
            prior = getattr(self.tls, "ib", None)
            self.tls.ib = ib
            try:
                return underlying(self, *args, **kwargs)
            finally:
                self.tls.ib = prior

        future = pool.submit(runner)

        if pin_after:
            def maybe_pin(fut):
                try:
                    result = fut.result()
                except Exception:
                    return
                key = pin_key_from_result(result)
                if key is not None and served["conn"] is not None:
                    pool.pin(key, served["conn"])
            future.add_done_callback(maybe_pin)

        return future

    @staticmethod
    def ibkr_symbol(symbol):
        """Convert dot-notation share classes to IBKR space notation.

        Canonical 'BRK.B', 'PBR.A' → IBKR 'BRK B', 'PBR A'.
        """
        return symbol.replace(".", " ") if "." in symbol else symbol

    async def make_contract(self, symbol, asset_type=None, option_params=None):
        """Create the appropriate IBKR contract for a symbol.

        For options, pass option_params dict with keys:
            underlying, expiry (YYYYMMDD), strike (float), right ('C' or 'P').
        """
        # Accept TWS dot notation for forex (EUR.USD -> EUR/USD) before any
        # branch decides the contract type; leaves stock share classes alone.
        symbol = normalize_pair_symbol(symbol)
        base = symbol.split("/")[0] if "/" in symbol else symbol
        if asset_type == AssetType.OPTIONS and option_params:
            underlying = self.ibkr_symbol(option_params["underlying"])
            contract = Option(
                underlying,
                option_params["expiry"],
                float(option_params["strike"]),
                option_params["right"],
                "SMART",
                multiplier="100",
            )
        elif asset_type == AssetType.CRYPTO or base in SUPPORTED_CRYPTO:
            contract = Crypto(base, "ZEROHASH", "USD")
        elif asset_type == AssetType.FOREX:
            pair = self.resolve_forex_pair_name(symbol)
            contract = Forex(pair, exchange="IDEALPRO")
        elif asset_type == AssetType.FUTURES or symbol in FUTURES_SPECS:
            contract = await self.resolve_front_month(symbol)
            return contract  # already qualified
        elif "/" in symbol and len(symbol) <= 7:
            pair = self.resolve_forex_pair_name(symbol)
            contract = Forex(pair, exchange="IDEALPRO")
        else:
            ibkr_sym = self.ibkr_symbol(symbol)
            contract = Stock(ibkr_sym, "SMART", "USD")
        await self.ib.qualifyContractsAsync(contract)
        return contract

    @route_to("data_pool")
    async def get_classification(self, symbol, asset_type=None):
        """IBKR industry classification for a symbol — factual reference data.

        Returns {"sector": ..., "industry": ...} from the contract's
        `reqContractDetails` (industry → sector, category → industry). This is a
        mechanical lookup of the security's published classification, NOT a
        screen, score, ranking, or opinion. Only equities carry a classification;
        forex/crypto/futures/options have none and return {}.
        """
        self.ensure_connected()
        contract = await self.make_contract(symbol, asset_type)
        if not isinstance(contract, Stock):
            return {}
        details = await self.ib.reqContractDetailsAsync(contract)
        if not details:
            return {}
        d = details[0]
        sector = (d.industry or "").strip()
        industry = (d.category or "").strip()
        # ETFs/funds carry no single industry; IBKR leaves industry/category
        # blank but reports the security type in stockType. Surface that as the
        # sector so a fund buckets as "ETF"/"Fund" rather than "Unclassified" —
        # still a factual security-type fact, not an opinion.
        if not sector:
            stock_type = (getattr(d, "stockType", "") or "").strip().upper()
            if stock_type in ("ETF", "ETN", "FUND", "ETC", "ETP"):
                sector = "ETF" if stock_type in ("ETF", "ETN", "ETP", "ETC") else "Fund"
        return {"sector": sector or None, "industry": industry or None}

    def resolve_forex_pair_name(self, symbol):
        """Resolve a symbol to a valid IBKR forex pair name.

        Handles forex cash symbols (CAD/USD → USDCAD) and direct pairs
        (EUR/JPY → EURJPY). Returns a 6-char pair string.
        """
        if symbol.endswith("/USD"):
            currency = symbol.split("/")[0]
            if currency in FOREX_CASH_MAP:
                return FOREX_CASH_MAP[currency][0]
        return symbol.replace("/", "")

    def is_forex_inverted(self, symbol):
        """Check if a forex cash symbol uses an inverted IBKR pair.

        Inverted means USD is the base in the IBKR pair (e.g., USDCAD), so
        closing a long cash position requires a BUY. Returns (is_inverted,
        ibkr_pair) or (False, None) for non-forex.
        """
        if not (symbol.endswith("/USD") and "/" in symbol):
            return False, None
        currency = symbol.split("/")[0]
        if currency in FOREX_CASH_MAP:
            ibkr_pair, inverted = FOREX_CASH_MAP[currency]
            return inverted, ibkr_pair
        return False, None

    def forex_convert_for_order(self, symbol, qty, stop_price=None,
                                 limit_price=None, side="sell"):
        """Convert forex cash order params to IBKR pair convention.

        For inverted pairs (CAD/USD → USDCAD): flip SELL→BUY, invert prices,
        convert qty from cash currency to USD (base). Returns (action, qty,
        stop_price, limit_price).
        """
        inverted, ibkr_pair = self.is_forex_inverted(symbol)
        action = "BUY" if side == "buy" else "SELL"
        if not inverted:
            return action, qty, stop_price, limit_price

        action = "BUY" if action == "SELL" else "SELL"

        if stop_price is not None:
            stop_price = round(1.0 / float(stop_price), 5)
        if limit_price is not None:
            limit_price = round(1.0 / float(limit_price), 5)

        currency = symbol.split("/")[0]
        rate = self.get_forex_rate(currency)
        if rate > 0:
            qty = int(float(qty) * rate)

        return action, qty, stop_price, limit_price

    def get_forex_rate(self, currency):
        """Get USD-per-unit exchange rate for a currency from IBKR."""
        for av in self.ib.accountValues():
            if av.tag == "ExchangeRate" and av.currency == currency:
                return float(av.value)
        return 0.0

    async def resolve_front_month(self, symbol):
        """Resolve to the front-month futures contract for a symbol.

        If the front month expires within 5 days, rolls to the next contract
        (if available) to avoid illiquid near-expiry trading. This is a
        mechanical contract-selection fact, not a trading opinion.
        """
        import datetime as dt

        spec = FUTURES_SPECS.get(symbol, {})
        exchange = spec.get("exchange", "CME")
        currency = spec.get("currency", "USD")
        generic = Future(symbol, exchange=exchange, currency=currency)
        details = await self.ib.reqContractDetailsAsync(generic)
        if not details:
            raise ValueError(f"No futures contracts found for {symbol}")
        details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)

        front = details[0].contract
        expiry_str = front.lastTradeDateOrContractMonth
        if len(expiry_str) == 8 and len(details) > 1:
            try:
                expiry_date = dt.datetime.strptime(expiry_str, "%Y%m%d").date()
                today = dt.date.today()
                days_to_expiry = (expiry_date - today).days
                if days_to_expiry <= 5:
                    next_contract = details[1].contract
                    log.warning(
                        "%s front month %s expires in %d days, rolling to %s",
                        symbol, expiry_str, days_to_expiry,
                        next_contract.lastTradeDateOrContractMonth,
                    )
                    front = next_contract
            except ValueError:
                pass

        await self.ib.qualifyContractsAsync(front)
        return front

    def is_crypto(self, symbol):
        """Check if symbol is a supported crypto."""
        base = symbol.split("/")[0] if "/" in symbol else symbol
        return base in SUPPORTED_CRYPTO

    def is_paper(self):
        """True if the connected account is an IBKR paper account.

        IBKR crypto (routed to Paxos/ZeroHash) is NOT available on paper
        accounts, so the broker reports crypto untradeable when paper — a
        factual broker-capability fact, not a trading opinion. Reads
        managedAccounts (populated at the API handshake, no round-trip).
        Fails CLOSED to paper when accounts can't be read, since aitrader is
        paper-only by design (the only non-paper path is allow_live=True)."""
        try:
            accounts = [a for a in self.ib.managedAccounts() if a]
        except Exception:
            return True
        if not accounts:
            return True
        return all(is_paper_account(a) for a in accounts)

    @staticmethod
    def is_forex(symbol):
        """Check if symbol is a forex pair (EUR/USD, EUR/CAD, USD/JPY, etc.)."""
        if "/" not in symbol:
            return False
        from aitrader.asset_types import FOREX_BASES
        base = symbol.split("/")[0]
        return base in FOREX_BASES

    @staticmethod
    def apply_order_ref(order, client_tag):
        """Stamp the agent's deterministic client tag onto Order.orderRef.

        BRIEF §5 idempotency: a relaunched agent recognizes its own in-flight
        orders by orderRef. No-op when client_tag is falsy.
        """
        if client_tag:
            order.orderRef = str(client_tag)
        return order

    @route_to("status_pool")
    async def get_account(self):
        """Get account info from IBKR account summary."""
        self.ensure_connected()
        summary = await self.ib.accountSummaryAsync()

        values = {}
        for item in summary:
            values[item.tag] = item.value

        cash = values.get("TotalCashValue", "0")
        equity = values.get("NetLiquidation", "0")
        buying_power = values.get("BuyingPower", "0")
        settled_cash = values.get("SettledCash", cash)

        # The account id is a factual property of the account — surface it so
        # callers (e.g. the broker MCP's paper-vs-live readout) don't have to
        # reach into managedAccounts separately.
        account_id = ""
        for item in summary:
            if getattr(item, "account", None):
                account_id = item.account
                break
        if not account_id:
            try:
                accts = self.ib.managedAccounts()
                account_id = accts[0] if accts else ""
            except Exception:
                account_id = ""

        return {
            "account": account_id,
            "cash": str(cash),
            "equity": str(equity),
            "buying_power": str(buying_power),
            "portfolio_value": str(equity),
            "pattern_day_trader": False,
            "daytrade_count": 0,
            "status": "ACTIVE",
            "settled_cash": str(settled_cash),
        }

    @route_to("orders_pool")
    def get_portfolio_history(self, period="1D", timeframe="1D", date_end=None):
        """IBKR doesn't have a direct portfolio history API."""
        return {
            "error": "Portfolio history not available on IBKR. Use the "
                     "journal equity snapshots for equity history."
        }

    @route_to("orders_pool")
    async def get_positions(self):
        """Get all open positions from IBKR with live market prices.

        Includes forex cash balances as positions: IBKR forex trades settle as
        currency cash changes, not portfolio items. Non-USD cash balances in
        FOREX_CASH_MAP are surfaced as XXX/USD positions.

        If portfolio is empty but the account has deployed capital, attempts to
        recover the account subscription before returning.
        """
        self.ensure_connected()
        portfolio = self.ib.portfolio()

        if not portfolio:
            portfolio = await self.recover_portfolio()

        positions = [normalize_position(item) for item in portfolio]

        existing = {p["symbol"] for p in positions}
        forex = self.get_forex_cash_positions(existing)
        positions.extend(forex)
        return positions

    async def recover_portfolio(self):
        """Attempt to recover an empty portfolio by re-subscribing.

        Returns the portfolio list (possibly still empty if recovery fails).
        Uses GrossPositionValue (actual value of open positions) rather than
        NetLiquidation - TotalCashValue, which includes forex cash imbalances
        that aren't real positions.
        """
        summary = {item.tag: item.value for item in await self.ib.accountSummaryAsync()}
        gross_pos = float(summary.get("GrossPositionValue", 0))

        if gross_pos < 1000:
            return []

        log.warning(
            "Portfolio empty but $%.0f in positions — attempting recovery",
            gross_pos,
        )

        await self.ib.reqAccountUpdatesAsync()

        for attempt in range(5):
            await asyncio.sleep(1.0)
            portfolio = self.ib.portfolio()
            if portfolio:
                log.info("Portfolio recovered: %d items", len(portfolio))
                return portfolio

        log.error(
            "Portfolio recovery FAILED — $%.0f in positions but none visible",
            gross_pos,
        )
        return []

    def get_forex_cash_positions(self, existing_symbols):
        """Build forex position dicts from IBKR account cash balances.

        IBKR forex trades settle as currency cash changes, not portfolio items.
        This reads non-USD CashBalance entries from accountValues and surfaces
        each positive balance in FOREX_CASH_MAP as an XXX/USD long position,
        priced at the live ExchangeRate. Pure broker-truth reconstruction —
        no external store, no cognition.

        Cross pairs (e.g. EUR/GBP) cannot be reconstructed from merged cash
        and are intentionally omitted; only XXX/USD cash positions are built.
        """
        rates = {}        # {currency: USD per unit}
        balances = {}     # {currency: native units, summed across segments}
        for av in self.ib.accountValues():
            ccy = av.currency
            if ccy in ("BASE", "USD", ""):
                continue
            if av.tag == "ExchangeRate":
                try:
                    rates[ccy] = float(av.value)
                except (TypeError, ValueError):
                    pass
            elif av.tag == "CashBalance":
                try:
                    balances[ccy] = balances.get(ccy, 0.0) + float(av.value)
                except (TypeError, ValueError):
                    pass

        results = []
        for ccy, cash in balances.items():
            if cash <= 1e-6:
                continue
            if ccy not in FOREX_CASH_MAP:
                continue
            symbol = f"{ccy}/USD"
            if symbol in existing_symbols:
                continue
            rate = rates.get(ccy, 0.0)
            usd_value = cash * rate if rate > 0 else 0.0
            current_price = rate if rate > 0 else 0.0
            results.append({
                "symbol": symbol,
                "qty": str(cash),
                "avg_entry_price": str(current_price),
                "current_price": str(current_price),
                "market_value": str(usd_value),
                "unrealized_pl": "0",
                "unrealized_plpc": "0",
                "side": "long",
                "cost_basis": str(usd_value),
                "asset_class": "forex",
            })
        return results

    @route_to("orders_pool", pin_after=True)
    async def close_position(self, symbol, client_tag=None):
        """Close a position by symbol with a market order.

        Forex positions are stored by IBKR as cash balances; the base currency
        cash balance IS the position qty (see close_forex_position).
        """
        self.ensure_connected()

        if self.is_forex(symbol):
            return await self.close_forex_position(symbol, client_tag=client_tag)

        position = self.held_qty(symbol)
        if position == 0:
            await self.recover_portfolio()
            position = self.held_qty(symbol)
        if position == 0:
            raise ValueError(f"No open position for {symbol}")

        qty = abs(position)
        side = "SELL" if position > 0 else "BUY"
        contract = await self.make_contract(symbol)
        order = MarketOrder(side, qty)
        order.tif = "DAY"
        self.apply_order_ref(order, client_tag)
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(2)
        self.check_rejected(trade)
        return normalize_order(trade)

    async def close_forex_position(self, symbol, client_tag=None):
        """Close a forex cash position (any pair type).

        Finds the base currency cash balance from accountValues and sells it
        through the appropriate IBKR forex contract. Sums across account
        segments.
        """
        base = symbol.split("/")[0]
        cash_qty = 0.0
        for av in self.ib.accountValues():
            if av.tag == "CashBalance" and av.currency == base:
                cash_qty += float(av.value)

        if cash_qty <= 0:
            raise ValueError(f"No {base} cash balance to close for {symbol}")

        inverted, ibkr_pair = self.is_forex_inverted(symbol)
        contract = await self.make_contract(symbol)

        if inverted:
            rate = self.get_forex_rate(base)
            usd_qty = int(cash_qty * rate) if rate > 0 else int(cash_qty)
            order = MarketOrder("BUY", usd_qty)
        else:
            order = MarketOrder("SELL", int(cash_qty))

        order.tif = "IOC"
        self.apply_order_ref(order, client_tag)
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(2)
        self.check_rejected(trade)
        return normalize_order(trade)

    @route_to("orders_pool")
    def get_currency_balances(self):
        """List non-USD currency cash balances from IBKR account values.

        Surfaces residual currency cash (e.g. left over after a forex close)
        so it can be flattened back to USD via flatten_currency(). Returns a
        list of {currency, cash, usd_value, ibkr_pair, inverted, rate} for each
        FOREX_CASH_MAP currency with a non-zero balance. Negative balances
        (margin debt) are returned with negative values.
        """
        self.ensure_connected()
        rates = {}
        balances = {}
        for av in self.ib.accountValues():
            ccy = av.currency
            if ccy in ("BASE", "USD", ""):
                continue
            if av.tag == "ExchangeRate":
                try:
                    rates[ccy] = float(av.value)
                except (TypeError, ValueError):
                    pass
            elif av.tag == "CashBalance":
                try:
                    balances[ccy] = balances.get(ccy, 0.0) + float(av.value)
                except (TypeError, ValueError):
                    pass

        results = []
        for ccy, cash in balances.items():
            if abs(cash) < 1e-6:
                continue
            if ccy not in FOREX_CASH_MAP:
                continue
            ibkr_pair, inverted = FOREX_CASH_MAP[ccy]
            rate = rates.get(ccy, 0.0)
            usd_value = cash * rate if rate > 0 else 0.0
            results.append({
                "currency": ccy,
                "cash": cash,
                "usd_value": usd_value,
                "ibkr_pair": ibkr_pair,
                "inverted": inverted,
                "rate": rate,
            })
        results.sort(key=lambda x: -abs(x["usd_value"]))
        return results

    @route_to("orders_pool")
    async def flatten_currency(self, currency, min_usd=20.0):
        """Convert all residual cash in a non-USD currency to zero.

        Positive balance (we hold it): SELL it for USD via the FOREX_CASH_MAP
        pair (reuses close_forex_position). Negative balance (margin debt): BUY
        just enough to zero the debt. min_usd is a dumb safety floor against
        accidental spam, not a trading threshold.
        """
        self.ensure_connected()

        if currency in (None, "", "USD"):
            return {"currency": currency, "status": "skipped_unknown_currency"}
        if currency not in FOREX_CASH_MAP:
            return {"currency": currency, "status": "skipped_unknown_currency"}

        cash = 0.0
        rate = 0.0
        for av in self.ib.accountValues():
            if av.currency != currency:
                continue
            if av.tag == "CashBalance":
                try:
                    cash += float(av.value)
                except (TypeError, ValueError):
                    pass
            elif av.tag == "ExchangeRate":
                try:
                    rate = float(av.value)
                except (TypeError, ValueError):
                    pass

        usd_value = cash * rate if rate > 0 else 0.0

        if abs(cash) < 1e-6:
            return {"currency": currency, "cash_before": 0.0,
                    "usd_value": 0.0, "status": "skipped_no_balance"}

        if abs(usd_value) < min_usd:
            return {"currency": currency, "cash_before": cash,
                    "usd_value": usd_value, "status": "skipped_below_min"}

        symbol = f"{currency}/USD"
        inverted, ibkr_pair = self.is_forex_inverted(symbol)

        try:
            if cash > 0:
                order = await self.close_forex_position(symbol)
                direction = "sell"
            else:
                contract = await self.make_contract(symbol)
                if inverted:
                    usd_qty = int(abs(cash) * rate) if rate > 0 else int(abs(cash))
                    if usd_qty <= 0:
                        return {"currency": currency, "cash_before": cash,
                                "usd_value": usd_value,
                                "status": "skipped_below_min", "direction": "buy"}
                    log.info("[flatten] %s: SELL %s qty=%d (covers %.2f %s debt)",
                             currency, ibkr_pair, usd_qty, abs(cash), currency)
                    order_obj = MarketOrder("SELL", usd_qty)
                else:
                    qty = int(abs(cash))
                    if qty <= 0:
                        return {"currency": currency, "cash_before": cash,
                                "usd_value": usd_value,
                                "status": "skipped_below_min", "direction": "buy"}
                    log.info("[flatten] %s: BUY %s qty=%d", currency, ibkr_pair, qty)
                    order_obj = MarketOrder("BUY", qty)
                order_obj.tif = "IOC"
                trade = self.ib.placeOrder(contract, order_obj)
                await asyncio.sleep(2)
                self.check_rejected(trade)
                order = normalize_order(trade)
                direction = "buy"

            return {"currency": currency, "cash_before": cash,
                    "usd_value": usd_value, "status": "flattened",
                    "direction": direction, "order": order}
        except Exception as exc:
            log.error("flatten_currency %s failed: %s", currency, exc)
            return {"currency": currency, "cash_before": cash,
                    "usd_value": usd_value, "status": "failed",
                    "error": str(exc)}

    @route_to("orders_pool")
    async def flatten_all_residual_currencies(self, min_usd=20.0):
        """Flatten every non-USD currency balance back to USD.

        Iterates get_currency_balances() and calls flatten_currency() on each.
        Returns a list of per-currency result dicts; continues past failures.
        """
        balances = self.get_currency_balances()
        results = []
        for entry in balances:
            ccy = entry["currency"]
            results.append(await self.flatten_currency(ccy, min_usd=min_usd))
        return results

    @route_to("orders_pool", mode="pinned", pinned_by="order_id", timeout=120)
    async def wait_for_fill(self, order_id, timeout=300, poll_interval=2):
        """Poll order status until filled or timeout.

        Yields to the connection's asyncio loop between checks so orderStatus
        callbacks can update trade objects. Returns the filled order dict, or
        None if not filled within timeout.
        """
        self.ensure_connected()
        order_id_int = int(order_id)
        deadline = time.time() + timeout
        while time.time() < deadline:
            await asyncio.sleep(poll_interval)
            for trade in self.ib.trades():
                if trade.order.orderId == order_id_int:
                    status = trade.orderStatus.status.lower()
                    if status == "filled":
                        return normalize_order(trade)
                    if status in ("cancelled", "inactive"):
                        return None
                    break
        return None

    def held_qty(self, symbol):
        """Return the quantity held for a stock/crypto/futures symbol.

        IBKR exposes two independent feeds — ib.positions() (reqPositions) and
        ib.portfolio() (reqAccountUpdates) — and they can desync. To stay
        consistent with get_positions() and never block a real exit, check both
        feeds and take whichever reports the larger absolute quantity.
        """
        ibkr_sym = self.ibkr_symbol(symbol)

        from_positions = 0.0
        for p in self.ib.positions():
            if p.contract.symbol == ibkr_sym:
                from_positions = float(p.position)
                break

        from_portfolio = 0.0
        for item in self.ib.portfolio():
            if item.contract.symbol == ibkr_sym:
                from_portfolio = float(item.position)
                break

        if abs(from_portfolio) >= abs(from_positions):
            return from_portfolio
        return from_positions

    async def verify_position_for_sell(self, symbol, qty):
        """Verify sufficient long position exists before allowing a sell.

        Prevents accidental short creation by refusing to sell more than held.
        For forex (XXX/USD pairs), checks the base currency cash balance from
        IBKR accountValues. Raises ValueError if the position is insufficient.
        """
        held_qty = 0.0

        if self.is_forex(symbol):
            base = symbol.split("/")[0]
            for av in self.ib.accountValues():
                if av.tag == "CashBalance" and av.currency == base:
                    held_qty += float(av.value)
        else:
            held_qty = self.held_qty(symbol)
            if held_qty <= 0:
                await self.recover_portfolio()
                held_qty = self.held_qty(symbol)

        if held_qty <= 0:
            raise ValueError(
                f"Cannot sell {qty} {symbol}: no open long position "
                f"(held={held_qty}). Would create accidental short."
            )
        if float(qty) > held_qty:
            raise ValueError(
                f"Cannot sell {qty} {symbol}: only {held_qty} held. "
                f"Would create accidental short."
            )

    def round_crypto_qty(self, symbol, qty):
        """Round crypto quantity to IBKR's allowed decimals for the coin."""
        base = symbol.split("/")[0] if "/" in symbol else symbol
        decimals = CRYPTO_QTY_DECIMALS.get(base, 6)
        return round(float(qty), decimals)

    def check_rejected(self, trade):
        """Raise if IBKR rejected/cancelled the order after async processing."""
        status = trade.orderStatus.status.lower()
        if status in ("cancelled", "inactive"):
            errors = [e.message for e in trade.log if e.errorCode]
            msg = errors[-1] if errors else f"Order {status}"
            raise RuntimeError(msg)

    def round_crypto_price(self, price):
        """Round price to IBKR ZEROHASH minimum tick.

        Price < $1: 4 decimals, $1-$99.99: 2 decimals, >= $100: whole dollars.
        """
        price = float(price)
        if price >= 100:
            return round(price, 0)
        elif price >= 1:
            return round(price, 2)
        else:
            return round(price, 4)

    @route_to("orders_pool", pin_after=True)
    async def place_bracket_order(self, symbol, qty, side, limit_price,
                            stop_loss, take_profit, tif="day",
                            stop_limit_price=None, client_tag=None):
        """Place a bracket order (parent limit + take profit + stop loss).

        Crypto on ZEROHASH: stop orders not supported, so places a single
        IOC market/limit leg. stop_limit_price: if provided, the stop-loss leg
        becomes a stop-limit order with this limit price.
        """
        self.ensure_connected()
        contract = await self.make_contract(symbol)
        action = "BUY" if side == "buy" else "SELL"
        ibkr_tif = normalize_tif(tif)

        if self.is_crypto(symbol):
            if action == "BUY":
                cash_amount = round(float(qty) * float(limit_price), 2)
                order = MarketOrder(action, 0)
                order.cashQty = cash_amount
            else:
                rounded_qty = self.round_crypto_qty(symbol, qty)
                order = MarketOrder(action, rounded_qty)
            order.tif = "IOC"
            self.apply_order_ref(order, client_tag)
            trade = self.ib.placeOrder(contract, order)
            await asyncio.sleep(2)
            self.check_rejected(trade)
            return normalize_order(trade)

        bracket = self.ib.bracketOrder(
            action,
            float(qty),
            round(float(limit_price), 2),
            round(float(take_profit), 2),
            round(float(stop_loss), 2),
        )

        parent, tp_order, sl_order = bracket

        if stop_limit_price is not None:
            sl_order.orderType = "STP LMT"
            sl_order.lmtPrice = round(float(stop_limit_price), 2)

        parent.tif = ibkr_tif
        tp_order.tif = "GTC"
        sl_order.tif = "GTC"

        # Stamp the agent's tag on every leg so the whole bracket is
        # recognizable as the agent's own on relaunch.
        self.apply_order_ref(parent, client_tag)
        self.apply_order_ref(tp_order, client_tag)
        self.apply_order_ref(sl_order, client_tag)

        parent_trade = self.ib.placeOrder(contract, parent)
        self.ib.placeOrder(contract, tp_order)
        self.ib.placeOrder(contract, sl_order)

        await asyncio.sleep(2)
        self.check_rejected(parent_trade)
        return normalize_order(parent_trade)

    @route_to("orders_pool", pin_after=True)
    async def place_market_order(self, symbol, qty, side, tif="day",
                                 asset_type=None, client_tag=None):
        """Place a market order.

        Crypto BUYs go through Paxos/Zerohash, which require dollar-denominated
        cashQty rather than coin quantity; qty × current_price → cashQty using a
        fresh snapshot. SELLs use coin qty.
        """
        self.ensure_connected()

        if side == "sell":
            await self.verify_position_for_sell(symbol, qty)

        contract = await self.make_contract(symbol, asset_type=asset_type)
        action = "BUY" if side == "buy" else "SELL"
        ibkr_tif = normalize_tif(tif)

        if self.is_forex(symbol):
            qty = int(qty)
            ibkr_tif = "IOC"

        if self.is_crypto(symbol):
            ibkr_tif = "IOC"
            if action == "BUY":
                price = 0.0
                try:
                    snap = await self.get_snapshot(symbol, asset_type=asset_type)
                    price = float(snap.get("latestTrade", {}).get("p", 0) or 0)
                except Exception:
                    price = 0.0
                if price <= 0:
                    raise ValueError(
                        f"Cannot price crypto BUY for {symbol}: no snapshot "
                        f"available — Paxos requires cashQty for buys."
                    )
                cash_amount = round(float(qty) * price, 2)
                order = MarketOrder(action, 0)
                order.cashQty = cash_amount
                order.tif = ibkr_tif
                self.apply_order_ref(order, client_tag)
                trade = self.ib.placeOrder(contract, order)
                await asyncio.sleep(2)
                self.check_rejected(trade)
                return normalize_order(trade)
            qty = self.round_crypto_qty(symbol, qty)

        order = MarketOrder(action, float(qty))
        order.tif = ibkr_tif
        self.apply_order_ref(order, client_tag)
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(2)
        self.check_rejected(trade)
        return normalize_order(trade)

    @route_to("orders_pool", pin_after=True)
    async def place_limit_order(self, symbol, qty, side, limit_price, tif="day",
                          asset_type=None, outside_rth=False, client_tag=None):
        """Place a limit order."""
        self.ensure_connected()

        if side == "sell":
            await self.verify_position_for_sell(symbol, qty)

        if self.is_crypto(symbol) and side == "sell_short":
            raise ValueError("Short selling crypto is not supported on IBKR")

        contract = await self.make_contract(symbol, asset_type=asset_type)
        action = "BUY" if side == "buy" else "SELL"
        ibkr_tif = normalize_tif(tif)

        if self.is_crypto(symbol):
            qty = self.round_crypto_qty(symbol, qty)
            limit_price = self.round_crypto_price(limit_price)
            ibkr_tif = "IOC"
        elif symbol in FUTURES_SPECS:
            limit_price = round_to_tick(limit_price, symbol)
        elif self.is_forex(symbol):
            limit_price = round(float(limit_price), 5)
            qty = int(qty)
        else:
            limit_price = round(float(limit_price), 2)

        order = LimitOrder(action, float(qty), float(limit_price), tif=ibkr_tif)
        if outside_rth:
            order.outsideRth = True
        self.apply_order_ref(order, client_tag)
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(2)
        self.check_rejected(trade)
        return normalize_order(trade)

    @route_to("orders_pool", pin_after=True)
    async def place_stop_limit_order(self, symbol, qty, side, stop_price,
                               limit_price, tif="day", asset_type=None,
                               outside_rth=False, client_tag=None):
        """Place a stop-limit order."""
        self.ensure_connected()

        if side == "sell":
            await self.verify_position_for_sell(symbol, qty)

        contract = await self.make_contract(symbol, asset_type=asset_type)
        ibkr_tif = normalize_tif(tif)

        inverted, _ = self.is_forex_inverted(symbol)
        if inverted:
            action, qty, stop_price, limit_price = self.forex_convert_for_order(
                symbol, qty, stop_price, limit_price, side)
            stop_price = round(float(stop_price), 5)
            limit_price = round(float(limit_price), 5)
        elif symbol in FUTURES_SPECS:
            action = "BUY" if side == "buy" else "SELL"
            stop_price = round_to_tick(stop_price, symbol)
            limit_price = round_to_tick(limit_price, symbol)
        elif self.is_forex(symbol):
            action = "BUY" if side == "buy" else "SELL"
            stop_price = round(float(stop_price), 5)
            limit_price = round(float(limit_price), 5)
        elif not self.is_crypto(symbol):
            action = "BUY" if side == "buy" else "SELL"
            stop_price = round(float(stop_price), 2)
            limit_price = round(float(limit_price), 2)
        else:
            action = "BUY" if side == "buy" else "SELL"

        if self.is_forex(symbol) or inverted:
            qty = int(qty)

        order = StopOrder(action, float(qty), float(stop_price), tif=ibkr_tif)
        order.lmtPrice = float(limit_price)
        order.orderType = "STP LMT"
        if outside_rth:
            order.outsideRth = True
        self.apply_order_ref(order, client_tag)
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(2)
        self.check_rejected(trade)
        return normalize_order(trade)

    @route_to("orders_pool", pin_after=True)
    async def place_stop_order(self, symbol, qty, side, stop_price, tif="day",
                         asset_type=None, client_tag=None):
        """Place a stop-market order."""
        self.ensure_connected()

        if side == "sell":
            await self.verify_position_for_sell(symbol, qty)

        contract = await self.make_contract(symbol, asset_type=asset_type)
        ibkr_tif = normalize_tif(tif)

        inverted, _ = self.is_forex_inverted(symbol)
        if inverted:
            action, qty, stop_price, _ = self.forex_convert_for_order(
                symbol, qty, stop_price, None, side)
            stop_price = round(float(stop_price), 5)
        elif symbol in FUTURES_SPECS:
            action = "BUY" if side == "buy" else "SELL"
            stop_price = round_to_tick(stop_price, symbol)
        elif self.is_forex(symbol):
            action = "BUY" if side == "buy" else "SELL"
            stop_price = round(float(stop_price), 5)
        elif not self.is_crypto(symbol):
            action = "BUY" if side == "buy" else "SELL"
            stop_price = round(float(stop_price), 2)
        else:
            # CRYPTO: raw stop price (no rounding). NOTE this sends a stop-MARKET.
            # IBKR crypto routes to Paxos/ZeroHash — live-only (untradeable on
            # paper), so this path is UNVERIFIED. Alpaca has no crypto stop-market
            # and routes to stop-limit; Paxos MAY reject a naked crypto stop too.
            # GO-LIVE checklist: verify on a live IBKR crypto account; if rejected,
            # route to place_stop_limit_order here exactly as AlpacaBroker does.
            action = "BUY" if side == "buy" else "SELL"

        if self.is_forex(symbol) or inverted:
            qty = int(qty)

        order = StopOrder(action, float(qty), float(stop_price), tif=ibkr_tif)
        self.apply_order_ref(order, client_tag)
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(2)
        self.check_rejected(trade)
        return normalize_order(trade)

    @route_to("orders_pool", mode="pinned", pinned_by="order_id")
    async def modify_order(self, order_id, stop_price=None, limit_price=None,
                     qty=None, symbol=None):
        """Modify an existing order's prices and/or qty in place, preserving ID."""
        self.ensure_connected()
        order_id_int = int(order_id)
        trade = None
        for t in self.ib.trades():
            if t.order.orderId == order_id_int:
                trade = t
                break
        if trade is None:
            raise ValueError(f"Order {order_id} not found")

        order = trade.order
        mod_symbol = trade.contract.symbol

        is_inverted_forex = (hasattr(trade.contract, 'secType')
                             and trade.contract.secType == "CASH"
                             and trade.contract.symbol == "USD")
        if is_inverted_forex:
            if stop_price is not None and stop_price > 0:
                stop_price = round(1.0 / float(stop_price), 5)
            if limit_price is not None and limit_price > 0:
                limit_price = round(1.0 / float(limit_price), 5)

        if mod_symbol in FUTURES_SPECS:
            if stop_price is not None:
                order.auxPrice = round_to_tick(stop_price, mod_symbol)
            if limit_price is not None:
                order.lmtPrice = round_to_tick(limit_price, mod_symbol)
        elif is_inverted_forex:
            if stop_price is not None:
                order.auxPrice = round(float(stop_price), 5)
            if limit_price is not None:
                order.lmtPrice = round(float(limit_price), 5)
        elif self.is_crypto(mod_symbol):
            # Match place_stop_limit_order: crypto prices pass RAW. 2dp rounding
            # would coarsen a sub-cent crypto stop (1.165 -> 1.17) and land it a
            # hair under the market -> instant full-position wick-out.
            if stop_price is not None:
                order.auxPrice = float(stop_price)
            if limit_price is not None:
                order.lmtPrice = float(limit_price)
        else:
            if stop_price is not None:
                order.auxPrice = round(float(stop_price), 2)
            if limit_price is not None:
                order.lmtPrice = round(float(limit_price), 2)
        if qty is not None:
            order.totalQuantity = float(qty)

        modified = self.ib.placeOrder(trade.contract, order)
        await asyncio.sleep(2)
        self.check_rejected(modified)
        return normalize_order(modified)

    @route_to("orders_pool", mode="scatter")
    async def global_cancel(self):
        """Cancel ALL open orders across all client sessions."""
        self.ensure_connected()
        self.ib.reqGlobalCancel()
        await asyncio.sleep(3)

    @route_to("orders_pool", mode="pinned", pinned_by="order_id")
    def get_order(self, order_id):
        """Get a single order by ID."""
        self.ensure_connected()
        order_id_int = int(order_id)
        for trade in self.ib.trades():
            if trade.order.orderId == order_id_int:
                return normalize_order(trade)
        raise ValueError(f"Order {order_id} not found")

    @route_to("orders_pool", mode="scatter", merge_id="id")
    def get_orders(self, status=None, after=None, until=None, limit=None):
        """Get orders with optional filters."""
        self.ensure_connected()
        if status == "open":
            # openTrades() can linger stale Trade objects after reconnect with
            # the same clientId. Filter to orders IBKR actually acknowledged
            # (have a permId), plus still-sending pendingsubmit orders.
            trades = []
            for t in self.ib.openTrades():
                status = t.orderStatus.status.lower()
                perm_id = t.orderStatus.permId
                if status in ("submitted", "presubmitted") and perm_id > 0:
                    trades.append(t)
                elif status == "pendingsubmit":
                    trades.append(t)
        else:
            trades = self.ib.trades()

        results = [normalize_order(t) for t in trades]

        if limit is not None:
            results = results[:limit]

        return results

    @route_to("orders_pool")
    async def list_all_open_orders(self):
        """All open orders across EVERY client (via reqAllOpenOrders), not just
        this connection's. The dashboard API connects as a different clientId than
        the agent, so it must call this to see the agent's working orders/stops.

        Return the FRESH snapshot reqAllOpenOrders resolves to — NOT self.ib.openTrades(),
        which is THIS connection's local cache. IBKR delivers order-status updates
        (including cancellations) only to the client that PLACED the order, so a stop the
        agent (a different clientId) cancels stays stuck at PreSubmitted in our cache
        indefinitely; openTrades() would then leak those phantom orders to the dashboard
        every poll. reqAllOpenOrders returns the broker's authoritative current open set,
        so cancelled orders simply aren't in it."""
        self.ensure_connected()
        trades = await self.ib.reqAllOpenOrdersAsync()
        return [normalize_order(t) for t in (trades or [])]

    @route_to("orders_pool", mode="scatter")
    async def cancel_order(self, order_id, timeout=8, poll_interval=0.5):
        """Cancel an order by ID on the connection that OWNS it, verifying the
        cancellation actually took effect at the broker.

        Runs on EVERY orders-pool connection (scatter). An order placed by one
        connection's clientId can only be cancelled by that same clientId —
        IBKR rejects a cancel from any other client (Error 10147) and ib_async
        does NOT raise on that async rejection. Scatter makes the cancel
        correct by construction: only the owning connection issues cancelOrder;
        every other no-ops. The owner polls until the order reaches a terminal
        state before reporting success.

        Returns a one-element list [outcome] from the owning connection and []
        from all others (flattened by the scatter layer). outcome status is one
        of: cancelled, already_terminal, unconfirmed.
        """
        self.ensure_connected()
        order_id_int = int(order_id)
        try:
            my_client_id = self.ib.client.clientId
        except Exception:
            my_client_id = None

        def find_owned():
            for trade in self.ib.trades():
                if trade.order.orderId != order_id_int:
                    continue
                owner = getattr(trade.order, "clientId", None)
                if (isinstance(my_client_id, int) and isinstance(owner, int)
                        and owner != 0 and owner != my_client_id):
                    return None
                return trade
            return None

        target_trade = find_owned()
        if target_trade is None:
            try:
                await self.ib.reqAllOpenOrdersAsync()
            except Exception as exc:
                log.warning("cancel_order(%s): reqAllOpenOrdersAsync failed on %s: %s",
                            order_id, my_client_id, exc)
            target_trade = find_owned()
        if target_trade is None:
            return []

        status = target_trade.orderStatus.status.lower()
        if status in ("cancelled", "inactive", "filled"):
            return [{"order_id": order_id_int, "outcome": "already_terminal",
                     "status": status}]

        self.ib.cancelOrder(target_trade.order)

        deadline = time.time() + timeout
        while time.time() < deadline:
            await asyncio.sleep(poll_interval)
            status = target_trade.orderStatus.status.lower()
            if status in ("cancelled", "inactive", "pendingcancel", "filled"):
                return [{"order_id": order_id_int, "outcome": "cancelled",
                         "status": status}]

        log.error(
            "cancel_order(%s): OWNER (clientId=%s) sent cancel but status "
            "still '%s' after %.1fs — order may still be LIVE at broker",
            order_id, my_client_id, target_trade.orderStatus.status, timeout,
        )
        return [{"order_id": order_id_int, "outcome": "unconfirmed",
                 "status": target_trade.orderStatus.status}]

    @route_to("orders_pool", mode="scatter", merge_id="id")
    def get_open_orders_for_symbol(self, symbol):
        """Get open orders for a specific symbol."""
        self.ensure_connected()
        trades = self.ib.openTrades()
        results = []
        ibkr_sym = self.ibkr_symbol(symbol)
        for trade in trades:
            if trade.contract.symbol == ibkr_sym:
                results.append(normalize_order(trade))
        return results

    @route_to("data_pool")
    def get_tradeable_assets(self, asset_type=AssetType.STOCK):
        """Get tradeable assets — the raw list of what exists, never ranked.

        Crypto: IBKR-supported coins as SYM/USD pairs. Forex: the major
        IDEALPRO pairs. Futures: the contracts in FUTURES_SPECS. Each is the
        COMPLETE infra enumeration of what the broker offers, never a filtered
        or ranked shortlist — the agent surveys it by reasoning. Stocks: empty
        (IBKR has no list-all API).
        """
        if asset_type == AssetType.CRYPTO:
            # IBKR crypto (ZeroHash/Paxos) is live-only; a paper account cannot
            # trade it, so the tradeable list is empty when paper.
            if self.is_paper():
                return []
            return [
                {"symbol": f"{sym}/USD", "name": sym, "exchange": "ZEROHASH",
                 "tradable": True, "asset_class": "crypto", "fractionable": True}
                for sym in SUPPORTED_CRYPTO
            ]
        if asset_type == AssetType.FOREX:
            return [
                {"symbol": pair, "name": pair, "exchange": "IDEALPRO",
                 "tradable": True, "asset_class": "forex", "fractionable": False}
                for pair in FOREX_UNIVERSE
            ]
        if asset_type == AssetType.FUTURES:
            return [
                {"symbol": sym, "name": sym,
                 "exchange": spec.get("exchange", "CME"),
                 "tradable": True, "asset_class": "futures", "fractionable": False}
                for sym, spec in FUTURES_SPECS.items()
            ]
        return []

    @route_to("data_pool")
    async def get_snapshot(self, symbol, asset_type=None):
        """Get market snapshot for a symbol."""
        self.ensure_connected()
        contract = await self.make_contract(symbol, asset_type)
        # Fall back to delayed data so an account without a real-time
        # subscription (paper accounts, or unsubscribed forex/futures feeds)
        # returns quotes instead of an all-zeros snapshot. With a live
        # subscription IBKR still serves real-time.
        try:
            self.ib.reqMarketDataType(3)
        except Exception:
            pass
        ticker = self.ib.reqMktData(contract, "", False, False)
        # Streaming ticks arrive asynchronously; a single fixed sleep often
        # reads before the first tick lands (the all-zeros symptom). Poll
        # briefly until a usable price arrives.
        for _ in range(12):
            await asyncio.sleep(0.25)
            if safe_float(getattr(ticker, "last", None)) or safe_float(getattr(ticker, "close", None)):
                break

        if ticker is None:
            return {}

        last = safe_float(getattr(ticker, "last", None)) or safe_float(getattr(ticker, "close", None))
        open_price = safe_float(getattr(ticker, "open", None))
        high = safe_float(getattr(ticker, "high", None))
        low = safe_float(getattr(ticker, "low", None))
        close = safe_float(getattr(ticker, "close", None))
        volume = safe_float(getattr(ticker, "volume", None))

        return {
            "latestTrade": {
                "p": float(last) if last else 0.0,
                "s": 0.0,
                "t": "",
            },
            "dailyBar": {
                "o": float(open_price),
                "h": float(high),
                "l": float(low),
                "c": float(close),
                "v": float(volume),
                "t": "",
            },
            "prevDailyBar": {
                "c": 0.0,
                "v": 0.0,
            },
        }

    @route_to("data_pool")
    async def get_snapshots(self, symbols, asset_type=None):
        """Get market snapshots for multiple symbols.

        Requests all market-data subscriptions up front, waits once, then reads
        all tickers — faster than sequential per-symbol requests.
        """
        if not symbols:
            return {}
        self.ensure_connected()
        # Delayed-data fallback (see get_snapshot) so unsubscribed feeds return
        # quotes instead of all-zeros.
        try:
            self.ib.reqMarketDataType(3)
        except Exception:
            pass

        contracts = []
        for sym in symbols:
            contract = await self.make_contract(sym, asset_type)
            self.ib.reqMktData(contract, "", False, False)
            contracts.append((sym, contract))

        await asyncio.sleep(2)

        results = {}
        for sym, contract in contracts:
            ticker = self.ib.ticker(contract)
            if ticker is None:
                results[sym] = {}
                continue
            last = safe_float(getattr(ticker, "last", None)) or safe_float(getattr(ticker, "close", None))
            open_price = safe_float(getattr(ticker, "open", None))
            high = safe_float(getattr(ticker, "high", None))
            low = safe_float(getattr(ticker, "low", None))
            close = safe_float(getattr(ticker, "close", None))
            volume = safe_float(getattr(ticker, "volume", None))
            results[sym] = {
                "latestTrade": {"p": float(last) if last else 0.0, "s": 0.0, "t": ""},
                "dailyBar": {"o": float(open_price), "h": float(high),
                             "l": float(low), "c": float(close),
                             "v": float(volume), "t": ""},
                "prevDailyBar": {"c": 0.0, "v": 0.0},
            }
        return results

    @route_to("data_pool", timeout=120)
    async def get_bars(self, symbols, asset_type=None, timeframe="1Day",
                 start=None, limit=None):
        """Get historical bars using IBKR historical data."""
        self.ensure_connected()
        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            return {}

        bar_size_map = {
            "1Day": "1 day",
            "1Hour": "1 hour",
            "1Min": "1 min",
            "5Min": "5 mins",
            "15Min": "15 mins",
            "1Week": "1 week",
        }
        bar_size = bar_size_map.get(timeframe, "1 day")

        bars_needed = limit or 80
        if start is not None:
            try:
                from datetime import datetime, date
                if "T" in str(start):
                    start_dt = datetime.fromisoformat(str(start)).date()
                else:
                    start_dt = date.fromisoformat(str(start)[:10])
                days_diff = (date.today() - start_dt).days + 5
                duration = f"{max(1, days_diff)} D"
            except (ValueError, TypeError):
                duration = "60 D"
        elif timeframe == "1Day":
            duration = f"{max(1, bars_needed + 10)} D"
        elif timeframe == "1Hour":
            days_needed = max(1, (bars_needed // 24) + 2)
            duration = f"{days_needed} D"
        elif timeframe == "1Min":
            duration = f"{bars_needed * 60} S"
        elif timeframe == "5Min":
            duration = f"{max(1, bars_needed * 5 * 60)} S"
        elif timeframe == "15Min":
            duration = f"{max(1, bars_needed * 15 * 60)} S"
        elif timeframe == "1Week":
            duration = f"{max(1, bars_needed)} W"
        else:
            duration = "80 D"

        if asset_type == AssetType.FOREX:
            what_to_show = "MIDPOINT"
        elif asset_type == AssetType.CRYPTO:
            what_to_show = "AGGTRADES"
        else:
            what_to_show = "TRADES"
        use_rth = asset_type not in (AssetType.FOREX, AssetType.FUTURES, AssetType.CRYPTO)
        if use_rth and bar_size in ("1 min", "5 mins", "15 mins") and start is not None:
            try:
                from datetime import datetime as dt_cls
                from zoneinfo import ZoneInfo
                et = ZoneInfo("America/New_York")
                if "T" in str(start):
                    s = dt_cls.fromisoformat(str(start))
                    if s.tzinfo is None:
                        s = s.replace(tzinfo=et)
                    s_et = s.astimezone(et)
                    if s_et.hour < 9 or (s_et.hour == 9 and s_et.minute < 30):
                        use_rth = False
            except Exception:
                pass

        # IBKR MIDPOINT 1-day caps at ~1 year; clamp so a misconfigured caller
        # can't silently time out (Error 366).
        if what_to_show == "MIDPOINT" and bar_size == "1 day":
            try:
                head = duration.strip().split()
                if len(head) == 2 and head[1] == "D" and int(head[0]) > 365:
                    log.warning("[ibkr] MIDPOINT 1-day duration %s exceeds IBKR's "
                                "1-year cap; clamping to '365 D'", duration)
                    duration = "365 D"
            except (ValueError, IndexError):
                pass

        results = {}
        # IBKR TRADES 1-day fetches cap at ~280 calendar days per call. For
        # longer durations, paginate 280-day windows backwards and merge.
        stock_daily_paginate = what_to_show == "TRADES" and bar_size == "1 day"
        requested_days = None
        if stock_daily_paginate:
            try:
                head = duration.strip().split()
                if len(head) == 2 and head[1] == "D":
                    requested_days = int(head[0])
            except (ValueError, IndexError):
                requested_days = None

        for sym in symbols:
            try:
                contract = await self.make_contract(sym, asset_type)
                if (stock_daily_paginate and requested_days
                        and requested_days > 280):
                    from datetime import datetime as paginate_dt
                    from datetime import timezone as paginate_tz
                    from datetime import timedelta as paginate_td
                    chunk_days = 280
                    now_utc = paginate_dt.now(paginate_tz.utc)
                    seen = set()
                    accumulated = []
                    chunks = (requested_days + chunk_days - 1) // chunk_days
                    for i in range(chunks):
                        if i == 0:
                            end = ""
                            csize = min(chunk_days, requested_days)
                        else:
                            end = now_utc - paginate_td(days=i * chunk_days)
                            csize = min(chunk_days,
                                        requested_days - i * chunk_days)
                        if csize <= 0:
                            break
                        chunk_bars = await self.ib.reqHistoricalDataAsync(
                            contract,
                            endDateTime=end,
                            durationStr=f"{csize} D",
                            barSizeSetting=bar_size,
                            whatToShow=what_to_show,
                            useRTH=use_rth,
                            timeout=15,
                        )
                        added = 0
                        for bar in (chunk_bars or []):
                            key = str(bar.date)
                            if key in seen:
                                continue
                            seen.add(key)
                            accumulated.append(bar)
                            added += 1
                        if added == 0:
                            break
                    accumulated.sort(key=lambda b: b.date)
                    bars = accumulated
                else:
                    bars = await self.ib.reqHistoricalDataAsync(
                        contract,
                        endDateTime="",
                        durationStr=duration,
                        barSizeSetting=bar_size,
                        whatToShow=what_to_show,
                        useRTH=use_rth,
                        timeout=15,
                    )
                normalized = []
                for bar in bars:
                    normalized.append({
                        "t": str(bar.date),
                        "o": float(bar.open),
                        "h": float(bar.high),
                        "l": float(bar.low),
                        "c": float(bar.close),
                        "v": float(bar.volume),
                    })
                results[sym] = normalized
            except Exception as exc:
                log.warning("[ibkr] get_bars failed for %s: %s", sym, exc)

        return results

    @route_to("orders_pool", mode="scatter", merge_id="id", timeout=20)
    def get_fill_activities(self, after=None):
        """Get fill (trade execution) activities for the current session."""
        self.ensure_connected()
        fills = self.ib.fills()
        return [normalize_fill(f) for f in fills]

    @route_to("orders_pool", mode="scatter", merge_id="id", timeout=20)
    async def get_historical_executions(self, symbol=None, side=None, days=7):
        """Query IBKR for historical executions (up to 7 days back).

        Unlike get_fill_activities (current session only), this requests
        execution reports from IBKR's servers via reqExecutions.
        """
        from ib_async import ExecutionFilter
        self.ensure_connected()
        filt = ExecutionFilter()
        if symbol:
            filt.symbol = symbol.replace("/", "")
        if side:
            filt.side = "BOT" if side == "buy" else "SLD"
        trades = await self.ib.reqExecutionsAsync(filt)
        results = []
        for trade in trades:
            for fill in trade.fills:
                results.append(normalize_fill(fill))
        return results

    @route_to("status_pool")
    async def get_session_close(self, target_date):
        """Return target_date's NYSE session close as a UTC datetime, or None.

        Queries SPY's contract details for liquidHours, parses the entry
        matching target_date. Half-day sessions return the half-day close.
        Holidays / weekends return None. Times in liquidHours are exchange-local
        (ET); converted to UTC before return.
        """
        return await self.session_close_from_gateway(target_date)

    async def session_close_from_gateway(self, target_date):
        """liquidHours body of get_session_close, undecorated so routed
        methods (market_session_now) can await it directly — re-dispatching
        through route_to from inside a routed call would hand back a raw
        coroutine (pool re-entry) or asyncio.run() inside a running loop
        (non-pool mode). Raises when the gateway can't be reached."""
        from datetime import datetime as dt, timezone
        from zoneinfo import ZoneInfo

        self.ensure_connected()
        target_str = target_date.strftime("%Y%m%d")
        spy = Stock("SPY", "SMART", "USD")
        details_list = await self.ib.reqContractDetailsAsync(spy)
        if not details_list:
            log.warning("[ibkr] get_session_close: no contract details for SPY")
            return None
        liquid_hours = (details_list[0].liquidHours or "")
        et = ZoneInfo("America/New_York")
        for entry in liquid_hours.split(";"):
            entry = entry.strip()
            if not entry.startswith(target_str + ":"):
                continue
            tail = entry[len(target_str) + 1:]
            if tail.upper() == "CLOSED":
                return None
            last_window = tail.split(",")[-1]
            try:
                close_part = last_window.split("-")[1]
            except IndexError:
                log.warning("[ibkr] get_session_close: malformed entry %r", entry)
                return None
            try:
                hh = int(close_part[:2])
                mm = int(close_part[2:4])
            except (ValueError, IndexError):
                log.warning("[ibkr] get_session_close: bad close time %r", close_part)
                return None
            close_et = dt.combine(target_date, dt.min.time(),
                                   tzinfo=et).replace(hour=hh, minute=mm)
            return close_et.astimezone(timezone.utc)
        return None

    async def class_windows_from_gateway(self, asset_class):
        """UTC trading windows for the class's representative contract, from
        the gateway's contract details (tradingHours, NOT liquidHours — the
        overnight Globex session IS tradeable). forex → EUR/USD IDEALPRO;
        futures → front-month ES (CME Globex). Undecorated (route_to must not
        re-enter); raises when the gateway can't answer. A representative-
        contract proxy, same pattern as SPY for the stock session — a raw
        schedule fact, no opinions.
        """
        self.ensure_connected()
        if asset_class == "forex":
            contract = Forex("EURUSD", exchange="IDEALPRO")
            await self.ib.qualifyContractsAsync(contract)
        elif asset_class == "futures":
            contract = await self.resolve_front_month("ES")
        else:
            raise ValueError(f"no representative contract for {asset_class!r}")
        details_list = await self.ib.reqContractDetailsAsync(contract)
        if not details_list:
            raise ValueError(f"no contract details for {asset_class} representative")
        det = details_list[0]
        return parse_trading_hours(det.tradingHours or "",
                                   det.timeZoneId or "US/Eastern")

    async def class_open_now(self, asset_class, fallback):
        """True when the class's representative contract is inside a live
        trading window right now (broker truth; windows cached per ET date,
        failures never cached). Returns `fallback` (the caller's weekday-math
        answer) when the gateway can't say, so an outage degrades to the
        pre-1.4.0 behavior."""
        import datetime as dt
        from zoneinfo import ZoneInfo

        now = dt.datetime.now(dt.timezone.utc)
        key = (asset_class, now.astimezone(ZoneInfo("America/New_York")).date())
        windows = self.class_windows_by_date.get(key)
        if windows is None:
            try:
                windows = await asyncio.wait_for(
                    self.class_windows_from_gateway(asset_class), timeout=10)
                self.class_windows_by_date[key] = windows
            except Exception as exc:
                log.warning("[ibkr] %s availability gate: gateway can't answer "
                            "(%s) — using weekday time math", asset_class, exc)
                return fallback
        return any(start <= now < end for start, end in windows)

    @route_to("status_pool")
    async def get_available_types(self):
        """Return which asset types can be traded right now.

        Keys are real asset types only. `stock` is True during the regular
        session (holiday-aware via the liquidHours session gate — see
        market_session_now), and during pre/after-hours windows when
        self.extended_hours is set. Forex/Futures: gated on the LIVE trading
        windows of a representative contract (EUR/USD IDEALPRO; ES front
        month) so holiday halts and early closes come from the broker; the
        Sun-5PM-to-Fri-5PM weekday math survives only as the fallback when
        the gateway can't answer. Crypto: 24/7. Options: regular session only.
        """
        import datetime as dt
        from zoneinfo import ZoneInfo

        now = dt.datetime.now(dt.timezone.utc)
        et = now.astimezone(ZoneInfo("America/New_York"))
        weekday = et.weekday()

        weekday_fx_open = True
        if weekday == 5:                          # Saturday
            weekday_fx_open = False
        elif weekday == 4 and et.hour >= 17:      # Friday 5 PM+ ET
            weekday_fx_open = False
        elif weekday == 6 and et.hour < 17:       # Sunday before 5 PM ET
            weekday_fx_open = False

        forex_open = await self.class_open_now("forex", weekday_fx_open)
        futures_open = await self.class_open_now("futures", weekday_fx_open)

        session = await self.market_session_now()
        stock_open = session == "regular"
        if session == "extended" and self.extended_hours:
            stock_open = True

        return {
            "stock": stock_open,
            # IBKR crypto is unavailable on paper accounts (Paxos/ZeroHash is
            # live-only), so report it untradeable when paper — factual, not a
            # view. Otherwise crypto trades 24/7.
            "crypto": not self.is_paper(),
            "forex": forex_open,
            "futures": futures_open,
            # US listed options follow the regular equity session (no extended/weekend).
            "options": session == "regular",
        }

    @route_to("status_pool")
    async def get_market_session(self):
        """Return the current US stock-market session: regular/extended/closed.

        Holiday- and half-day-aware — gated on today's session close from SPY
        liquidHours (broker truth, cached per ET date); see market_session_now.
        """
        return await self.market_session_now()

    async def market_session_now(self):
        """Session logic shared by get_market_session / get_available_types —
        undecorated so both routed methods can await it directly (see
        session_close_from_gateway for why re-dispatching is unsafe).

        A date the gateway confirms has no session is 'closed' outright —
        no extended windows on holidays. Regular runs 9:30 to the liquidHours
        close (13:00 on half-days); extended is 4:00-9:30 pre-market and
        close-20:00 after-hours (nominal — half-day after-hours actually ends
        17:00). Falls back to the pre-1.3.0 pure weekday time math when the
        gateway can't answer, so an outage degrades to the old answer rather
        than calling a live session 'closed'.
        """
        import datetime as dt
        from zoneinfo import ZoneInfo

        now = dt.datetime.now(dt.timezone.utc)
        et = now.astimezone(ZoneInfo("America/New_York"))
        d = et.date()
        close_utc, known = None, False
        if d in self.session_close_by_date:
            close_utc, known = self.session_close_by_date[d], True
        else:
            try:
                close_utc = await asyncio.wait_for(
                    self.session_close_from_gateway(d), timeout=10)
                self.session_close_by_date[d] = close_utc
                known = True
            except Exception as exc:
                log.warning("[ibkr] session gate: liquidHours unavailable (%s) — "
                            "falling back to weekday time math", exc)
        if known:
            if close_utc is None:
                return "closed"
            market_open = et.replace(hour=9, minute=30, second=0, microsecond=0)
            if market_open <= et and now < close_utc:
                return "regular"
            pre_open = et.replace(hour=4, minute=0, second=0, microsecond=0)
            post_close = et.replace(hour=20, minute=0, second=0, microsecond=0)
            if pre_open <= et < market_open:
                return "extended"
            if now >= close_utc and et < post_close:
                return "extended"
            return "closed"

        # Gateway unreachable — legacy holiday-blind weekday math.
        weekday = et.weekday()
        stock_open = False
        if weekday < 5:
            market_open = et.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = et.replace(hour=16, minute=0, second=0, microsecond=0)
            stock_open = market_open <= et < market_close
        if stock_open:
            return "regular"

        if weekday < 5:
            pre_open = et.replace(hour=4, minute=0, second=0, microsecond=0)
            pre_close = et.replace(hour=9, minute=30, second=0, microsecond=0)
            post_open = et.replace(hour=16, minute=0, second=0, microsecond=0)
            post_close = et.replace(hour=20, minute=0, second=0, microsecond=0)
            if (pre_open <= et < pre_close) or (post_open <= et < post_close):
                return "extended"
        return "closed"

    @route_to("data_pool")
    async def get_option_chain(self, symbol, expiry_range_days=60):
        """Fetch available option expirations and strikes for an underlying.

        Returns {'expirations': [...], 'strikes': [...]} filtered to SMART
        exchange and expirations within expiry_range_days. A raw data lookup,
        not a recommendation.
        """
        import datetime as dt

        self.ensure_connected()
        underlying = Stock(self.ibkr_symbol(symbol), "SMART", "USD")
        await self.ib.qualifyContractsAsync(underlying)
        con_id = underlying.conId

        chains = await self.ib.reqSecDefOptParamsAsync(symbol, "", "STK", con_id)
        if not chains:
            log.warning("No option chains returned for %s", symbol)
            return {"expirations": [], "strikes": []}

        chain = None
        for c in chains:
            if c.exchange == "SMART":
                chain = c
                break
        if chain is None:
            chain = chains[0]

        today = dt.date.today()
        cutoff = today + dt.timedelta(days=expiry_range_days)

        valid_expirations = []
        for exp in sorted(chain.expirations):
            try:
                exp_date = dt.datetime.strptime(exp, "%Y%m%d").date()
            except ValueError:
                continue
            if today < exp_date <= cutoff:
                valid_expirations.append(exp)

        return {
            "expirations": valid_expirations,
            "strikes": sorted(chain.strikes),
            "exchange": chain.exchange,
            "multiplier": chain.multiplier,
        }

    @route_to("data_pool")
    async def get_option_greeks(self, symbol, expiry, strike, right):
        """Fetch option Greeks for a specific contract.

        Returns delta/gamma/theta/vega/impliedVol plus bid/ask/last. A raw
        data lookup; the agent decides what to make of it. Empty dict on
        failure.
        """
        self.ensure_connected()
        contract = Option(
            self.ibkr_symbol(symbol), expiry, float(strike), right,
            "SMART", multiplier="100",
        )
        qualified = await self.ib.qualifyContractsAsync(contract)
        if not qualified:
            log.warning("Could not qualify option %s %s %.2f%s", symbol, expiry, strike, right)
            return {}

        tickers = await self.ib.reqTickersAsync(contract)
        if not tickers:
            return {}

        ticker = tickers[0]
        greeks = getattr(ticker, "modelGreeks", None)

        result = {
            "bid": safe_float(ticker.bid),
            "ask": safe_float(ticker.ask),
            "last": safe_float(ticker.last),
            "volume": safe_float(ticker.volume),
            "open_interest": safe_float(getattr(ticker, "callOpenInterest", 0)
                                        if right == "C" else
                                        getattr(ticker, "putOpenInterest", 0)),
        }

        if greeks:
            result.update({
                "delta": safe_float(greeks.delta),
                "gamma": safe_float(greeks.gamma),
                "theta": safe_float(greeks.theta),
                "vega": safe_float(greeks.vega),
                "impliedVol": safe_float(greeks.impliedVol),
                "undPrice": safe_float(greeks.undPrice),
            })
        else:
            result.update({
                "delta": 0.0, "gamma": 0.0, "theta": 0.0,
                "vega": 0.0, "impliedVol": 0.0, "undPrice": 0.0,
            })

        return result
