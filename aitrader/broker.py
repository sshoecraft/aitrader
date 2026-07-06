"""Broker abstraction for the trader package.

Defines the Broker ABC. Broker implementations live in aitrader/brokers/.
The broker MCP server is the sole owner of broker connections (it
    instantiates the connection, runs the wait() pump in its own thread,
    and handles reconnect). See aitrader/brokers/ibkr_connection.py.
"""

__version__ = "2.4.0"

import threading
from abc import ABC, abstractmethod
from concurrent.futures import Future

from aitrader.asset_types import AssetType


class Broker(ABC):
    """Abstract base class for broker implementations.

    AlpacaBroker and IBKRBroker are the concrete drivers.
    All methods return plain dicts (not SDK-specific types).
    """

    def submit_async(self, method_name, *args, **kwargs):
        """Fire a broker call asynchronously. Returns a concurrent.futures.Future.

        Default implementation: spawn a daemon thread per call. Subclasses
        that have a native async path (IBKR connection pool, Alpaca
        thread-pool executor) should OVERRIDE this to dispatch without
        creating a new thread per invocation.
        """
        future: Future = Future()

        def runner():
            try:
                future.set_result(getattr(self, method_name)(*args, **kwargs))
            except Exception as exc:
                future.set_exception(exc)

        threading.Thread(
            target=runner,
            name=f"{self.name}-submit-{method_name}",
            daemon=True,
        ).start()
        return future

    name = None  # Subclasses must set: "alpaca", "ibkr"

    @abstractmethod
    def connect(self):
        """Connect to the broker. Called once by the command module on startup."""
        ...

    @abstractmethod
    def reconnect(self):
        """Reconnect after a connection failure."""
        ...

    @abstractmethod
    def wait(self):
        """Called every loop iteration by the command module. Yields CPU.

        IBKR: processes ib_async callbacks via ib.sleep(0.1).
        Alpaca: yields CPU via time.sleep(0.1).
        """
        ...

    @abstractmethod
    def get_account(self):
        """Get account info. Returns dict with cash, equity, buying_power, portfolio_value."""
        ...

    @abstractmethod
    def get_portfolio_history(self, period="1D", timeframe="1D", date_end=None):
        """Get portfolio history. Returns dict with base_value, equity list, etc.

        Args:
            period: Duration like "1D", "1W", "1M".
            timeframe: Resolution like "1Min", "1D".
            date_end: Optional date string (YYYY-MM-DD) to anchor the end of the window.
                      If None, defaults to today (current market date).
        """
        ...

    @abstractmethod
    def get_positions(self):
        """Get all open positions. Returns list of dicts."""
        ...

    @abstractmethod
    def close_position(self, symbol):
        """Close a position by symbol. Returns order dict."""
        ...

    @abstractmethod
    def place_limit_order(self, symbol, qty, side, limit_price, tif="day",
                          outside_rth=False):
        """Place a limit order. Returns order dict."""
        ...

    @abstractmethod
    def place_stop_limit_order(self, symbol, qty, side, stop_price,
                               limit_price, tif="day"):
        """Place a stop-limit order. Returns order dict."""
        ...

    @abstractmethod
    def place_stop_order(self, symbol, qty, side, stop_price, tif="day"):
        """Place a stop-market order. Returns order dict."""
        ...

    @abstractmethod
    def modify_order(self, order_id, stop_price=None, limit_price=None,
                     qty=None, symbol=None):
        """Modify an existing order's price(s) and/or qty in place. Returns order dict.

        Raises ValueError if the order is not found.
        Note: Alpaca returns a new order ID (replacement); IBKR preserves the ID.
        symbol is optional — used by Alpaca for correct rounding of crypto prices.
        """
        ...

    @abstractmethod
    def get_order(self, order_id):
        """Get a single order by ID. Returns order dict."""
        ...

    @abstractmethod
    def get_orders(self, status=None, after=None, until=None, limit=None):
        """Get orders with optional filters. Returns list of order dicts."""
        ...

    def list_all_open_orders(self):
        """All open orders in the account, across every client connection.

        Default = get_orders(status="open"): correct for brokers whose account is
        a single shared view (Alpaca, MYSE) — every order is visible regardless of
        which client placed it. IBKR overrides this (reqAllOpenOrders) because each
        clientId otherwise sees only its own orders, and the dashboard connects on
        a different clientId than the agent."""
        return self.get_orders(status="open")

    @abstractmethod
    def cancel_order(self, order_id):
        """Cancel an order by ID."""
        ...

    @abstractmethod
    def get_open_orders_for_symbol(self, symbol):
        """Get open orders for a specific symbol. Returns list of order dicts."""
        ...

    @abstractmethod
    def get_tradeable_assets(self, asset_type=AssetType.STOCK):
        """Get tradeable assets. Returns list of asset dicts."""
        ...

    @abstractmethod
    def get_snapshot(self, symbol, asset_type=None):
        """Get market snapshot for a symbol. Returns snapshot dict."""
        ...

    @abstractmethod
    def get_snapshots(self, symbols, asset_type=None):
        """Get market snapshots for multiple symbols. Returns dict of {symbol: snapshot}."""
        ...

    @abstractmethod
    def get_bars(self, symbols, asset_type=None, timeframe="1Day",
                 start=None, limit=None):
        """Get historical bars. Returns dict of {symbol: [bar, ...]}."""
        ...

    @abstractmethod
    def get_fill_activities(self, after=None):
        """Get fill (trade execution) activities. Returns list of activity dicts."""
        ...

    def get_historical_executions(self, symbol=None, side=None, days=7):
        """Query broker for historical executions (up to N days back).

        Default returns empty — brokers that support historical queries
        override this (e.g. IBKR reqExecutions).
        """
        return []

    @abstractmethod
    def get_available_types(self):
        """Return which asset types can be traded right now.

        Session-truth check: implementations gate the stock/options answer
        on the broker's own trading calendar when reachable (holiday- and
        half-day-aware, cached per date — so this MAY make one broker call
        per day), degrading to pure weekday time-math only when the
        calendar can't be consulted. Never True for stocks on a market
        holiday when the calendar is reachable.
        Returns dict of {asset_type_str: bool}, e.g.:
            {"stock": True, "crypto": True, "forex": False, "futures": False}

        Keys are real asset types ONLY (stock, crypto, forex, futures).
        `stock` is True when stocks are tradeable right now: during the
        regular session always, and during the pre/after-hours windows
        when the `extended_hours` setting is enabled. The regular-vs-
        extended-vs-closed distinction lives in get_market_session().

        Each broker only includes types it supports.
        """
        ...

    @abstractmethod
    def get_market_session(self):
        """Return the current US stock-market session as a string.

        One of: "regular"  — regular session open (9:30 ET to the session
                             close; 13:00 ET on half-days)
                "extended" — pre-market or after-hours window on a trading day
                "closed"   — outside all stock trading windows, weekends,
                             and market holidays (holidays have NO extended
                             windows)

        A session-clock fact, holiday-aware: gated on the broker calendar
        when reachable (cached per date), weekday time-math fallback when
        not. Does NOT consult the `extended_hours` setting.
        Consumers that need the regular-vs-extended distinction (monitor
        trailing/session-close, bandwagon entry cutoff) read this; the
        setting only governs whether get_available_types() reports
        `stock` tradeable during the extended window.
        """
        ...

    def get_session_close(self, target_date):
        """Return today's stock-market session close as a tz-aware UTC datetime.

        `target_date` is the calendar date to query (UTC). Returns None if
        the broker can't determine the close (not a trading day, not
        connected, query failed). Half-days return the half-day close
        (e.g. 13:00 ET on day-after-Thanksgiving, July 3 when applicable,
        Dec 24 when applicable).

        Default returns None — brokers that know the schedule override
        this. aitrader.market_calendar caches the result per date so the
        broker is queried at most once per calendar day.
        """
        return None

    @abstractmethod
    def wait_for_fill(self, order_id, timeout=300, poll_interval=2):
        """Poll order status until filled or timeout.

        Returns the filled order dict, or None if not filled within timeout.
        """
        ...

    def get_currency_balances(self):
        """List non-USD currency cash balances. Default: empty (single-currency broker)."""
        return []

    def flatten_currency(self, currency, min_usd=20.0):
        """Flatten a single non-USD currency back to USD. Default: not supported."""
        return {"currency": currency, "status": "skipped_unknown_currency",
                "error": f"{self.name} does not support multi-currency flatten"}

    def flatten_all_residual_currencies(self, min_usd=20.0):
        """Flatten every non-USD currency back to USD. Default: empty list."""
        return []

