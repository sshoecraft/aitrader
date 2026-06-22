"""MYSE (My Stock Exchange) broker — REST execution backend (broker="myse").

Ported from /src/trader. A REST client for a local MYSE exchange (default
http://localhost:7777), a 24/7 simulated stock exchange. All methods normalize
MYSE's JSON to the SAME plain-dict shapes aitrader's other brokers return
(latestTrade/dailyBar/prevDailyBar; t/o/h/l/c/v; orders carry `order_ref` =
your client_tag). Session state comes from the exchange's /v1/clock — no
hardcoded hours.

Stocks only. Like the IBKR/Alpaca backends here, this does NOT enforce long-only
— the agent owns sizing/direction (CLAUDE.md §2); MYSE enforces its own rules
server-side. Configure with secrets.toml: myse_api_key (+ optional myse_host).
"""

__version__ = "0.3.0"

import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

from aitrader.asset_types import AssetType
from aitrader.broker import Broker

# Fixed HTTP timeout — finite so a stalled socket can't wedge a thread forever.
HTTP_TIMEOUT_SEC = 30.0
DEFAULT_HOST = "http://localhost:7777"


def normalize_account(acct):
    cash = float(acct.get("cash", 0))
    equity = float(acct.get("equity", cash))
    return {
        "cash": str(cash),
        "equity": str(equity),
        "buying_power": str(acct.get("buying_power", cash)),
        "portfolio_value": str(equity),
        "long_market_value": str(acct.get("position_market_value", 0)),
        "short_market_value": "0",
        "pattern_day_trader": False,
        "daytrade_count": 0,
        "daytrading_buying_power": str(acct.get("buying_power", cash)),
        "status": "ACTIVE",
        "account": str(acct.get("account_id", "MYSE")),
    }


def normalize_position(pos):
    qty = float(pos.get("qty", 0))
    avg = float(pos.get("avg_entry_price", 0))
    current = float(pos.get("current_price", avg))
    mv = float(pos.get("market_value", qty * current))
    cost = float(pos.get("cost_basis", qty * avg))
    upl = float(pos.get("unrealized_pl", mv - cost))
    upl_pct = (upl / cost) if cost else 0.0
    return {
        "symbol": str(pos.get("symbol", "")),
        "qty": str(qty),
        "qty_available": str(qty),
        "avg_entry_price": str(avg),
        "current_price": str(current),
        "market_value": str(mv),
        "unrealized_pl": str(upl),
        "unrealized_plpc": str(upl_pct),
        "side": str(pos.get("side", "long")),
        "cost_basis": str(cost),
        "asset_class": "us_equity",
    }


def normalize_order(order):
    tif = order.get("time_in_force") or order.get("tif") or "gtc"
    return {
        "id": str(order.get("id", "")),
        "symbol": str(order.get("symbol", "")),
        "side": str(order.get("side", "")),
        "qty": str(order.get("qty", "") or ""),
        "filled_qty": str(order.get("filled_qty", "") or ""),
        "filled_avg_price": str(order.get("avg_fill_price", "") or ""),
        "status": str(order.get("status", "")).lower(),
        "type": str(order.get("type", "")),
        "time_in_force": str(tif),
        "order_class": "simple",
        "limit_price": str(order.get("limit_price", "") or ""),
        "stop_price": str(order.get("stop_price", "") or ""),
        "created_at": str(order.get("created_at", "")),
        "order_ref": str(order.get("client_order_id", "") or ""),
    }


def normalize_bar(bar):
    return {
        "t": str(bar.get("ts", "") or bar.get("t", "")),
        "o": float(bar.get("o", 0)),
        "h": float(bar.get("h", 0)),
        "l": float(bar.get("l", 0)),
        "c": float(bar.get("c", 0)),
        "v": float(bar.get("v", 0)),
    }


def normalize_asset(a):
    return {
        "symbol": str(a.get("symbol", "")),
        "name": str(a.get("name", "")),
        "exchange": str(a.get("exchange", "MYSE")),
        "tradable": a.get("tradable", False),
        "asset_class": str(a.get("asset_class", "us_equity")),
        "fractionable": a.get("fractionable", False),
    }


class MYSEBroker(Broker):
    """MYSE REST broker (stocks only, 24/7 simulated exchange)."""

    name = "myse"

    DEFAULT_ASYNC_WORKERS = 8

    def __init__(self, host=DEFAULT_HOST, api_key=None, timeout=HTTP_TIMEOUT_SEC):
        if not api_key:
            raise ValueError("MYSE api_key required")
        self.host = host.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = None
        self.async_executor: ThreadPoolExecutor | None = None
        self.position_cache_lock = threading.Lock()

    def submit_async(self, method_name, *args, **kwargs):
        if self.async_executor is None:
            self.async_executor = ThreadPoolExecutor(
                max_workers=self.DEFAULT_ASYNC_WORKERS,
                thread_name_prefix="myse-async",
            )
        return self.async_executor.submit(
            getattr(self, method_name), *args, **kwargs,
        )

    # ── HTTP plumbing ────────────────────────────────────────────────

    def url(self, path):
        return f"{self.host}/v1{path}"

    def request(self, method, path, *, params=None, json=None, auth=True):
        headers = {}
        if auth:
            headers["x-api-key"] = self.api_key
        try:
            resp = self.session.request(
                method, self.url(path),
                params=params, json=json,
                headers=headers, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"MYSE {method} {path} failed: {exc}") from exc
        if resp.status_code == 404:
            raise LookupError(f"MYSE {method} {path}: 404")
        if not resp.ok:
            raise RuntimeError(
                f"MYSE {method} {path}: HTTP {resp.status_code} {resp.text[:200]}")
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def connect(self):
        self.session = requests.Session()
        self.request("GET", "/account")

    def reconnect(self):
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        self.connect()

    def wait(self):
        _time.sleep(0.1)

    # ── account / positions ──────────────────────────────────────────

    def get_account(self):
        return normalize_account(self.request("GET", "/account"))

    def get_portfolio_history(self, period="1D", timeframe="1D", date_end=None):
        # MYSE only knows the long-form bar labels (1Min/.../1Day).
        tf_alias = {"1D": "1Day", "1H": "1Hour", "1M": "1Min",
                    "5M": "5Min", "15M": "15Min", "30M": "30Min"}
        timeframe = tf_alias.get(timeframe, timeframe)
        params = {"period": period, "timeframe": timeframe}
        if date_end is not None:
            params["date_end"] = (date_end if isinstance(date_end, str)
                                  else date_end.isoformat())
        h = self.request("GET", "/account/portfolio_history", params=params)
        return {
            "base_value": float(h.get("base_value", 0)),
            "equity": [float(x) for x in (h.get("equity") or [])],
            "profit_loss": [float(x) for x in (h.get("profit_loss") or [])],
            "profit_loss_pct": [float(x) for x in (h.get("profit_loss_pct") or [])],
            "timestamp": list(h.get("timestamp") or []),
            "timeframe": str(h.get("timeframe", timeframe)),
        }

    def get_positions(self):
        positions = self.request("GET", "/positions") or []
        return [normalize_position(p) for p in positions]

    def get_position(self, symbol):
        return normalize_position(self.request("GET", f"/positions/{symbol}"))

    def get_position_qty(self, symbol):
        try:
            pos = self.request("GET", f"/positions/{symbol}")
            return float(pos.get("qty", 0))
        except LookupError:
            return 0.0

    def close_position(self, symbol, client_tag=None):
        held = self.get_position_qty(symbol)
        if held <= 0:
            raise ValueError(
                f"close_position({symbol}) but no long position (qty={held})")
        return normalize_order(self.request("DELETE", f"/positions/{symbol}"))

    # ── order placement ──────────────────────────────────────────────

    def post_order(self, body, client_tag=None):
        if client_tag:
            body["client_order_id"] = str(client_tag)
        return normalize_order(self.request("POST", "/orders", json=body))

    def place_market_order(self, symbol, qty, side, tif="day", notional=None,
                           asset_type=None, client_tag=None):
        body = {"symbol": symbol, "side": side, "type": "market",
                "time_in_force": tif}
        if notional is not None:
            body["notional"] = round(float(notional), 2)
        else:
            body["qty"] = float(qty)
        return self.post_order(body, client_tag)

    def place_limit_order(self, symbol, qty, side, limit_price, tif="day",
                          asset_type=None, outside_rth=False, client_tag=None):
        body = {"symbol": symbol, "side": side, "type": "limit",
                "qty": float(qty), "limit_price": round(float(limit_price), 4),
                "time_in_force": tif}
        return self.post_order(body, client_tag)

    def place_stop_limit_order(self, symbol, qty, side, stop_price, limit_price,
                               tif="day", asset_type=None, outside_rth=False,
                               client_tag=None):
        body = {"symbol": symbol, "side": side, "type": "stop_limit",
                "qty": float(qty), "stop_price": round(float(stop_price), 4),
                "limit_price": round(float(limit_price), 4), "time_in_force": tif}
        return self.post_order(body, client_tag)

    def place_stop_order(self, symbol, qty, side, stop_price, tif="day",
                         asset_type=None, client_tag=None):
        body = {"symbol": symbol, "side": side, "type": "stop",
                "qty": float(qty), "stop_price": round(float(stop_price), 4),
                "time_in_force": tif}
        return self.post_order(body, client_tag)

    def place_bracket_order(self, *args, **kwargs):
        raise NotImplementedError(
            "MYSE has no native bracket order — place entry + stop + take-profit "
            "as separate orders.")

    def modify_order(self, order_id, stop_price=None, limit_price=None,
                     qty=None, symbol=None):
        """Modify in place (PATCH — order id preserved). symbol is accepted for
        API parity but ignored."""
        body = {}
        if qty is not None:
            body["qty"] = float(qty)
        if limit_price is not None:
            body["limit_price"] = round(float(limit_price), 4)
        if stop_price is not None:
            body["stop_price"] = round(float(stop_price), 4)
        if not body:
            return self.get_order(order_id)
        return normalize_order(
            self.request("PATCH", f"/orders/{order_id}", json=body))

    # ── order queries ────────────────────────────────────────────────

    def get_order(self, order_id):
        return normalize_order(self.request("GET", f"/orders/{order_id}"))

    def get_orders(self, status=None, after=None, until=None, limit=None):
        params = {}
        if status is not None:
            params["status"] = status
        rows = self.request("GET", "/orders", params=params) or []
        if after is not None:
            after_str = after if isinstance(after, str) else after.isoformat()
            rows = [r for r in rows if str(r.get("created_at", "")) >= after_str]
        if until is not None:
            until_str = until if isinstance(until, str) else until.isoformat()
            rows = [r for r in rows if str(r.get("created_at", "")) <= until_str]
        if limit is not None:
            rows = rows[:int(limit)]
        return [normalize_order(o) for o in rows]

    def cancel_order(self, order_id, timeout=8, poll_interval=0.5):
        try:
            self.request("DELETE", f"/orders/{order_id}")
        except LookupError:
            return {"id": str(order_id), "status": "canceled"}
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
        """Cancel every open order (MYSE has no bulk endpoint — cancel each)."""
        rows = self.request("GET", "/orders", params={"status": "open"}) or []
        n = 0
        for o in rows:
            oid = o.get("id")
            if not oid:
                continue
            try:
                self.request("DELETE", f"/orders/{oid}")
                n += 1
            except Exception:
                pass
        return {"status": "all_cancelled", "cancelled": n}

    def get_open_orders_for_symbol(self, symbol):
        rows = self.request("GET", "/orders", params={"status": "open"}) or []
        return [normalize_order(o) for o in rows
                if str(o.get("symbol", "")).upper() == symbol.upper()]

    def wait_for_fill(self, order_id, timeout=300, poll_interval=2):
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            order = self.get_order(order_id)
            status = order.get("status", "").lower()
            if status == "filled":
                return order
            if status in ("canceled", "cancelled", "expired", "rejected"):
                return None
            _time.sleep(poll_interval)
        return None

    def get_fill_activities(self, after=None):
        """Per-fill records from /v1/account/activities (FILL only)."""
        params = {}
        if after is None:
            after_dt = datetime.now(timezone.utc) - timedelta(days=30)
            params["after"] = after_dt.strftime("%Y-%m-%dT00:00:00+00:00")
        elif isinstance(after, str):
            params["after"] = (f"{after}T00:00:00+00:00"
                               if len(after) == 10 else after)
        else:
            params["after"] = after.isoformat()

        rows = self.request("GET", "/account/activities", params=params) or []
        out = []
        for a in rows:
            if str(a.get("activity_type", "")).upper() != "FILL":
                continue
            out.append({
                "id": str(a.get("id", "")),
                "symbol": str(a.get("symbol", "")),
                "side": str(a.get("side", "")),
                "qty": str(a.get("qty", "")),
                "price": str(a.get("price", "")),
                "transaction_time": str(a.get("ts", "")),
                "order_id": str(a.get("order_id", "")),
                "type": "FILL",
            })
        return out

    # ── options: not supported (clear error, not AttributeError) ──────

    def get_option_chain(self, symbol, expiry_range_days=60):
        raise NotImplementedError("MYSE backend does not support option chains")

    def get_option_greeks(self, symbol, expiry, strike, right):
        raise NotImplementedError("MYSE backend does not support option greeks")

    # ── assets / market data ─────────────────────────────────────────

    def get_tradeable_assets(self, asset_type=AssetType.STOCK):
        if asset_type != AssetType.STOCK:
            raise ValueError(f"MYSE only supports stocks (got {asset_type})")
        rows = self.request("GET", "/assets",
                            params={"asset_class": "stock"}) or []
        return [normalize_asset(a) for a in rows if a.get("tradable")]

    def get_snapshot(self, symbol, asset_type=None):
        quote = self.request("GET", f"/quotes/{symbol}/latest")
        try:
            trade = self.request("GET", f"/trades/{symbol}/latest")
        except LookupError:
            trade = None
        try:
            day_bars = self.request("GET", f"/bars/{symbol}",
                                    params={"timeframe": "1Day", "limit": 2})
            bars = day_bars.get("bars", []) if day_bars else []
        except (LookupError, RuntimeError):
            bars = []

        result = {}
        if trade:
            result["latestTrade"] = {
                "p": float(trade.get("price", 0)),
                "s": float(trade.get("qty", 0)),
                "t": str(trade.get("ts", "")),
            }
        else:
            result["latestTrade"] = {
                "p": float(quote.get("last", 0)),
                "s": 0.0,
                "t": str(quote.get("ts", "")),
            }
        result["latestQuote"] = {
            "bp": float(quote.get("bid", 0)),
            "ap": float(quote.get("ask", 0)),
            "t": str(quote.get("ts", "")),
        }
        if bars:
            last = bars[-1]
            result["dailyBar"] = {
                "o": float(last["o"]), "h": float(last["h"]),
                "l": float(last["l"]), "c": float(last["c"]),
                "v": float(last["v"]), "t": str(last.get("ts", "")),
            }
        else:
            result["dailyBar"] = {}
        if len(bars) >= 2:
            prev = bars[-2]
            result["prevDailyBar"] = {
                "o": float(prev["o"]), "h": float(prev["h"]),
                "l": float(prev["l"]), "c": float(prev["c"]),
                "v": float(prev["v"]), "t": str(prev.get("ts", "")),
            }
        else:
            result["prevDailyBar"] = {}
        return result

    def get_snapshots(self, symbols, asset_type=None):
        # MYSE has no batch full-snapshot endpoint — fan out concurrently.
        if not symbols:
            return {}
        if self.async_executor is None:
            self.async_executor = ThreadPoolExecutor(
                max_workers=self.DEFAULT_ASYNC_WORKERS,
                thread_name_prefix="myse-async",
            )
        futures = {
            sym: self.async_executor.submit(self.get_snapshot, sym, asset_type)
            for sym in symbols
        }
        out = {}
        for sym, fut in futures.items():
            try:
                out[sym] = fut.result(timeout=self.timeout)
            except Exception:
                out[sym] = {}
        return out

    def get_bars(self, symbols, asset_type=None, timeframe="1Day",
                 start=None, limit=None, end=None):
        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            return {}

        params_base = {"timeframe": timeframe}
        if limit is not None:
            params_base["limit"] = int(limit)
        if start is not None:
            params_base["start"] = (start if isinstance(start, str)
                                    else start.isoformat())
        if end is not None:
            params_base["end"] = (end if isinstance(end, str)
                                  else end.isoformat())

        out = {}
        for sym in symbols:
            try:
                resp = self.request("GET", f"/bars/{sym}", params=params_base)
            except (LookupError, RuntimeError):
                out[sym] = []
                continue
            bars = resp.get("bars", []) if resp else []
            out[sym] = [normalize_bar(b) for b in bars]
        return out

    # ── calendar / session ───────────────────────────────────────────

    def get_clock(self):
        return self.request("GET", "/clock", auth=False)

    def get_market_session(self):
        """MYSE publishes session state at /v1/clock. 'regular' when is_open,
        else 'closed'. No extended-hours concept."""
        try:
            clock = self.get_clock()
            return "regular" if clock.get("is_open") else "closed"
        except Exception:
            return "closed"

    def get_available_types(self):
        return {"stock": self.get_market_session() == "regular"}

    def get_session_close(self, target_date):
        # MYSE trades 24/7 — no fixed close.
        return None
