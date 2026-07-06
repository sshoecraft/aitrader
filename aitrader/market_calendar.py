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

__version__ = "0.2.0"

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


def format_close_for_log(close: datetime) -> str:
    """Render a UTC session close as 'HH:MM ET / HH:MM UTC on YYYY-MM-DD'."""
    from zoneinfo import ZoneInfo
    et = close.astimezone(ZoneInfo("America/New_York"))
    return f"{et.strftime('%H:%M')} ET / {close.strftime('%H:%M')} UTC on {et.strftime('%Y-%m-%d')}"


def clear_cache() -> None:
    """Drop the entire cache. For tests."""
    session_close_cache.clear()
