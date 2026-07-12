"""NYSE session-close resolver with multi-tier fallback.

Infrastructure only — a factual resolver, no decisions. Answers "when does the
US stock session close on date D?" so callers (the scheduler MCP's
wait_until_session_close, the harness) don't hammer the broker every tick.

Three-tier resolution, in order of preference:
    1. Broker calendar (IBKR liquidHours via broker.get_session_close).
       Authoritative; reflects what the broker actually thinks today.
    2. pandas_market_calendars NYSE schedule. Offline, rule-driven, knows all
       holidays and half-days. Cannot fail on transient outages. A
       library-confirmed non-trading day is a FINAL answer (None), not a
       failure — see NOT_TRADING_DAY.
    3. Hardcoded 16:00 ET (weekdays only). Last-resort guard if tiers 1 and 2
       are both UNAVAILABLE. WRONG on half-days AND weekday holidays —
       logged loudly.

Cache value carries its source so a degraded answer (library/fallback) is
upgraded to broker the next time the broker query succeeds. Self-healing.

All identifiers plain snake_case; all internal state UTC, display ET.

Clean-room provenance: ported from /src/trader/trader/market_calendar.py
(pure infra resolver, no cognition); the only change is the clock dependency
(`trader.clock` -> `aitrader.timeutil`).
"""

from __future__ import annotations

__version__ = "0.3.0"

import logging
from datetime import datetime, timezone, date, time as dtime
from typing import Optional

log = logging.getLogger("aitrader.market_calendar")

# Per-process cache. Key: calendar date (UTC). Value: (close, source) where
# close is a UTC datetime or None (= confirmed non-trading day) and
# source ∈ {"broker", "library", "fallback"}.
session_close_cache: dict[date, tuple[Optional[datetime], str]] = {}

# query_library sentinel: the library answered authoritatively "no session on
# this date" (weekend/holiday). Distinct from None, which means the library
# itself was unavailable — conflating the two made every weekday holiday fall
# through to the hardcoded-16:00 tier (0.1.0 bug: July 3 2026 got a close).
NOT_TRADING_DAY = object()


def today_utc() -> date:
    """The current UTC date — the cache key."""
    from aitrader.timeutil import utcnow
    return utcnow().astimezone(timezone.utc).date()


def session_close_today(broker=None) -> Optional[datetime]:
    """Return today's NYSE session close (UTC tz-aware datetime).

    None means weekend / holiday / all tiers failed — callers should treat
    None as "unknown" and refuse risky time-of-day actions. `broker` is
    consulted on cache-miss and on the upgrade path; omit for cache-only.
    """
    today = today_utc()
    cached = session_close_cache.get(today)
    if cached is not None:
        close_value, source = cached
        if source != "broker" and broker is not None:
            broker_close = query_broker(broker, today)
            if broker_close is not None:
                session_close_cache[today] = (broker_close, "broker")
                return broker_close
        return close_value
    return resolve_and_cache(today, broker)


def session_close_for(target_date: date, broker=None) -> Optional[datetime]:
    """Resolve the session close for an arbitrary date (not just today)."""
    cached = session_close_cache.get(target_date)
    if cached is not None and (cached[1] == "broker" or broker is None):
        return cached[0]
    return resolve_and_cache(target_date, broker)


def resolve_and_cache(target_date: date, broker) -> Optional[datetime]:
    """Tier 1 (broker) → Tier 2 (library) → Tier 3 (hardcoded). Cache first hit.

    Tier 3 fires only when tiers 1 and 2 are UNAVAILABLE. A library-confirmed
    holiday/weekend is cached as (None, "library") and returned as None — it
    must never fall through to the weekday-16:00 fabrication."""
    if broker is not None:
        close = query_broker(broker, target_date)
        if close is not None:
            session_close_cache[target_date] = (close, "broker")
            return close

    close = query_library(target_date)
    if close is NOT_TRADING_DAY:
        session_close_cache[target_date] = (None, "library")
        log.info("[market_calendar] library: %s is not a trading day "
                 "(holiday/weekend)", target_date)
        return None
    if close is not None:
        session_close_cache[target_date] = (close, "library")
        log.info("[market_calendar] library NYSE close for %s: %s (broker unavailable)",
                 target_date, format_close_for_log(close))
        return close

    if target_date.weekday() < 5:
        from zoneinfo import ZoneInfo
        close = datetime.combine(target_date, dtime(16, 0)).replace(
            tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        session_close_cache[target_date] = (close, "fallback")
        log.warning("[market_calendar] broker AND library failed for weekday %s — "
                    "hardcoded 16:00 ET. WRONG ON HALF-DAYS. Investigate.", target_date)
        return close

    return None


def query_broker(broker, target_date: date) -> Optional[datetime]:
    """Ask the broker for target_date's session close. None on any failure."""
    if broker is None or not hasattr(broker, "get_session_close"):
        return None
    try:
        result = broker.get_session_close(target_date)
    except Exception as exc:
        log.warning("[market_calendar] broker query failed: %s", exc)
        return None
    if result is None or not isinstance(result, datetime):
        return None
    return result


def query_library(target_date: date):
    """Ask pandas_market_calendars for target_date's NYSE close.

    Returns a UTC datetime on a trading day, NOT_TRADING_DAY when the library
    authoritatively says the date has no session (weekend/holiday), or None
    when the library is unavailable/failed. Callers MUST distinguish
    "no session" (final) from "no answer" (degrade to the next tier)."""
    try:
        import pandas_market_calendars as mcal
    except ImportError:
        return None
    try:
        nyse = mcal.get_calendar("NYSE")
        sched = nyse.schedule(start_date=target_date, end_date=target_date)
        if sched.empty:
            return NOT_TRADING_DAY
        ts = sched.iloc[0]["market_close"]
        py_dt = ts.to_pydatetime()
        py_dt = py_dt.replace(tzinfo=timezone.utc) if py_dt.tzinfo is None else py_dt.astimezone(timezone.utc)
        return py_dt
    except Exception as exc:
        log.warning("[market_calendar] library query failed: %s", exc)
        return None


def next_session_open(broker=None, start: Optional[datetime] = None) -> Optional[datetime]:
    """Return the next NYSE regular-session OPEN at/after `start` (UTC). Uses
    pandas_market_calendars; None if unavailable. Pure schedule fact."""
    try:
        import pandas_market_calendars as mcal
    except ImportError:
        return None
    from aitrader.timeutil import utcnow
    if start is None:
        start = utcnow()
    try:
        nyse = mcal.get_calendar("NYSE")
        start_d = start.astimezone(timezone.utc).date()
        sched = nyse.schedule(start_date=start_d, end_date=start_d.replace(year=start_d.year) if False else start_d)
        # Look ahead up to 10 calendar days to clear weekends/holidays.
        from datetime import timedelta
        sched = nyse.schedule(start_date=start_d, end_date=start_d + timedelta(days=10))
        for _, row in sched.iterrows():
            opn = row["market_open"].to_pydatetime()
            opn = opn.replace(tzinfo=timezone.utc) if opn.tzinfo is None else opn.astimezone(timezone.utc)
            if opn >= start:
                return opn
        return None
    except Exception as exc:
        log.warning("[market_calendar] next_session_open failed: %s", exc)
        return None


# ── per-class week-ahead schedule (1.43.0) ───────────────────────────────────
# Pure schedule FACTS for every asset class, so the agent can read "futures
# reopen Sunday 18:00 ET" / "Friday is a holiday" ONCE at session start instead
# of discovering each closure the moment it happens. Library tier
# (pandas_market_calendars: NYSE for stock/options, CME_Equity for futures —
# holiday- and half-day-aware) with rule-based weekday-window fallbacks
# (holiday-BLIND; every class carries its `source` so degraded answers are
# visible). These are MARKET hours — what is tradeable this minute on THIS
# broker stays the broker MCP's get_available_types (e.g. IBKR paper has no
# crypto at all).

ET_ZONE = "America/New_York"


def format_span_et(open_utc: datetime, close_utc: datetime) -> str:
    """Render a session span compactly in ET: 'Mon 07/13 09:30–16:00 ET'."""
    from zoneinfo import ZoneInfo
    o = open_utc.astimezone(ZoneInfo(ET_ZONE))
    c = close_utc.astimezone(ZoneInfo(ET_ZONE))
    if o.date() == c.date():
        return f"{o.strftime('%a %m/%d %H:%M')}–{c.strftime('%H:%M')} ET"
    return f"{o.strftime('%a %m/%d %H:%M')} → {c.strftime('%a %m/%d %H:%M')} ET"


def library_sessions(calendar_name: str, start_d: date, end_d: date):
    """Sessions for [start_d, end_d] from pandas_market_calendars, as a list of
    (open_utc, close_utc). None when the library or calendar is unavailable —
    callers degrade to a rule tier."""
    try:
        import pandas_market_calendars as mcal
    except ImportError:
        return None
    try:
        cal = mcal.get_calendar(calendar_name)
        sched = cal.schedule(start_date=start_d, end_date=end_d)
        rows = []
        for _, row in sched.iterrows():
            o = row["market_open"].to_pydatetime()
            c = row["market_close"].to_pydatetime()
            o = o.replace(tzinfo=timezone.utc) if o.tzinfo is None else o.astimezone(timezone.utc)
            c = c.replace(tzinfo=timezone.utc) if c.tzinfo is None else c.astimezone(timezone.utc)
            rows.append((o, c))
        return rows
    except Exception as exc:
        log.warning("[market_calendar] library sessions for %s failed: %s",
                    calendar_name, exc)
        return None


def rule_sessions_stock(start_d: date, end_d: date):
    """Weekday 09:30–16:00 ET. Holiday-blind — fallback only."""
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    et = ZoneInfo(ET_ZONE)
    rows, d = [], start_d
    while d <= end_d:
        if d.weekday() < 5:
            rows.append((
                datetime.combine(d, dtime(9, 30), tzinfo=et).astimezone(timezone.utc),
                datetime.combine(d, dtime(16, 0), tzinfo=et).astimezone(timezone.utc),
            ))
        d += timedelta(days=1)
    return rows


def rule_sessions_futures(start_d: date, end_d: date):
    """CME Globex weekday windows: trade date D opens (D-1) 18:00 ET and closes
    D 17:00 ET; Monday's session opens Sunday 18:00 ET. Holiday-blind fallback."""
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    et = ZoneInfo(ET_ZONE)
    rows, d = [], start_d
    while d <= end_d:
        if d.weekday() < 5:
            rows.append((
                datetime.combine(d - timedelta(days=1), dtime(18, 0), tzinfo=et).astimezone(timezone.utc),
                datetime.combine(d, dtime(17, 0), tzinfo=et).astimezone(timezone.utc),
            ))
        d += timedelta(days=1)
    return rows


def rule_sessions_forex(start_d: date, end_d: date):
    """One continuous weekly window: Sunday 17:00 ET → Friday 17:00 ET (the
    IDEALPRO-style week; the daily 17:00 pause is below this resolution)."""
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    et = ZoneInfo(ET_ZONE)
    rows = []
    # Find the Sunday at/before start_d, then emit each week touching the window.
    sunday = start_d - timedelta(days=(start_d.weekday() + 1) % 7)
    while sunday <= end_d:
        rows.append((
            datetime.combine(sunday, dtime(17, 0), tzinfo=et).astimezone(timezone.utc),
            datetime.combine(sunday + timedelta(days=5), dtime(17, 0), tzinfo=et).astimezone(timezone.utc),
        ))
        sunday += timedelta(days=7)
    return rows


def class_sessions(asset_type: str, start_d: date, end_d: date):
    """(rows, source) for one asset class over [start_d, end_d]."""
    if asset_type in ("stock", "options"):
        rows = library_sessions("NYSE", start_d, end_d)
        if rows is not None:
            return rows, "library"
        return rule_sessions_stock(start_d, end_d), "rule"
    if asset_type == "futures":
        rows = library_sessions("CME_Equity", start_d, end_d)
        if rows is not None:
            return rows, "library"
        return rule_sessions_futures(start_d, end_d), "rule"
    if asset_type == "forex":
        return rule_sessions_forex(start_d, end_d), "rule"
    if asset_type == "crypto":
        return [], "always_open"
    return [], "unknown"


def week_schedule(days: int = 7) -> dict:
    """The per-class schedule for the next `days` days — the session-start
    orientation fact. Per class: whether it is open right now (by the clock),
    each session's open/close (UTC + compact ET), the NEXT open and close, and
    the answering `source` (library = holiday/half-day aware; rule = plain
    weekday windows). Plus the window's closed weekdays for stock (holidays)."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    from aitrader.timeutil import utcnow

    now = utcnow().astimezone(timezone.utc)
    start_d = now.date() - timedelta(days=1)   # catch a session already in progress
    end_d = now.date() + timedelta(days=days)
    payload: dict = {
        "as_of_utc": now.isoformat(),
        "as_of_et": now.astimezone(ZoneInfo(ET_ZONE)).strftime("%a %m/%d %H:%M ET"),
        "days": days,
        "classes": {},
    }

    for asset_type in ("stock", "futures", "forex", "crypto"):
        if asset_type == "crypto":
            payload["classes"]["crypto"] = {
                "open_now": True, "always_open": True, "source": "rule",
                "note": "24/7 market clock; whether THIS broker offers crypto is get_available_types",
            }
            continue
        rows, source = class_sessions(asset_type, start_d, end_d)
        rows = [(o, c) for o, c in rows if c > now - timedelta(days=2)]
        open_now = any(o <= now < c for o, c in rows)
        next_open = next((o for o, c in rows if o > now), None)
        current_close = next((c for o, c in rows if o <= now < c), None)
        next_close = current_close or next((c for o, c in rows if o > now), None)
        payload["classes"][asset_type] = {
            "open_now": open_now,
            "sessions": [
                {"open_utc": o.isoformat(), "close_utc": c.isoformat(),
                 "et": format_span_et(o, c)}
                for o, c in rows if c > now
            ],
            "next_open_utc": next_open.isoformat() if next_open else None,
            "next_open_et": next_open.astimezone(ZoneInfo(ET_ZONE)).strftime("%a %m/%d %H:%M ET") if next_open else None,
            "next_close_utc": next_close.isoformat() if next_close else None,
            "source": source,
        }

    payload["classes"]["options"] = {"note": "follows the stock regular session (see stock)"}

    stock_rows, stock_source = class_sessions("stock", now.date(), end_d)
    if stock_source == "library":
        from datetime import timedelta as td
        session_dates = {o.astimezone(ZoneInfo(ET_ZONE)).date() for o, _ in stock_rows}
        holidays = []
        d = now.date()
        while d <= end_d:
            if d.weekday() < 5 and d not in session_dates:
                holidays.append(d.isoformat())
            d += td(days=1)
        payload["stock_closed_weekdays_in_window"] = holidays
    return payload


def format_close_for_log(close: datetime) -> str:
    """Render a UTC session close as 'HH:MM ET / HH:MM UTC on YYYY-MM-DD'."""
    from zoneinfo import ZoneInfo
    et = close.astimezone(ZoneInfo("America/New_York"))
    return f"{et.strftime('%H:%M')} ET / {close.strftime('%H:%M')} UTC on {et.strftime('%Y-%m-%d')}"


def clear_cache() -> None:
    """Drop the entire cache. For tests."""
    session_close_cache.clear()
