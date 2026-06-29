"""Alpaca broker (alpaca-py SDK) — DATA + EXECUTION.

Alpaca can serve two independent roles, selected by config:
  - settings.data_broker = "alpaca"  -> market DATA (bars/snapshots/tradeable
    list) for the data_broker_types, in front of any execution broker.
  - settings.broker      = "alpaca"  -> EXECUTION (orders/positions/account).

Both roles use the same class; the broker MCP's router decides which methods
reach it. On the aitrader box (broker="ibkr"), only the data methods are ever
called; on a pure-Alpaca box (broker="alpaca"), execution flows here too.

Paper-vs-live for Alpaca is the `paper=` flag on the client (NOT a DU/DF account
id). The execution factory passes paper=(not allow_live), so it's paper by
default and only an explicit allow_live=true reaches the live endpoint — the
paper-only fuse for this backend.

All methods normalize SDK objects to the SAME plain-dict shapes aitrader's
IBKRBroker returns (latestTrade/dailyBar/prevDailyBar; t/o/h/l/c/v; orders carry
`order_ref` = your client_tag for idempotent reconcile).

PURE INFRA — no screening/ranking/signal; raw data + mechanical order primitives.
Unlike /src/trader's AlpacaBroker, this does NOT enforce long-only — the agent
owns sizing/direction (CLAUDE.md §2), matching aitrader's IBKR backend.
"""

__version__ = "0.4.0"

import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetAssetsRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    ReplaceOrderRequest,
    StopLimitOrderRequest,
    StopLossRequest,
    StopOrderRequest,
    TakeProfitRequest,
)
from alpaca.trading.enums import (
    AssetClass,
    AssetStatus,
    OrderClass,
    OrderSide,
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.historical.screener import ScreenerClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockSnapshotRequest,
    CryptoBarsRequest,
    CryptoSnapshotRequest,
)
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from aitrader.asset_types import AssetType, normalize_crypto_symbol
from aitrader.broker import Broker

log = logging.getLogger("alpaca")

# Bounded HTTP timeout (connect, read) seconds for every alpaca-py request.
# Finite so a stalled socket can never block a thread forever; short enough that a
# stale pooled keep-alive connection fails fast instead of hanging the dashboard.
# Fixed (no env var) — aitrader is configured via settings.toml only.
HTTP_CONNECT_TIMEOUT_SEC = 5.0
HTTP_READ_TIMEOUT_SEC = 12.0
HTTP_TIMEOUT_SEC = (HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC)


def enum_val(obj):
    """Extract .value from an SDK enum, or fall back to str()."""
    if hasattr(obj, "value"):
        return obj.value
    return str(obj) if obj is not None else ""


def is_crypto(symbol):
    """True if a symbol is a crypto pair (contains / or BTCUSD-style)."""
    if "/" in symbol:
        return True
    # Alpaca normalizes crypto symbols by stripping the slash: BTC/USD -> BTCUSD.
    # Stock tickers never end in "USD" with a 3+ char base (no AAPLUSD, etc.).
    s = symbol.upper()
    return s.endswith("USD") and len(s) >= 6


def pround(val, places=2):
    """Precision round — format to a string and parse back to kill float drift."""
    return float(f"{val:.{places}f}")


def round_price(price, symbol):
    """Round price: 2 decimals for stocks, 8 for crypto (sub-penny prices)."""
    return round(float(price), 8 if is_crypto(symbol) else 2)


def tif_enum(tif, symbol=None):
    """Convert a string time-in-force to the SDK enum (case-insensitive).

    Crypto rejects DAY, so silently mapping an unrecognized value to DAY (e.g.
    an uppercase "GTC" that misses the lowercase keys) yields a cryptic broker
    "invalid crypto time_in_force" error. Normalize case; reject real typos.

    Crypto only accepts GTC/IOC. The tools default tif="day", so an unspecified
    crypto order would be rejected; coerce the DAY default (empty/None/"day") to
    GTC for crypto symbols. An explicit stock-only tif (opg/cls/fok) on crypto is
    left to fail at the broker — that's a deliberate bad choice, not a default."""
    if not tif:
        return TimeInForce.GTC if symbol and is_crypto(symbol) else TimeInForce.DAY
    mapping = {
        "day": TimeInForce.DAY, "gtc": TimeInForce.GTC, "opg": TimeInForce.OPG,
        "cls": TimeInForce.CLS, "ioc": TimeInForce.IOC, "fok": TimeInForce.FOK,
    }
    key = str(tif).strip().lower()
    if key not in mapping:
        raise ValueError(f"unknown time_in_force {tif!r}; valid: {', '.join(mapping)}")
    if key == "day" and symbol and is_crypto(symbol):
        return TimeInForce.GTC
    return mapping[key]


def side_enum(side):
    """Convert a string side to the SDK enum (case-insensitive).

    The old `BUY if side=="buy" else SELL` silently turned any non-exact match
    (e.g. "BUY", "Buy") into a SELL — a wrong-direction trade. Match on the
    normalized value and reject anything that isn't buy/sell."""
    key = str(side).strip().lower()
    if key == "buy":
        return OrderSide.BUY
    if key == "sell":
        return OrderSide.SELL
    raise ValueError(f"unknown order side {side!r}; valid: buy, sell")


def normalize_account(acct):
    """Convert TradeAccount to aitrader's account dict."""
    return {
        "cash": str(acct.cash),
        "equity": str(acct.equity),
        "buying_power": str(acct.buying_power),
        "portfolio_value": str(acct.equity),
        "long_market_value": str(getattr(acct, "long_market_value", 0)),
        "short_market_value": str(getattr(acct, "short_market_value", 0)),
        "pattern_day_trader": getattr(acct, "pattern_day_trader", False),
        "daytrade_count": getattr(acct, "daytrade_count", 0),
        "daytrading_buying_power": str(getattr(acct, "daytrading_buying_power", 0)),
        "status": enum_val(getattr(acct, "status", "")),
        "account": str(getattr(acct, "account_number", "") or getattr(acct, "id", "")),
    }


def normalize_position(pos):
    """Convert Position to aitrader's position dict."""
    return {
        "symbol": normalize_crypto_symbol(str(pos.symbol)),
        "qty": str(pos.qty),
        "qty_available": str(getattr(pos, "qty_available", pos.qty)),
        "avg_entry_price": str(pos.avg_entry_price),
        "current_price": str(pos.current_price),
        "market_value": str(pos.market_value),
        "unrealized_pl": str(pos.unrealized_pl),
        "unrealized_plpc": str(pos.unrealized_plpc),
        "side": enum_val(getattr(pos, "side", "long")),
        "cost_basis": str(getattr(pos, "cost_basis", "0")),
        "asset_class": enum_val(getattr(pos, "asset_class", "")),
    }


def normalize_order(order):
    """Convert Order to aitrader's order dict. `order_ref` carries the client tag
    (Alpaca client_order_id) for idempotent reconcile — same role as IBKR's
    orderRef."""
    return {
        "id": str(order.id),
        "symbol": normalize_crypto_symbol(str(order.symbol)),
        "side": enum_val(order.side),
        "qty": str(getattr(order, "qty", "") or ""),
        "filled_qty": str(getattr(order, "filled_qty", "") or ""),
        "filled_avg_price": str(getattr(order, "filled_avg_price", "") or ""),
        "status": enum_val(order.status),
        "type": enum_val(order.type),
        "time_in_force": enum_val(order.time_in_force),
        "order_class": enum_val(getattr(order, "order_class", "")),
        "limit_price": str(getattr(order, "limit_price", "") or ""),
        "stop_price": str(getattr(order, "stop_price", "") or ""),
        "created_at": str(getattr(order, "created_at", "")),
        "order_ref": str(getattr(order, "client_order_id", "") or ""),
    }


def normalize_activity(act):
    """Convert a fill-activity dict/object to aitrader's activity dict."""
    if isinstance(act, dict):
        return {
            "id": act.get("id", ""),
            "symbol": normalize_crypto_symbol(act.get("symbol", "")),
            "side": act.get("side", ""),
            "qty": act.get("qty", ""),
            "price": act.get("price", ""),
            "transaction_time": act.get("transaction_time", ""),
            "order_id": act.get("order_id", ""),
            "type": act.get("type", ""),
        }
    return {
        "id": str(getattr(act, "id", "")),
        "symbol": normalize_crypto_symbol(str(getattr(act, "symbol", ""))),
        "side": str(getattr(act, "side", "")),
        "qty": str(getattr(act, "qty", "")),
        "price": str(getattr(act, "price", "")),
        "transaction_time": str(getattr(act, "transaction_time", "")),
        "order_id": str(getattr(act, "order_id", "")),
        "type": str(getattr(act, "type", "")),
    }


def normalize_bar(bar):
    """Convert an SDK Bar to aitrader's bar dict: t, o, h, l, c, v."""
    return {
        "t": str(bar.timestamp) if bar.timestamp else "",
        "o": float(bar.open),
        "h": float(bar.high),
        "l": float(bar.low),
        "c": float(bar.close),
        "v": float(bar.volume),
    }


def normalize_snapshot(snap):
    """Convert an SDK Snapshot to aitrader's nested snapshot dict.

    Matches IBKRBroker.get_snapshot output:
        snapshot["latestTrade"]["p"|"s"|"t"]
        snapshot["dailyBar"]["o"|"h"|"l"|"c"|"v"|"t"]
        snapshot["prevDailyBar"]["c"|"v"|...]
        snapshot["latestBar"][...]   (when a minute/latest bar is present)
    """
    result = {}

    lt = getattr(snap, "latest_trade", None)
    if lt is not None:
        result["latestTrade"] = {
            "p": float(lt.price),
            "s": float(getattr(lt, "size", 0)),
            "t": str(lt.timestamp) if lt.timestamp else "",
        }
    else:
        result["latestTrade"] = {}

    db = getattr(snap, "daily_bar", None)
    if db is not None:
        result["dailyBar"] = {
            "o": float(db.open),
            "h": float(db.high),
            "l": float(db.low),
            "c": float(db.close),
            "v": float(db.volume),
            "t": str(db.timestamp) if db.timestamp else "",
        }
    else:
        result["dailyBar"] = {}

    pdb = getattr(snap, "previous_daily_bar", None)
    if pdb is not None:
        result["prevDailyBar"] = {
            "o": float(pdb.open),
            "h": float(pdb.high),
            "l": float(pdb.low),
            "c": float(pdb.close),
            "v": float(pdb.volume),
            "t": str(pdb.timestamp) if pdb.timestamp else "",
        }
    else:
        result["prevDailyBar"] = {}

    lb = getattr(snap, "minute_bar", None) or getattr(snap, "latest_bar", None)
    if lb is not None:
        result["latestBar"] = {
            "o": float(lb.open),
            "h": float(lb.high),
            "l": float(lb.low),
            "c": float(lb.close),
            "v": float(lb.volume),
            "t": str(lb.timestamp) if lb.timestamp else "",
        }

    return result


def enforce_http_timeout(client, timeout=HTTP_TIMEOUT_SEC):
    """Force a default request timeout AND stale-connection retry onto an
    alpaca-py client's session.

    Two failure modes this guards against on a long-lived process (the dashboard
    API, the agent's broker MCP):

    1. alpaca-py calls ``self._session.request(method, url, **opts)`` with no
       timeout, so a stalled socket blocks the calling thread indefinitely. We
       inject a (connect, read) timeout so a stall becomes a prompt exception.
    2. A pooled keep-alive connection that Alpaca's load balancer closed after
       idle is silently reused on the next call; that dead socket blocks until
       the read timeout, which under the /status lock looks like a permanent hang.
       We mount a urllib3 Retry that transparently reopens a fresh connection.

    The retry is **GET-only for read timeouts** (allowed_methods={GET,HEAD,
    OPTIONS}) so a slow order POST/cancel is NEVER silently re-sent — only
    idempotent reads (account/positions/orders/bars, i.e. the dashboard) retry.
    Connect-level failures are retried for all methods (no request was sent).
    """
    session = getattr(client, "_session", None)
    if session is None:
        return
    if getattr(session, "aitrader_timeout_wrapped", False):
        return

    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    # connect=3 reopens a fresh socket when a pooled keep-alive connection was
    # dropped (the stale-connection hang). read=0: do NOT retry read timeouts — a
    # read timeout means the request reached Alpaca but it isn't responding (e.g.
    # a degraded /v2/orders endpoint); retrying only multiplies the wait. Let it
    # fail once so the caller can degrade. GET/HEAD/OPTIONS only, so order
    # POST/cancel is never silently re-sent.
    retry = Retry(
        total=3, connect=3, read=0, backoff_factor=0.3,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    original_request = session.request

    def request_with_timeout(*args, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return original_request(*args, **kwargs)

    session.request = request_with_timeout
    session.aitrader_timeout_wrapped = True


class AlpacaBroker(Broker):
    """Alpaca broker — data + execution (role selected by config; see module
    docstring). paper=(not allow_live) is the paper-only fuse for this backend."""

    name = "alpaca"

    DEFAULT_ASYNC_WORKERS = 8

    def __init__(self, api_key, secret_key, paper=True, data_feed="iex"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        # Stock data feed for bars + snapshots: "iex" (real-time, IEX-only
        # volume) or "sip" (full consolidated tape — paid plan; free/basic plans
        # delay it ~15 min and block recent SIP). See config.alpaca_data_feed.
        self.data_feed = data_feed
        self.trading = None
        self.stock_data = None
        self.crypto_data = None
        self.async_executor: ThreadPoolExecutor | None = None
        # Lazily-created HTTP session for the Yahoo classification lookup
        # (Alpaca's own API carries no sector/industry). See get_classification.
        self.yf_session = None

    # ── connection ──────────────────────────────────────────────────────

    def connect(self):
        # paper=self.paper selects the paper vs live endpoint — the paper-only
        # fuse for Alpaca (paper=True physically cannot touch a live account).
        self.trading = TradingClient(self.api_key, self.secret_key, paper=self.paper)
        self.stock_data = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.crypto_data = CryptoHistoricalDataClient(self.api_key, self.secret_key)
        self.screener = ScreenerClient(self.api_key, self.secret_key)
        for client in (self.trading, self.stock_data, self.crypto_data, self.screener):
            enforce_http_timeout(client)
        # Verify credentials/connectivity with a cheap read.
        self.trading.get_account()

    def reconnect(self):
        self.connect()

    def resolve_feed(self):
        """Map the configured data_feed string to the DataFeed enum (default
        IEX). Used as the default feed for stock bars + snapshots."""
        return DataFeed.SIP if str(self.data_feed).lower() == "sip" else DataFeed.IEX

    def get_top_movers(self, top_n=20):
        """Factual market movers: the top % gainers and losers in US stocks right
        now, straight from Alpaca's screener (the vendor's published movers list,
        like CNBC's). DATA ONLY — ranked by raw % change, no edge or buy/sell
        opinion; the agent confirms each name on the bars before acting."""
        from alpaca.data.requests import MarketMoversRequest
        n = max(1, int(top_n))
        m = self.screener.get_market_movers(MarketMoversRequest(top=n))
        def row(x):
            return {"symbol": x.symbol, "pct_change": float(x.percent_change),
                    "price": float(x.price), "change": float(x.change)}
        return {
            "gainers": [row(g) for g in (m.gainers or [])],
            "losers": [row(l) for l in (m.losers or [])],
            "as_of": str(getattr(m, "last_updated", "")),
        }

    def get_most_actives(self, top_n=20, by="volume"):
        """Factual most-active US stocks right now, straight from Alpaca's
        screener (the vendor's published most-active list). Ranked by raw
        trading activity — `by='volume'` (shares) or `by='trades'` (trade
        count) — NOT by % move, edge, or buy/sell opinion. This is where the
        large, liquid, institutionally-traded names live, which the % movers
        feed (`get_top_movers`) buries under low-float pump stocks. DATA ONLY:
        a name being most-active says nothing about direction — it can be
        ripping up OR getting dumped. The agent pulls bars/snapshots on these
        to decide what's actually moving with strength. Returns
        {actives:[{symbol, volume, trade_count}], by, as_of}."""
        from alpaca.data.requests import MostActivesRequest
        n = max(1, int(top_n))
        kind = "trades" if str(by).lower().startswith("trade") else "volume"
        m = self.screener.get_most_actives(MostActivesRequest(top=n, by=kind))
        return {
            "actives": [
                {"symbol": x.symbol, "volume": int(x.volume),
                 "trade_count": int(x.trade_count)}
                for x in (m.most_actives or [])
            ],
            "by": kind,
            "as_of": str(getattr(m, "last_updated", "")),
        }

    def get_classification(self, symbol, asset_type=None):
        """Equity sector/industry for a symbol — factual published reference
        data, mirroring IBKRBroker.get_classification. Alpaca's API carries NO
        fundamental classification, so this reads Yahoo Finance's keyless
        quote-search endpoint (the same published sector/industry a quote page
        shows). A mechanical lookup of the security's classification — NOT a
        screen, score, ranking, or opinion. Only equities carry one; the
        crypto/forex/futures the dashboard skips never reach here. Network
        failures return {} so the dashboard degrades to 'Unclassified' rather
        than erroring (and the caller caches that definitive answer)."""
        sym = (symbol or "").strip().upper()
        if not sym:
            return {}
        # Alpaca writes share classes with a dot (BRK.B); Yahoo uses a dash
        # (BRK-B). Query and match on Yahoo's form.
        yf_sym = sym.replace(".", "-")
        if self.yf_session is None:
            import requests
            self.yf_session = requests.Session()
            self.yf_session.headers.update({"User-Agent": "Mozilla/5.0"})
        try:
            r = self.yf_session.get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": yf_sym, "quotesCount": 10, "newsCount": 0},
                timeout=8,
            )
            r.raise_for_status()
            quotes = r.json().get("quotes") or []
        except Exception:
            return {}
        # Search is fuzzy (a query for AAPL also returns AAPL34.SA); take the
        # quote whose symbol EXACTLY matches the request, never a near-name.
        match = next(
            (q for q in quotes if str(q.get("symbol", "")).upper() == yf_sym), None)
        if match is None:
            return {}
        sector = (match.get("sector") or match.get("sectorDisp") or "").strip()
        industry = (match.get("industry") or match.get("industryDisp") or "").strip()
        # ETFs/funds carry no single sector in the feed; bucket them by security
        # type the way the IBKR path does, so a fund reads "ETF"/"Fund" rather
        # than "Unclassified" — still a factual security-type fact, not opinion.
        if not sector:
            qt = (match.get("quoteType") or match.get("typeDisp") or "").strip().upper()
            if qt in ("ETF", "ETN", "ETP", "ETC"):
                sector = "ETF"
            elif qt in ("MUTUALFUND", "FUND"):
                sector = "Fund"
        return {"sector": sector or None, "industry": industry or None}

    def wait(self):
        _time.sleep(0.1)

    def submit_async(self, method_name, *args, **kwargs):
        """Persistent ThreadPoolExecutor (8 workers) — avoids a fresh thread per
        call. Lazy-created so callers that never go async pay nothing."""
        if self.async_executor is None:
            self.async_executor = ThreadPoolExecutor(
                max_workers=self.DEFAULT_ASYNC_WORKERS,
                thread_name_prefix="alpaca-async",
            )
        return self.async_executor.submit(
            getattr(self, method_name), *args, **kwargs,
        )

    # ── account + positions ─────────────────────────────────────────────

    def get_account(self):
        return normalize_account(self.trading.get_account())

    def get_portfolio_history(self, period="1D", timeframe="1D", date_end=None):
        from datetime import date as date_type
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        params = {"period": period, "timeframe": timeframe}
        if date_end is not None:
            params["date_end"] = (date_type.fromisoformat(date_end)
                                  if isinstance(date_end, str) else date_end)
        h = self.trading.get_portfolio_history(
            history_filter=GetPortfolioHistoryRequest(**params))
        return {
            "base_value": float(h.base_value) if h.base_value else 0.0,
            "equity": [float(e) for e in h.equity] if h.equity else [],
            "profit_loss": [float(p) for p in h.profit_loss] if h.profit_loss else [],
            "profit_loss_pct": [float(p) for p in h.profit_loss_pct] if h.profit_loss_pct else [],
            "timestamp": list(h.timestamp) if h.timestamp else [],
            "timeframe": str(h.timeframe) if h.timeframe else timeframe,
        }

    def get_positions(self):
        return [normalize_position(p) for p in self.trading.get_all_positions()]

    def get_position(self, symbol):
        return normalize_position(self.trading.get_open_position(symbol.replace("/", "")))

    def get_position_qty(self, symbol):
        try:
            return float(self.trading.get_open_position(symbol.replace("/", "")).qty)
        except Exception:
            return 0.0

    def close_position(self, symbol, client_tag=None):
        # client_tag accepted for API parity; Alpaca's close endpoint assigns its
        # own offsetting-order id.
        return normalize_order(self.trading.close_position(symbol.replace("/", "")))

    # ── order placement ─────────────────────────────────────────────────

    def place_market_order(self, symbol, qty, side, tif="day", notional=None,
                           asset_type=None, client_tag=None):
        params = {"symbol": symbol, "side": side_enum(side),
                  "time_in_force": tif_enum(tif, symbol)}
        if notional is not None:
            params["notional"] = round(float(notional), 2)
        else:
            params["qty"] = float(qty)
        if client_tag:
            params["client_order_id"] = str(client_tag)
        return normalize_order(self.trading.submit_order(MarketOrderRequest(**params)))

    def place_limit_order(self, symbol, qty, side, limit_price, tif="day",
                          asset_type=None, outside_rth=False, extended_hours=None,
                          client_tag=None):
        params = {
            "symbol": symbol, "qty": float(qty), "side": side_enum(side),
            "time_in_force": tif_enum(tif, symbol),
            "limit_price": round_price(limit_price, symbol),
        }
        if extended_hours is not None:
            params["extended_hours"] = extended_hours
        elif outside_rth and not is_crypto(symbol):
            params["extended_hours"] = True
        if client_tag:
            params["client_order_id"] = str(client_tag)
        return normalize_order(self.trading.submit_order(LimitOrderRequest(**params)))

    def place_stop_order(self, symbol, qty, side, stop_price, tif="day",
                         asset_type=None, client_tag=None):
        params = {
            "symbol": symbol, "qty": float(qty), "side": side_enum(side),
            "time_in_force": tif_enum(tif, symbol),
            "stop_price": round_price(stop_price, symbol),
        }
        if client_tag:
            params["client_order_id"] = str(client_tag)
        return normalize_order(self.trading.submit_order(StopOrderRequest(**params)))

    def place_stop_limit_order(self, symbol, qty, side, stop_price, limit_price,
                               tif="day", asset_type=None, outside_rth=False,
                               client_tag=None):
        params = {
            "symbol": symbol, "qty": float(qty), "side": side_enum(side),
            "time_in_force": tif_enum(tif, symbol),
            "stop_price": round_price(stop_price, symbol),
            "limit_price": round_price(limit_price, symbol),
        }
        if client_tag:
            params["client_order_id"] = str(client_tag)
        return normalize_order(self.trading.submit_order(StopLimitOrderRequest(**params)))

    def place_bracket_order(self, symbol, qty, side, limit_price, stop_loss,
                            take_profit, tif="day", stop_limit_price=None,
                            client_tag=None):
        """Bracket = entry limit + stop-loss + take-profit. Stocks use Alpaca's
        native OCO bracket; crypto is simulated (Alpaca has no native crypto
        bracket and no naked crypto stop-market)."""
        if is_crypto(symbol):
            return self._place_crypto_bracket(symbol, qty, side, limit_price,
                                              stop_loss, take_profit,
                                              stop_limit_price, client_tag)
        sl_limit = stop_limit_price if stop_limit_price else pround(stop_loss * 0.995)
        params = {
            "symbol": symbol, "qty": float(qty), "side": side_enum(side),
            "time_in_force": tif_enum(tif, symbol),
            "limit_price": round_price(limit_price, symbol),
            "order_class": OrderClass.BRACKET,
            "stop_loss": StopLossRequest(
                stop_price=round_price(stop_loss, symbol),
                limit_price=round_price(sl_limit, symbol)),
            "take_profit": TakeProfitRequest(
                limit_price=round_price(take_profit, symbol)),
        }
        if client_tag:
            params["client_order_id"] = str(client_tag)
        return normalize_order(self.trading.submit_order(LimitOrderRequest(**params)))

    def _place_crypto_bracket(self, symbol, qty, side, limit_price, stop_loss,
                              take_profit, stop_limit_price, client_tag):
        buy = self.place_market_order(symbol, qty, side, tif="gtc",
                                      client_tag=client_tag)
        filled = self.wait_for_fill(buy["id"], timeout=300)
        if filled is None:
            try:
                self.cancel_order(buy["id"])
            except Exception:
                pass
            raise RuntimeError(
                f"Crypto bracket buy for {symbol} did not fill within 300s; "
                f"cancelled — no unprotected position.")
        filled_qty = float(filled.get("filled_qty", qty))
        try:  # crypto fees come out of the asset; use the real position qty
            filled_qty = float(self.get_position(symbol).get("qty", filled_qty))
        except Exception:
            pass
        sl_limit = stop_limit_price if stop_limit_price else pround(stop_loss * 0.995)
        stop_order = None
        try:
            stop_order = self.place_stop_limit_order(
                symbol, filled_qty, "sell", stop_loss, sl_limit, tif="gtc")
        except Exception:
            try:
                q = float(self.get_position(symbol).get("qty", 0))
                if q > 0:
                    stop_order = self.place_stop_limit_order(
                        symbol, q, "sell", stop_loss, sl_limit, tif="gtc")
            except Exception:
                pass
        result = dict(filled)
        result["stop_order_id"] = stop_order["id"] if stop_order else None
        return result

    def modify_order(self, order_id, stop_price=None, limit_price=None,
                     qty=None, symbol=None):
        """Modify an order's price(s)/qty. Alpaca REPLACES (new id); the order
        dict's id changes. symbol is used only for crypto price rounding."""
        sym = symbol or ""
        kwargs = {}
        if stop_price is not None:
            kwargs["stop_price"] = round_price(stop_price, sym)
        if limit_price is not None:
            kwargs["limit_price"] = round_price(limit_price, sym)
        if qty is not None:
            # ReplaceOrderRequest types qty as int — fractional crypto fails
            # pydantic; only forward whole quantities (price-only modify still ok).
            iq = int(qty)
            if iq == qty:
                kwargs["qty"] = iq
        return normalize_order(
            self.trading.replace_order_by_id(order_id, ReplaceOrderRequest(**kwargs)))

    # ── order queries ───────────────────────────────────────────────────

    def get_order(self, order_id):
        return normalize_order(self.trading.get_order_by_id(order_id))

    def get_orders(self, status=None, after=None, until=None, limit=None):
        params = {}
        if status is not None:
            params["status"] = {
                "open": QueryOrderStatus.OPEN, "closed": QueryOrderStatus.CLOSED,
                "all": QueryOrderStatus.ALL,
            }.get(status, QueryOrderStatus.ALL)
        if after is not None:
            params["after"] = after
        if until is not None:
            params["until"] = until
        if limit is not None:
            params["limit"] = limit
        req = GetOrdersRequest(**params) if params else None
        return [normalize_order(o) for o in self.trading.get_orders(filter=req)]

    def cancel_order(self, order_id, timeout=8, poll_interval=0.5):
        """Cancel and wait (up to timeout) for terminal confirmation. Returns the
        order dict."""
        try:
            self.trading.cancel_order_by_id(order_id)
        except Exception as exc:
            return {"id": str(order_id), "status": "cancel_failed", "error": str(exc)}
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                o = self.get_order(order_id)
            except Exception:
                break
            if o.get("status", "").lower() in (
                    "canceled", "cancelled", "filled", "expired", "rejected"):
                return o
            _time.sleep(poll_interval)
        try:
            return self.get_order(order_id)
        except Exception:
            return {"id": str(order_id), "status": "canceled"}

    def global_cancel(self):
        """Cancel ALL open orders at Alpaca. Blunt instrument."""
        self.trading.cancel_orders()
        return {"status": "all_cancelled"}

    def get_open_orders_for_symbol(self, symbol):
        symbols = [symbol]
        if is_crypto(symbol):
            alt = symbol.replace("/", "") if "/" in symbol else normalize_crypto_symbol(symbol)
            if alt != symbol:
                symbols.append(alt)
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=symbols)
        return [normalize_order(o) for o in self.trading.get_orders(filter=req)]

    def wait_for_fill(self, order_id, timeout=300, poll_interval=2):
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            order = self.get_order(order_id)
            status = order.get("status", "").lower()
            if "filled" in status and "partial" not in status:
                return order
            if status in ("canceled", "cancelled", "expired", "rejected"):
                return None
            _time.sleep(poll_interval)
        return None

    def get_fill_activities(self, after=None):
        """All FILL activities (paginated). after = ISO str / datetime; default
        30 days back."""
        if after is None:
            after_str = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
                "%Y-%m-%dT00:00:00Z")
        elif isinstance(after, str):
            after_str = f"{after}T00:00:00Z" if len(after) == 10 else after
        else:
            after_str = after.isoformat()

        all_acts = []
        params = f"after={after_str}&direction=asc&page_size=100"
        page_token = None
        while True:
            path = f"/account/activities/FILL?{params}"
            if page_token:
                path += f"&page_token={page_token}"
            page = self.trading.get(path)
            if not isinstance(page, list) or not page:
                break
            all_acts.extend(normalize_activity(a) for a in page)
            last_id = (page[-1].get("id") if isinstance(page[-1], dict)
                       else str(getattr(page[-1], "id", "")))
            if not last_id:
                break
            page_token = last_id
        return all_acts

    # ── options: not supported by Alpaca (clear error, not AttributeError) ─

    def get_option_chain(self, symbol, expiry_range_days=60):
        raise NotImplementedError("Alpaca backend does not support option chains")

    def get_option_greeks(self, symbol, expiry, strike, right):
        raise NotImplementedError("Alpaca backend does not support option greeks")

    # ── tradeable universe (raw list — never ranked) ────────────────────

    def get_tradeable_assets(self, asset_type=AssetType.STOCK):
        asset_class_map = {
            AssetType.STOCK: AssetClass.US_EQUITY,
            AssetType.CRYPTO: AssetClass.CRYPTO,
        }
        ac = asset_class_map.get(asset_type)
        if ac is None:
            raise ValueError(f"Asset type {asset_type} not supported by Alpaca")

        request = GetAssetsRequest(asset_class=ac, status=AssetStatus.ACTIVE)
        assets = self.trading.get_all_assets(filter=request)
        result = []
        for a in assets:
            if not a.tradable:
                continue
            result.append({
                "symbol": str(a.symbol),
                "name": str(getattr(a, "name", "")),
                "exchange": enum_val(getattr(a, "exchange", "")),
                "tradable": bool(a.tradable),
                "asset_class": enum_val(getattr(a, "asset_class", "")),
                "fractionable": bool(getattr(a, "fractionable", False)),
            })
        return result

    # ── snapshots ───────────────────────────────────────────────────────

    def get_snapshot(self, symbol, asset_type=None):
        if asset_type == AssetType.CRYPTO or is_crypto(symbol):
            return self.get_crypto_snapshot(symbol)
        return self.get_stock_snapshot(symbol)

    def get_stock_snapshot(self, symbol):
        request = StockSnapshotRequest(symbol_or_symbols=symbol,
                                       feed=self.resolve_feed())
        snaps = self.stock_data.get_stock_snapshot(request)
        snap = snaps.get(symbol)
        if snap is None:
            return {}
        return normalize_snapshot(snap)

    def get_crypto_snapshot(self, symbol):
        symbol = normalize_crypto_symbol(symbol)
        request = CryptoSnapshotRequest(symbol_or_symbols=symbol)
        snaps = self.crypto_data.get_crypto_snapshot(request)
        snap = snaps.get(symbol)
        if snap is None:
            return {}
        return normalize_snapshot(snap)

    def get_snapshots(self, symbols, asset_type=None):
        if asset_type == AssetType.CRYPTO or (symbols and is_crypto(symbols[0])):
            return self.get_crypto_snapshots(symbols)
        return self.get_stock_snapshots(symbols)

    def get_stock_snapshots(self, symbols):
        if not symbols:
            return {}
        # Batch in groups of 200 (Alpaca limit).
        all_snaps = {}
        for i in range(0, len(symbols), 200):
            batch = symbols[i:i + 200]
            request = StockSnapshotRequest(symbol_or_symbols=batch,
                                           feed=self.resolve_feed())
            snaps = self.stock_data.get_stock_snapshot(request)
            for sym, snap in snaps.items():
                all_snaps[sym] = normalize_snapshot(snap)
        return all_snaps

    def get_crypto_snapshots(self, symbols):
        if not symbols:
            return {}
        symbols = [normalize_crypto_symbol(s) for s in symbols]
        request = CryptoSnapshotRequest(symbol_or_symbols=symbols)
        snaps = self.crypto_data.get_crypto_snapshot(request)
        result = {}
        for sym, snap in snaps.items():
            result[sym] = normalize_snapshot(snap)
        return result

    # ── bars ────────────────────────────────────────────────────────────

    def get_bars(self, symbols, asset_type=None, timeframe="1Day",
                 start=None, limit=None, end=None, feed=None, adjustment=None):
        if asset_type == AssetType.CRYPTO or (symbols and is_crypto(
                symbols[0] if isinstance(symbols, list) else symbols)):
            return self.get_crypto_bars(symbols, timeframe, start, end, limit)
        return self.get_stock_bars(symbols, timeframe, start, end, limit,
                                   feed, adjustment)

    def parse_timeframe(self, timeframe):
        mapping = {
            "1Day": TimeFrame.Day,
            "1Hour": TimeFrame.Hour,
            "1Min": TimeFrame.Minute,
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Week": TimeFrame.Week,
            "1Month": TimeFrame.Month,
        }
        return mapping.get(timeframe, TimeFrame.Day)

    @staticmethod
    def default_start_for_limit(timeframe, limit):
        """When a caller asks for "last N bars" via limit-only (no start), pick a
        start that just covers N bars of recent history.

        Alpaca returns bars chronologically from `start` and caps at `limit` — it
        has NO native "last N bars" mode. Passing start = 80 days ago with
        limit=12 on 5Min returns the FIRST 12 bars from 80 days ago, not the
        latest 12. So when only `limit` is set, compute a start covering ~4x the
        nominal window (absorbs weekends/halts) and trim client-side.
        """
        minutes_per_bar = {
            "1Min": 1, "5Min": 5, "15Min": 15,
            "1Hour": 60, "1Day": 24 * 60,
            "1Week": 7 * 24 * 60, "1Month": 30 * 24 * 60,
        }.get(timeframe, 24 * 60)
        window_min = max(30, minutes_per_bar * limit * 4)
        return datetime.now(timezone.utc) - timedelta(minutes=window_min)

    def get_stock_bars(self, symbols, timeframe, start, end, limit,
                       feed=None, adjustment=None):
        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            return {}

        tf = self.parse_timeframe(timeframe)
        latest_n_intent = (start is None and end is None
                           and limit is not None and limit > 0)
        if latest_n_intent:
            start = self.default_start_for_limit(timeframe, limit)
            trim_to = int(limit)
            limit = None
        else:
            trim_to = None
            if start is None:
                start = datetime.now(timezone.utc) - timedelta(days=80)
            elif isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if end is not None and isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))

        # Default feed comes from config (self.data_feed): IEX is real-time but
        # IEX-only volume; SIP is the full consolidated tape but a free/basic
        # plan delays it ~15 min and blocks recent SIP outright (so default-SIP
        # silently returns intraday bars ~15 min stale — useless for momentum).
        # Default IEX keeps the live tape real-time; a SIP-entitled node sets
        # alpaca_data_feed="sip" for full-volume coverage. Callers needing
        # full-session historical volume can still pass feed=DataFeed.SIP.
        if feed is None:
            feed = self.resolve_feed()

        all_bars = {}
        for i in range(0, len(symbols), 200):
            batch = symbols[i:i + 200]
            params = {
                "symbol_or_symbols": batch,
                "timeframe": tf,
                "start": start,
                "feed": feed,
            }
            if end is not None:
                params["end"] = end
            if limit:
                params["limit"] = limit
            if adjustment is not None:
                params["adjustment"] = adjustment

            request = StockBarsRequest(**params)
            barset = self.stock_data.get_stock_bars(request)
            for sym, bars in barset.data.items():
                all_bars.setdefault(sym, []).extend(normalize_bar(b) for b in bars)

        if trim_to is not None:
            for sym in list(all_bars.keys()):
                all_bars[sym] = all_bars[sym][-trim_to:]
        return all_bars

    def get_crypto_bars(self, symbols, timeframe, start, end, limit):
        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            return {}

        # Alpaca crypto data API requires slash format.
        symbols = [normalize_crypto_symbol(s) for s in symbols]

        tf = self.parse_timeframe(timeframe)
        latest_n_intent = (start is None and end is None
                           and limit is not None and limit > 0)
        if latest_n_intent:
            start = self.default_start_for_limit(timeframe, limit)
            trim_to = int(limit)
            limit = None
        else:
            trim_to = None
            if start is None:
                start = datetime.now(timezone.utc) - timedelta(days=80)
            elif isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if end is not None and isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))

        all_bars = {}
        params = {
            "symbol_or_symbols": symbols,
            "timeframe": tf,
            "start": start,
        }
        if end is not None:
            params["end"] = end
        if limit:
            params["limit"] = limit

        request = CryptoBarsRequest(**params)
        barset = self.crypto_data.get_crypto_bars(request)
        for s, bars in barset.data.items():
            all_bars.setdefault(s, []).extend(normalize_bar(b) for b in bars)

        if trim_to is not None:
            for s in list(all_bars.keys()):
                all_bars[s] = all_bars[s][-trim_to:]
        return all_bars

    # ── time facts (pure clock math + calendar) ─────────────────────────

    def get_market_session(self):
        """Current US stock session: 'regular' | 'extended' | 'closed'.

        Pure ET time math (Mon-Fri). Regular 9:30-16:00; extended is the
        4:00-9:30 pre-market and 16:00-20:00 after-hours windows.
        """
        from zoneinfo import ZoneInfo
        now = datetime.now(timezone.utc)
        et = now.astimezone(ZoneInfo("America/New_York"))
        if et.weekday() >= 5:
            return "closed"
        market_open = et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = et.replace(hour=16, minute=0, second=0, microsecond=0)
        if market_open <= et < market_close:
            return "regular"
        pre_open = et.replace(hour=4, minute=0, second=0, microsecond=0)
        post_close = et.replace(hour=20, minute=0, second=0, microsecond=0)
        if (pre_open <= et < market_open) or (market_close <= et < post_close):
            return "extended"
        return "closed"

    def get_available_types(self):
        """Which asset types Alpaca can serve right now. Stock = regular session;
        crypto = 24/7. Alpaca has no forex/futures."""
        return {
            "stock": self.get_market_session() == "regular",
            "crypto": True,
        }

    def get_session_close(self, target_date):
        """target_date's NYSE session close as a tz-aware UTC datetime, or None.

        Uses Alpaca's /v2/calendar — knows holidays AND half-days. None if
        target_date is not a trading day.
        """
        from zoneinfo import ZoneInfo
        from alpaca.trading.requests import GetCalendarRequest
        try:
            entries = self.trading.get_calendar(
                GetCalendarRequest(start=target_date, end=target_date)
            )
        except Exception as exc:
            log.warning("[alpaca] get_session_close failed: %s", exc)
            return None
        if not entries:
            return None
        entry = entries[0]
        close_part = entry.close.time() if isinstance(entry.close, datetime) else entry.close
        close_et = datetime.combine(
            entry.date, close_part, tzinfo=ZoneInfo("America/New_York"))
        return close_et.astimezone(timezone.utc)
