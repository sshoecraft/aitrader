"""Execution/data broker router — the §A.3 data/execution seam.

aitrader can run with a separate market-DATA broker (Alpaca) in front of the
EXECUTION broker (IBKR), mirroring /src/trader's `broker=ibkr` +
`data_broker=alpaca` topology. This router is the seam: it owns both broker
objects and, per call, picks which one serves the method.

The agent never sees this. The MCP tools call ``broker().get_bars(...)`` exactly
as before; the router proxies to the right backend and both return the SAME
dict shapes. The ONLY observable change is that stock/crypto market data starts
coming back populated (Alpaca's tape covers pre-market, where IBKR's paper feed
returns nothing).

Routing rules (mirrors trader.command.resolve_broker, with one safety
refinement noted below):
  - No data broker configured        -> execution broker (IBKR), always.
  - Method is not a market-data method -> execution broker. Account, positions,
    orders, fills, place/modify/cancel — ALL stay on IBKR (the account of
    record). Only bars/snapshots/tradeable-list can be served by the data feed.
  - Market-data method whose asset_type is in data_broker_types -> data broker.
  - Anything else (incl. asset_type omitted) -> execution broker.

SAFETY REFINEMENT vs /src/trader: /src/trader routed a market-data call with NO
asset_type to the data broker. aitrader does NOT — an omitted/unknown asset_type
falls through to IBKR. IBKR can price every asset class; Alpaca only stock +
crypto. So a futures/forex/options data call that forgets to pass asset_type
must never be silently mis-served by Alpaca. The data broker is reached ONLY on
an EXPLICIT stock/crypto asset_type.

DELIBERATE NON-GOAL — do not "fix" this by inferring asset_type from the symbol.
That would duplicate IBKR `make_contract`'s heuristics (FUTURES_SPECS /
SUPPORTED_CRYPTO / forex-pair detection) in here and couple the router to the
driver. The router stays dumb. Instead the data-tool docstrings tell the agent
to pass asset_type='stock'/'crypto' to get the live feed; if it omits it, it
gets IBKR. The agent owns that call — by design.
"""

__version__ = "0.1.0"

from aitrader.asset_types import AssetType

# Market-data methods the data broker MAY serve. Deliberately NARROW: only true
# market facts. Notably absent — get_fill_activities: fills are account-of-record
# data and aitrader's account lives on IBKR (Alpaca's paper account is a
# different account), so fills ALWAYS come from IBKR or reconcile breaks.
DATA_METHODS = frozenset([
    "get_bars",
    "get_snapshot",
    "get_snapshots",
    "get_tradeable_assets",
])


class BrokerRouter:
    """Routes broker calls between an execution broker and an optional data
    broker. Transparent proxy: any method not defined here dispatches per the
    rules in the module docstring."""

    def __init__(self, execution, data=None, data_broker_types=None):
        self.execution = execution
        self.data = data
        self.data_broker_types = (
            list(data_broker_types) if data_broker_types else None)

    def resolve(self, method, kwargs):
        """Return the broker that should serve `method` given its call kwargs."""
        if self.data is None:
            return self.execution
        if method not in DATA_METHODS:
            return self.execution
        asset_type = kwargs.get("asset_type")
        if asset_type is None:
            # Safety refinement (see module docstring): never let an omitted
            # asset_type reach the data broker — IBKR is the all-asset default.
            return self.execution
        key = asset_type.value if isinstance(asset_type, AssetType) else str(asset_type)
        if self.data_broker_types is not None and key not in self.data_broker_types:
            return self.execution
        return self.data

    def __getattr__(self, name):
        # __getattr__ fires only for names not found normally (execution/data/
        # data_broker_types/resolve are real attrs). Return a dispatcher that
        # resolves at CALL time, because asset_type is a call-time kwarg.
        def dispatch(*args, **kwargs):
            target = self.resolve(name, kwargs)
            return getattr(target, name)(*args, **kwargs)
        dispatch.__name__ = name
        return dispatch

    def data_feed_name(self):
        """Name of the broker serving market data: the data broker if one is
        configured, else the execution broker (which serves its own data)."""
        return self.data.name if self.data is not None else self.execution.name
