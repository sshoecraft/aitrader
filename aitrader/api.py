"""aitrader API — FastAPI dashboard backend for trader-ui.

PURE INFRASTRUCTURE. It surfaces data the system already has (broker truth +
journal + settings) and performs mechanical control actions (close a position,
cancel an order, edit settings). It makes NO trading decisions and encodes no
strategy — same hard boundary as the MCP servers.

It owns its OWN broker connection (client_id 80, small pools) so it works
alongside the autonomous agent (which uses client_id 40-67) on the one paper
gateway. A human action here (e.g. a manual sell) is just broker truth the agent
will reconcile next cycle — no coordination needed.

Matches the contract ui/src/api.ts expects (the UI reaches the API on api_port,
default 2499). Endpoints aitrader has no concept of (strategies, analyze) return
safe empties so the UI doesn't crash; those tabs are inert. `/review` is NOT inert:
it assembles the agent's own recorded rationale (position-of-record + the symbol's
journal entries) — a pure read of what the agent wrote, no reviewer cognition.

Run: aitrader-api  (host/port from settings.toml: api_host, api_port=2499)
"""

__version__ = "0.6.1"

import glob
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

import tomllib
import tomli_w
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

import aitrader
from aitrader import journal_db
from aitrader.asset_types import classify_symbol, normalize_crypto_symbol
from aitrader.config import settings, DEFAULTS
from aitrader.timeutil import utcnow, utcnow_iso, to_et, UTC, parse_iso, et_display

app = FastAPI(title="aitrader API", version=__version__)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_broker = None
_journal = None

# Short cache for /status (the dashboard polls it every few seconds; each call is
# 4 broker requests). Caching the snapshot keeps the broker-call rate low and
# avoids IBKR Error 322 (too many account-summary subscriptions).
STATUS_TTL = 3.0
_status_cache = {"ts": 0.0, "data": None}
_status_lock = threading.Lock()

# A security's industry classification is static reference data, so it's cached
# for the process lifetime — keyed by symbol → {"sector":.., "industry":..}.
# Definitive answers (including "no classification") are cached; transient broker
# failures are not, so they retry on the next status fetch.
_classification_cache = {}

# The benchmark series (VTI by default) for the dashboard's relative-performance
# overlay comes from a BROKER-INDEPENDENT source, NOT the node's broker feed.
# Reasons: (1) a benchmark is one shared reference — two nodes must never disagree
# on the same VTI; sourcing it per-broker made atrader (Alpaca tape, incl.
# pre/post) and itrader (IBKR RTH feed) rebase to different bars and report
# different VTI%. (2) An IBKR-only node has no Alpaca feed at all. Yahoo's keyless
# v8 chart endpoint gives the same series everywhere. Cached per (symbol, period)
# so the polling dashboard doesn't hammer Yahoo; only successful fetches are cached
# (an empty/failed pull retries next poll).
BENCHMARK_TTL = 60.0
_benchmark_cache = {}
_benchmark_lock = threading.Lock()

# UI chart period -> Yahoo (range, interval). Keyed on the PERIOD, not the bar
# timeframe, so 1W vs 2W (both hourly) and 1M..1Y (all daily) get the right span.
YAHOO_RANGE_INTERVAL = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "60m"),
    "2W": ("1mo", "60m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
}


def fetch_benchmark_bars(symbol, period):
    """Broker-independent benchmark bars from Yahoo's keyless v8 chart endpoint,
    RTH-only, normalized to the same {t,o,h,l,c,v} shape /bars returns (t = epoch
    seconds). Cached per (symbol, period) for BENCHMARK_TTL; failures return []
    (uncached) so the overlay degrades to no line rather than erroring."""
    sym = (symbol or "VTI").upper()
    rng, interval = YAHOO_RANGE_INTERVAL.get(period, ("1d", "5m"))
    key = (sym, period)
    now = time.time()
    with _benchmark_lock:
        hit = _benchmark_cache.get(key)
        if hit and (now - hit["ts"]) < BENCHMARK_TTL:
            return hit["bars"]
    bars = []
    try:
        import requests
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            params={"range": rng, "interval": interval, "includePrePost": "false"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        r.raise_for_status()
        result = (r.json().get("chart", {}).get("result") or [None])[0]
        if result:
            ts = result.get("timestamp") or []
            q = (result.get("indicators", {}).get("quote") or [{}])[0]
            opens, highs = q.get("open") or [], q.get("high") or []
            lows, closes, vols = q.get("low") or [], q.get("close") or [], q.get("volume") or []
            for i, t in enumerate(ts):
                c = closes[i] if i < len(closes) else None
                if c is None:
                    continue  # Yahoo pads non-trading slots with nulls — skip them
                bars.append({
                    # ISO-8601 UTC string (NOT bare epoch) so it's a drop-in for the
                    # broker /bars `t` format the UI's dayKey()/lastSessionBars() parse
                    # by leading YYYY-MM-DD. A bare epoch made dayKey fall through, so
                    # the off-hours "Mode B" session grouping kept only 1 bar and the
                    # VTI line vanished off-hours. See ccmemory benchmark-broker-independent-yahoo.
                    "t": datetime.fromtimestamp(int(t), tz=UTC).isoformat(),
                    "o": opens[i] if i < len(opens) and opens[i] is not None else c,
                    "h": highs[i] if i < len(highs) and highs[i] is not None else c,
                    "l": lows[i] if i < len(lows) and lows[i] is not None else c,
                    "c": c,
                    "v": vols[i] if i < len(vols) and vols[i] is not None else 0,
                })
    except Exception:
        bars = []
    if bars:
        with _benchmark_lock:
            _benchmark_cache[key] = {"ts": now, "bars": bars}
    return bars


def build_data_broker():
    """Build + connect the optional market-DATA broker (settings.data_broker), or
    None if unset. Mirrors mcp/broker_server.build_data_broker so the dashboard
    shows the SAME prices the agent sees (e.g. Alpaca's tape covers pre/after
    hours where IBKR's paper feed is empty). Inlined rather than imported to keep
    the API process free of the MCP server module + FastMCP import."""
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


def broker():
    """Lazy execution broker per settings.broker ∈ {ibkr, alpaca, myse}, wrapped
    in a BrokerRouter when settings.data_broker is set (so dashboard prices use
    the same data feed the agent sees). The API owns its OWN connection: IBKR on
    client_id 80 with small pools (low-traffic dashboard); alpaca/myse just
    connect. Paper-only fuse per backend. A data-broker failure degrades to the
    execution broker for data — it never takes the dashboard down."""
    global _broker
    if _broker is None:
        from aitrader.brokers.router import BrokerRouter

        name = settings().broker or "ibkr"
        if name == "ibkr":
            from aitrader.brokers.ibkr import IBKRBroker
            execution = IBKRBroker(client_id=80, allow_live=settings().allow_live,
                                   pool_sizes={"orders": 1, "status": 1, "data": 1})
        elif name == "alpaca":
            from aitrader.brokers.alpaca import AlpacaBroker
            from aitrader.credentials import load_alpaca_credentials
            api_key, secret_key = load_alpaca_credentials()
            execution = AlpacaBroker(api_key, secret_key,
                                     paper=not settings().allow_live,
                                     data_feed=settings().alpaca_data_feed)
        elif name == "myse":
            from aitrader.brokers.myse import MYSEBroker
            from aitrader.credentials import load_myse_credentials
            creds = load_myse_credentials()
            execution = MYSEBroker(host=creds["host"], api_key=creds["api_key"])
        else:
            raise ValueError(f"Unknown broker: {name!r} (expected ibkr|alpaca|myse)")
        execution.connect()

        data = None
        try:
            data = build_data_broker()
        except Exception as exc:
            import sys
            print(f"WARNING: data_broker unavailable, using execution broker for "
                  f"data: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

        _broker = BrokerRouter(execution, data=data,
                               data_broker_types=settings().data_broker_types)
    return _broker


def journal():
    # check_same_thread=False: FastAPI serves sync endpoints across a threadpool,
    # so this one connection is read from multiple worker threads. The API only
    # reads the journal, so cross-thread reads are safe.
    global _journal
    if _journal is None:
        _journal = journal_db.get_db(check_same_thread=False)
    return _journal


# ── shape helpers (match trader-ui parsers) ───────────────────────────────

def map_position(p):
    """Broker position dict → the Position shape the UI expects. Defaults for
    fields filled later by mechanical enrichment against broker truth:
    stop/limit/to_stp/to_lim (protective orders), sector/industry (classification),
    heat (risk-at-stop). `trail` has no broker source here → stays null."""
    qty = float(p.get("qty") or p.get("position") or 0)
    avg = float(p.get("avg_entry_price") or p.get("avg_price") or p.get("average_cost") or 0)
    cur = float(p.get("current_price") or p.get("market_price") or 0)
    mv = float(p.get("market_value") or 0)
    upl = float(p.get("unrealized_pl") or p.get("unrealized_pnl") or p.get("unrealizedPNL") or 0)
    cost = float(p.get("cost_basis") or (avg * qty)) or 0
    return {
        "symbol": p.get("symbol", ""),
        "qty": qty, "avg_entry_price": avg, "current_price": cur,
        "market_value": mv, "unrealized_pl": upl,
        "unrealized_plpc": (upl / cost) if cost else 0,
        "side": p.get("side") or ("long" if qty >= 0 else "short"),
        "cost_basis": cost,
        "asset_class": p.get("asset_class") or p.get("asset_type") or "",
        # no risk engine here:
        "stop": 0, "has_broker_stop": False, "trail": None, "limit_price": 0,
        "has_broker_limit": False, "heat": 0, "to_stp": 0, "to_lim": 0,
        "sector": None, "industry": None,
    }


def map_order(o):
    return {
        "id": str(o.get("id") or o.get("order_id") or ""),
        "symbol": o.get("symbol", ""),
        "side": o.get("side", ""),
        "type": o.get("type") or o.get("order_type", ""),
        "qty": float(o.get("qty") or o.get("quantity") or 0),
        "stop_price": float(o.get("stop_price") or 0),
        "limit_price": float(o.get("limit_price") or 0),
        "status": o.get("status", ""),
        "order_ref": o.get("order_ref", ""),
    }


OPEN_ORDER_STATUSES = {
    "new", "accepted", "held", "pending_new", "pending_cancel", "pendingcancel",
    "submitted", "presubmitted", "pendingsubmit", "partially_filled",
}


def enrich_positions_with_protective_orders(positions, orders):
    """Standalone stop/limit orders aren't bracket-attached, so they don't render
    in the per-position Stop/Limit columns. Link each OPEN protective order to its
    position (same symbol, OPPOSITE side — a long is protected by a sell stop) and
    fill the position's stop/limit fields. Pure mechanical matching against broker
    truth — also confirms a stop is actually live (no match → stays '--')."""
    opens = [o for o in orders if str(o.get("status", "")).lower() in OPEN_ORDER_STATUSES]
    for p in positions:
        sym = str(p.get("symbol", "")).replace("/", "").upper()
        is_long = float(p.get("qty") or 0) >= 0
        protective_side = "sell" if is_long else "buy"
        cur = float(p.get("current_price") or 0)
        for o in opens:
            if str(o.get("symbol", "")).replace("/", "").upper() != sym:
                continue
            if str(o.get("side", "")).lower() != protective_side:
                continue
            otype = str(o.get("type", "")).lower()
            sp = float(o.get("stop_price") or 0)
            lp = float(o.get("limit_price") or 0)
            if "stop" in otype and sp > 0:
                p["stop"] = sp
                p["has_broker_stop"] = True
                if cur > 0:
                    # Progress toward the stop, NOT remaining distance: 100% = price
                    # is AT the stop, >100% = price has crossed PAST it (breached).
                    # Signed by side (stop/cur for a long, cur/stop for a short) so a
                    # breached stop reads as >1 instead of looking like cushion left —
                    # the old abs(cur-sp)/cur hid the sign (a stop 1% above a long's
                    # price was indistinguishable from 1% of room below it).
                    p["to_stp"] = (sp / cur) if is_long else (cur / sp)
            elif otype == "limit" and lp > 0:
                p["limit_price"] = lp
                p["has_broker_limit"] = True
                if cur > 0:
                    p["to_lim"] = abs(lp - cur) / cur


def enrich_positions_with_sector(b, positions):
    """Fill each equity position's sector/industry from the broker's factual
    IBKR industry classification. Cached process-wide (it's static reference
    data); forex/crypto/futures carry no classification and stay null. Pure
    lookup against broker truth — no screen, score, or opinion."""
    for p in positions:
        if p.get("asset_class") != "us_equity":
            continue
        sym = p.get("symbol")
        if not sym:
            continue
        if sym not in _classification_cache:
            try:
                # Cache the definitive answer (including "no classification");
                # leave transient failures uncached so they retry next fetch.
                _classification_cache[sym] = b.get_classification(sym) or {}
            except Exception:
                continue
        cls = _classification_cache.get(sym) or {}
        if cls.get("sector"):
            p["sector"] = cls["sector"]
        if cls.get("industry"):
            p["industry"] = cls["industry"]


def enrich_positions_with_heat(positions, equity):
    """Risk-at-stop as a fraction of account equity — DISPLAY-ONLY observability
    for the dashboard, derived purely from broker truth. This is NOT a risk
    budget, cap, or gate: nothing here constrains a decision, and the agent never
    reads this API (it acts through MCP tools). It's a mechanical derivation in
    the same class as the existing `to_stp`/sector enrichment, so it stays on the
    infra side of the hard boundary (CLAUDE.md §2). See memory `heat-observability`.

    Dollars at risk per position:
      • no live protective stop → |market_value| (the whole position is exposed —
        market_value already embeds the futures multiplier, so this is true
        notional for every asset class; no stop = max heat).
      • a live protective stop on the CORRECT side → the loss if stopped out:
            |market_value| × distance_to_stop / current
      • a stop that has CROSSED to the wrong side (price already past it — e.g. a
        pre-market gap below a long's stop that can't trigger until the regular
        open) → |market_value|, same as unprotected. Such a stop caps nothing at a
        known level: it becomes a market order at the next open and fills wherever
        price is. Reporting 0 risk there (the old max(0, …) floor did) is backwards.
    heat = at_risk / equity. Returns the per-class + total aggregate for the
    top-level `heat` object; also writes each position's own `heat`."""
    buckets = {"stock": 0.0, "crypto": 0.0, "forex": 0.0, "futures": 0.0}
    total = 0.0
    for p in positions:
        mv = abs(float(p.get("market_value") or 0))
        cur = float(p.get("current_price") or 0)
        at_risk = mv
        if p.get("has_broker_stop") and cur > 0:
            stop = float(p.get("stop") or 0)
            is_long = str(p.get("side")) == "long" or float(p.get("qty") or 0) >= 0
            dist = (cur - stop) if is_long else (stop - cur)
            # dist > 0 → stop is on the protective side; risk is the fall to it.
            # dist <= 0 → stop has crossed to the wrong side (breached); it protects
            # at no known level, so treat as unprotected (full notional at risk)
            # rather than flooring to 0 and calling a breached position "no risk".
            at_risk = mv * (dist / cur) if dist > 0 else mv
        p["heat"] = (at_risk / equity) if equity > 0 else 0.0
        total += at_risk
        bucket = classify_symbol(str(p.get("symbol", "")), p.get("asset_class")).value
        if bucket in buckets:
            buckets[bucket] += at_risk

    def frac(x):
        return (x / equity) if equity > 0 else 0.0

    return {
        "total_heat": frac(total),
        "stock_heat": frac(buckets["stock"]),
        "crypto_heat": frac(buckets["crypto"]),
        "forex_heat": frac(buckets["forex"]),
        "futures_heat": frac(buckets["futures"]),
        "position_count": len(positions),
    }


def broker_or_error():
    """Return (broker, None) or (None, error_dict) if the gateway is unreachable."""
    try:
        return broker(), None
    except Exception as exc:
        return None, {"connected": False, "error": f"{type(exc).__name__}: {exc}"}


# ── status / account ──────────────────────────────────────────────────────

@app.get("/health")
def health():
    b, err = broker_or_error()
    return {"status": "ok" if b else "disconnected", "connected": bool(b),
            "version": aitrader.__version__}


@app.get("/status")
def status():
    # Serve the cached snapshot if it's fresh; otherwise fetch once (under a lock
    # so concurrent pollers don't all hit the broker). TTL ~3s.
    now = time.monotonic()
    if _status_cache["data"] is not None and now - _status_cache["ts"] < STATUS_TTL:
        return _status_cache["data"]
    with _status_lock:
        now = time.monotonic()
        if _status_cache["data"] is not None and now - _status_cache["ts"] < STATUS_TTL:
            return _status_cache["data"]
        data = compute_status()
        _status_cache["data"] = data
        _status_cache["ts"] = time.monotonic()
        return data


def compute_status():
    b, err = broker_or_error()
    if err:
        return {"connected": False, "error": err["error"], "positions": [],
                "orders": [], "account": {}, "available_types": {},
                "heat": {"total_heat": 0, "stock_heat": 0, "crypto_heat": 0,
                         "forex_heat": 0, "futures_heat": 0, "position_count": 0},
                "version": aitrader.__version__, "last_sync": utcnow_iso(), "day_pl": 0}
    acct = b.get_account()
    positions = [map_position(p) for p in (b.get_positions() or [])]
    # list_all_open_orders (reqAllOpenOrders) so the dashboard sees the agent's
    # orders too — the API is a different IBKR client than the agent. NON-FATAL:
    # if the broker's orders endpoint is slow/degraded (e.g. Alpaca's /v2/orders
    # hanging), serve account+positions+equity anyway rather than hanging the whole
    # dashboard — positions just miss protective-order enrichment this cycle.
    try:
        orders = [map_order(o) for o in (b.list_all_open_orders() or [])]
    except Exception as exc:
        import sys
        print(f"WARNING: open-orders fetch failed; serving status without orders: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        orders = []
    enrich_positions_with_protective_orders(positions, orders)
    enrich_positions_with_sector(b, positions)
    try:
        available = b.get_available_types()
    except Exception:
        available = {}
    equity = float(acct.get("equity") or 0)
    cash = float(acct.get("cash") or 0)
    # Settled cash is what's actually deployable today; unsettled is proceeds still
    # in T+1/T+2 settlement (the binding constraint on a CASH account). IBKR returns
    # SettledCash; brokers that don't expose it default to "all settled" (unsettled 0).
    settled_cash = float(acct.get("settled_cash") or cash)
    unsettled_cash = round(cash - settled_cash, 2)
    heat = enrich_positions_with_heat(positions, equity)
    return {
        "connected": True,
        "account": {
            "account": acct.get("account", ""),
            "equity": equity, "cash": cash,
            "buying_power": float(acct.get("buying_power") or 0),
            "settled_cash": settled_cash,
            "unsettled_cash": unsettled_cash,
            "portfolio_value": float(acct.get("portfolio_value") or equity),
        },
        "positions": positions,
        "orders": orders,
        "heat": heat,
        "available_types": available,
        "version": aitrader.__version__,
        "last_sync": utcnow_iso(),
        "day_pl": day_pl(equity),
    }


def day_pl(current_equity):
    """current equity minus the first equity snapshot of the current *trading
    day*, where "day" is the ET calendar day — NOT the UTC day.

    Snapshots are stored as UTC ISO strings, but the dashboard displays in ET
    (CLAUDE.md §6: all times UTC internally, display ET) and the market day is
    an ET day. A UTC-midnight boundary disagrees with the displayed day at the
    edges: a snapshot written late ET evening (already past UTC midnight) would
    be counted as the *next* day's baseline, mis-anchoring day P&L. So we take
    ET midnight of the current ET day and convert it back to a UTC instant for
    the `since` filter — the filter calendar then matches the display calendar.
    """
    et_day_start = to_et(utcnow()).replace(hour=0, minute=0, second=0, microsecond=0)
    since = et_day_start.astimezone(UTC).isoformat()
    rows = journal_db.equity_read(journal(), limit=500, since=since)
    if not rows:
        return 0
    first = rows[-1].get("equity")  # equity_read is newest-first BY ts; last = earliest today
    return (current_equity - float(first)) if first else 0


# ── control: close / cancel ───────────────────────────────────────────────

@app.post("/sell")
def sell(symbol: str):
    b, err = broker_or_error()
    if err:
        return Response(err["error"], status_code=503)
    tag = f"ui-sell-{symbol}-{utcnow().date().isoformat()}"
    return b.close_position(symbol, client_tag=tag)


@app.post("/cancel/{order_id}")
def cancel(order_id: str):
    b, err = broker_or_error()
    if err:
        return Response(err["error"], status_code=503)
    return b.cancel_order(order_id)


# ── market data ───────────────────────────────────────────────────────────

# Rolling-window lengths (days) for portfolio_history periods that aren't a
# calendar boundary. 1A = "1 annum" — the name trader-ui's chart sends for 1Y.
PORTFOLIO_PERIOD_DAYS = {"1W": 7, "2W": 14, "1M": 30, "3M": 90, "6M": 180, "1Y": 365, "1A": 365}


def portfolio_since(period):
    """Lower-bound UTC-ISO timestamp for a portfolio_history period, or None for
    'ALL' (no bound). Ported from trader's resolve logic, ET-aware to match the
    display calendar: 1D = since ET midnight today (like day_pl, and like the UI's
    "1D = since local midnight" intent — NOT a broker 'last session'); YTD = since
    ET Jan 1; everything else is a rolling N-day window. Snapshots are stored as
    UTC ISO strings, so calendar boundaries are computed in ET then converted to a
    UTC instant for the `ts >= ?` filter."""
    p = (period or "").upper()
    if p == "ALL":
        return None
    if p == "1D":
        start = to_et(utcnow()).replace(hour=0, minute=0, second=0, microsecond=0)
    elif p == "YTD":
        start = to_et(utcnow()).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = utcnow() - timedelta(days=PORTFOLIO_PERIOD_DAYS.get(p, 30))
    return start.astimezone(UTC).isoformat()


@app.get("/portfolio_history")
def portfolio_history(period: str = "1M", timeframe: str = "1D"):
    """Equity curve from the journal's equity snapshots (IBKR has no native
    history; snapshots come from the agent + the cron recorder, see
    docs/snapshot-recorder.md). Honors `period` by filtering on a date window
    (NOT a fixed row cap) so every range — 1D/1W/1M/3M/1Y/YTD/ALL — returns its
    own window. `timeframe` is passed through (no server-side downsampling yet)."""
    since = portfolio_since(period)
    # since-filtered, then oldest-first. High limit is a safety backstop only —
    # the window is bounded by `since`, not by the count (ALL has no since, so the
    # limit does cap it; ample headroom at the recorder's ~96 snapshots/day).
    rows = list(reversed(journal_db.equity_read(journal(), limit=200000, since=since)))
    equity = [float(r.get("equity") or 0) for r in rows]
    ts = [r.get("ts") for r in rows]
    base = equity[0] if equity else 0
    pl = [e - base for e in equity]
    plpc = [(e - base) / base if base else 0 for e in equity]
    return {"equity": equity, "profit_loss": pl, "profit_loss_pct": plpc,
            "timestamp": ts, "base_value": base, "period": period,
            "timeframe": timeframe, "source": "equity_snapshots"}


@app.get("/bars")
def bars(symbols: str, timeframe: str = "1Day", start: str = None):
    b, err = broker_or_error()
    if err:
        return Response(err["error"], status_code=503)
    syms = [s for s in symbols.split(",") if s]
    raw = b.get_bars(syms, timeframe=timeframe, start=start) or {}
    out = {}
    for sym, blist in raw.items():
        out[sym] = [{"t": x.get("t") or x.get("ts"), "o": x.get("o") or x.get("open"),
                     "h": x.get("h") or x.get("high"), "l": x.get("l") or x.get("low"),
                     "c": x.get("c") or x.get("close"), "v": x.get("v") or x.get("volume")}
                    for x in (blist or [])]
    return out


@app.get("/benchmark")
def benchmark(symbol: str = "VTI", period: str = "1D"):
    """Broker-INDEPENDENT benchmark series for the dashboard's relative-performance
    overlay (the amber VTI line). Sourced from Yahoo, NOT the node's broker, so
    every node shows the SAME benchmark regardless of broker (an IBKR-only node has
    no Alpaca feed; two nodes must never disagree on the same VTI). Needs no broker
    connection — works even when the broker is down. Returns the same
    {symbol: [bars]} shape as /bars."""
    return {(symbol or "VTI").upper(): fetch_benchmark_bars(symbol, period)}


@app.get("/snapshot/{symbol}")
def snapshot(symbol: str):
    b, err = broker_or_error()
    if err:
        return Response(err["error"], status_code=503)
    return b.get_snapshot(symbol)


@app.get("/trades")
def trades(period: str = "all"):
    """Executions from the broker as 'transactions'. Round-trip P&L pairing is
    not reconstructed here (v1) — round_trips is empty."""
    b, err = broker_or_error()
    txs = []
    if b:
        try:
            fills = b.get_fill_activities() or []
        except Exception:
            fills = []
        for i, f in enumerate(fills):
            txs.append({
                "id": i, "symbol": f.get("symbol", ""), "side": f.get("side", ""),
                "quantity": float(f.get("qty") or f.get("quantity") or 0),
                "price": float(f.get("price") or f.get("fill_price") or 0),
                "total_value": float(f.get("value") or 0),
                "commission": float(f.get("commission") or 0),
                "strategy": None, "is_day_trade": False,
                "executed_at": f.get("time") or f.get("executed_at") or "",
                "asset_type": f.get("asset_type"),
            })
    return {"period": period, "start": None, "end": utcnow_iso(), "count": len(txs),
            "realized_pnl": 0, "transactions": txs, "round_trips": []}


# ── journal feed (the agent's notebook) ───────────────────────────────────

@app.get("/journal")
def journal_feed(limit: int = 100, kind: str = None, symbol: str = None, since: str = None):
    """The agent's notebook as a normalized feed. Emits the SHARED /journal
    contract (identical envelope + field names on the trader API) so trader-ui
    renders both backends with one component. Read-only projection of the
    journal table — no logic, no cognition.

    entry = {id, time (ISO-8601 UTC), kind, symbol|null, text, tags|null, meta}.
    aitrader's journal rows map: ts→time, kind→kind, body→text, tags→tags; there
    is no per-entry structured meta here (trader fills it from its risk check),
    so meta is an empty object. Newest-first, capped at `limit`; `since` (ISO or
    YYYY-MM-DD) and `kind`/`symbol` filter. The UI displays `time` in ET."""
    rows = journal_db.journal_read(journal(), limit=limit, kind=kind, symbol=symbol, since=since)
    entries = []
    for r in rows:
        ts = r.get("ts")
        entries.append({
            "id": r.get("id"),
            # ts is already stored UTC ISO; re-emit via parse_iso so a naive
            # string (if any writer ever wrote one) still carries the +00:00.
            "time": parse_iso(ts).isoformat() if ts else None,
            "kind": r.get("kind"),
            "symbol": r.get("symbol"),
            "text": r.get("body"),
            "tags": r.get("tags"),
            "meta": {},
        })
    return {"entries": entries}


# ── settings (settings.toml ↔ UI {default,current}) ───────────────────────

def read_settings_file():
    path = settings().path
    if os.path.exists(path):
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def write_settings_file(data):
    path = settings().path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)
    settings.cache_clear()  # force reload on next settings()


@app.get("/settings")
def get_settings():
    cur = read_settings_file()
    keys = set(DEFAULTS) | set(cur)
    out = {}
    for k in sorted(keys):
        out[k] = {"default": DEFAULTS.get(k, ""), "current": cur.get(k, DEFAULTS.get(k, ""))}
    return out


@app.put("/settings")
async def put_settings(request: Request):
    changes = await request.json()
    data = read_settings_file()
    data.update(changes)
    write_settings_file(data)
    return {"settings": get_settings()}


@app.delete("/settings")
async def delete_settings(request: Request):
    body = await request.json()
    keys = body.get("keys", [])
    data = read_settings_file()
    for k in keys:
        data.pop(k, None)
    write_settings_file(data)
    return {"settings": get_settings()}


# ── log (tail the agent's latest ccloop session output) ───────────────────

def _find_latest_transcript(run_dir):
    """Newest Claude Code JSONL transcript for the agent's run dir = the LIVE
    session. Claude Code names its project dir after the cwd with '/' and '.'
    replaced by '-'. Fall back to a glob if the exact dir name isn't found."""
    base = os.path.expanduser("~/.claude/projects")
    exact = os.path.join(base, re.sub(r"[/.]", "-", run_dir))
    dirs = [exact] if os.path.isdir(exact) else glob.glob(os.path.join(base, "*aitrader*run*"))
    jsonls = []
    for d in dirs:
        try:
            jsonls += [e.path for e in os.scandir(d) if e.name.endswith(".jsonl")]
        except OSError:
            pass
    return max(jsonls, key=os.path.getmtime) if jsonls else None


def _clip(s, limit):
    s = "" if s is None else str(s)
    return s if len(s) <= limit else s[:limit] + " …"


def _tool_result_text(content, limit=800):
    if isinstance(content, list):
        parts = [(b.get("text") or b.get("content") or "") if isinstance(b, dict) else str(b)
                 for b in content]
        content = "\n".join(p for p in parts if p)
    return _clip(str(content).strip(), limit)


def _render_transcript(path):
    """Render a Claude Code JSONL transcript to a readable text stream — the
    agent's full output: thinking, assistant text, tool calls, tool results.
    (Injected system/user prompts are skipped as noise; tool RESULTS are kept.)"""
    blocks = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            ts = str(o.get("timestamp") or "")[11:19]
            tag = f"[{ts}] " if ts else ""
            msg = o.get("message") if isinstance(o.get("message"), dict) else {}
            content = msg.get("content")
            if o.get("type") == "assistant" and isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "thinking" and (b.get("thinking") or "").strip():
                        blocks.append(f"{tag}💭 {b['thinking'].strip()}")
                    elif bt == "text" and (b.get("text") or "").strip():
                        blocks.append(f"{tag}{b['text'].strip()}")
                    elif bt == "tool_use":
                        blocks.append(f"{tag}→ {b.get('name', '?')}  {_clip(json.dumps(b.get('input'), default=str), 400)}")
            elif o.get("type") == "user" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        blocks.append(f"{tag}← {_tool_result_text(b.get('content'))}")
    return "\n\n".join(blocks)


@app.get("/log")
def log(bytes: int = 100000):
    """Engine Log = the agent's live Claude Code transcript rendered to text
    (thinking + tool calls + results). Tails the last `bytes` of the rendering.
    Same shape the LogViewer/LogPeek panels already consume."""
    path = _find_latest_transcript(settings().run_dir)
    if not path or not os.path.exists(path):
        return {"path": "", "size": 0, "mtime": 0, "returned_bytes": 0,
                "truncated": False, "content": "(no agent session output yet)"}
    sid = os.path.basename(path).split(".")[0][:8]
    rendered = f"── live session {sid} ──\n\n" + _render_transcript(path)
    full = rendered.encode("utf-8")
    truncated = len(full) > bytes
    content = full[-bytes:].decode("utf-8", errors="replace") if truncated else rendered
    return {"path": path, "size": len(full), "mtime": int(os.path.getmtime(path)),
            "returned_bytes": len(content.encode()), "truncated": truncated,
            "content": content}


# ── inert stubs for old-system concepts aitrader has no equivalent of ─────

@app.get("/strategies")
def strategies():
    return {"active": None, "strategies": []}


@app.get("/methods")
def methods():
    return {"methods": []}


@app.get("/reviews")
def reviews():
    return {"reviews": []}


def fmt_et(ts):
    """ISO-8601 UTC string → human ET display, or the raw value if unparseable."""
    if not ts:
        return ""
    try:
        return et_display(parse_iso(ts))
    except Exception:
        return str(ts)


@app.get("/review")
def review(symbol: str = ""):
    """The agent's recorded rationale for a symbol, assembled from the journal's
    durable stores: the position-of-record (why entered, current thesis, planned
    exit) plus that symbol's notebook entries (the chronological log). This is a
    pure read of what the agent itself wrote — no cognition, no scoring. Returns
    404 when the agent recorded nothing for the symbol (UI shows 'no review')."""
    sym = (symbol or "").strip()
    if not sym:
        return Response(status_code=404)
    j = journal()
    # The agent may key crypto either slash or no-slash; match the variants.
    candidates = []
    for s in (sym, normalize_crypto_symbol(sym), sym.replace("/", "")):
        if s and s not in candidates:
            candidates.append(s)

    por = None
    for s in candidates:
        por = journal_db.por_get(j, s)
        if por:
            break

    entries, seen = [], set()
    for s in candidates:
        for e in journal_db.journal_read(j, limit=200, symbol=s):
            if e.get("id") not in seen:
                seen.add(e.get("id"))
                entries.append(e)
    entries.sort(key=lambda e: e.get("ts") or "", reverse=True)

    if not por and not entries:
        return Response(status_code=404)

    lines = []
    if por:
        lines.append("=== POSITION OF RECORD ===")
        if por.get("status"):
            lines.append(f"Status:  {por['status']}")
        if por.get("opened_at"):
            lines.append(f"Opened:  {fmt_et(por['opened_at'])}")
        if por.get("entry_rationale"):
            lines.append(f"\nWhy entered:\n{por['entry_rationale']}")
        if por.get("thesis"):
            lines.append(f"\nThesis (why held):\n{por['thesis']}")
        if por.get("planned_exit"):
            lines.append(f"\nPlanned exit:\n{por['planned_exit']}")
    if entries:
        if lines:
            lines.append("")
        lines.append("=== JOURNAL (newest first) ===")
        for e in entries:
            lines.append(f"\n[{fmt_et(e.get('ts'))}] {e.get('kind') or 'note'}")
            if e.get("body"):
                lines.append(e["body"])

    reviewed = (por or {}).get("last_reviewed_at") or (por or {}).get("updated_at")
    if not reviewed and entries:
        reviewed = entries[0].get("ts")
    asset_type = (por or {}).get("asset_type") or classify_symbol(sym).value
    return {
        "symbol": (por or {}).get("symbol") or sym,
        "asset_type": asset_type or "",
        "reviewed_at": reviewed or "",
        "content": "\n".join(lines),
        "format": "text",
    }


@app.post("/actions/{action}")
def actions(action: str):
    # aitrader has no buyer/engine actions; the runtime is ccloop (systemctl).
    return {"status": "not_applicable", "action": action,
            "note": "aitrader has no engine actions; control the runtime via systemctl."}


def main():
    import uvicorn
    from aitrader import portd
    s = settings()
    # If portd is running, take the port it allocates us (reachable via Caddy at
    # /<portd_name>-api/); otherwise fall back to the configured api_port. The probe
    # is a hard ~1s and never hangs startup. Deregister on stop is wired in the
    # systemd unit (ExecStopPost), so it fires even on SIGKILL of this process.
    PORTD_NAME = f"{s.portd_name}-api"
    allocated = portd.allocate(PORTD_NAME)
    port = allocated or s.api_port
    if allocated:
        print(f"portd: allocated port {port} as '{PORTD_NAME}'", flush=True)
    else:
        print(f"portd: not in use — binding configured api_port {port}", flush=True)
    # Publish the actually-bound port so out-of-process readers (the snapshot
    # recorder timer) reach us regardless of portd dynamic allocation. Rewritten
    # every start, so a portd reallocation on restart self-heals. Best-effort.
    try:
        os.makedirs(s.state_dir, exist_ok=True)
        with open(s.api_port_file, "w") as f:
            f.write(str(port))
    except OSError as exc:
        print(f"warning: could not write {s.api_port_file}: {exc}", flush=True)
    uvicorn.run(app, host=s.api_host, port=port)


if __name__ == "__main__":
    main()
