"""scheduler MCP — pure blocking-wait mechanism (BRIEF §A.4.2).

This is how "I'll wait until the open" literally works: the agent issues ONE
tool call, the tool does not return until the condition is met, and the
session resumes in-place. The harness keeps the same long-lived `claude -p`
process alive across the wait.

ZERO trading logic. The scheduler decides nothing — it only sleeps until a
time/condition the agent named. Time facts come from the NYSE calendar
(`aitrader.market_calendar`: broker tier when available, else the offline
pandas_market_calendars library) — a factual schedule, not an opinion.

Deviations from the brief's first sketch, with rationale:
  - `wait_for_fill` lives in the BROKER MCP, not here. Polling an order needs
    the broker connection, which the broker MCP owns; a second process cannot
    share one IBKR socket cleanly. Keeping it there avoids a redundant
    connection.
  - Waits are chunked (not one long os-level sleep) so a multi-day weekend wait
    stays cancellable by process death (the harness can stop/relaunch mid-wait),
    and so a future broker-event wake can interrupt a sleep. `wait_seconds` is
    clamped to a floor (the cadence fuse: "never wake faster than ~5s"),
    settings.toml wake_floor_seconds (default 5).

Run: aitrader-scheduler-mcp  (stdio)
"""

__version__ = "0.2.0"

import asyncio
from datetime import timezone

from mcp.server.fastmcp import FastMCP

from aitrader import market_calendar as cal
from aitrader.config import settings
from aitrader.timeutil import utcnow, et_display, parse_iso

mcp = FastMCP("aitrader-scheduler")

WAKE_FLOOR_SECONDS = settings().wake_floor_seconds
CHUNK_SECONDS = 1.0  # granularity at which a long wait stays cancellable


def _now():
    return utcnow()


def _regular_session_bounds(when=None):
    """Return (open_utc, close_utc) for the NYSE regular session on `when`'s
    UTC date, or (None, None) if not a trading day / library unavailable."""
    if when is None:
        when = _now()
    d = when.astimezone(timezone.utc).date()
    close = cal.session_close_for(d, broker=None)
    if close is None:
        return None, None
    try:
        import pandas_market_calendars as mcal
        sched = mcal.get_calendar("NYSE").schedule(start_date=d, end_date=d)
        if sched.empty:
            return None, close
        opn = sched.iloc[0]["market_open"].to_pydatetime()
        opn = opn.replace(tzinfo=timezone.utc) if opn.tzinfo is None else opn.astimezone(timezone.utc)
        return opn, close
    except Exception:
        return None, close


async def _sleep_until(target_utc, label):
    """Chunked sleep until target_utc. Returns a result dict. Interruptible by
    process death (harness relaunch is safe)."""
    start = _now()
    if target_utc <= start:
        return {"waited_seconds": 0.0, "woke_reason": "already_past",
                "now_utc": start.isoformat(), "now_et": et_display(start), "target": target_utc.isoformat()}
    while True:
        now = _now()
        remaining = (target_utc - now).total_seconds()
        if remaining <= 0:
            return {"waited_seconds": (now - start).total_seconds(), "woke_reason": "condition_met",
                    "now_utc": now.isoformat(), "now_et": et_display(now),
                    "target": target_utc.isoformat(), "label": label}
        await asyncio.sleep(min(CHUNK_SECONDS, remaining))


# ── time facts ─────────────────────────────────────────────────────────────

@mcp.tool()
def now() -> dict:
    """Current time as UTC ISO-8601 plus an ET display string. Pure fact."""
    n = _now()
    return {"utc": n.isoformat(), "et": et_display(n)}


@mcp.tool()
def market_status() -> dict:
    """NYSE regular-session status right now: whether stocks' regular session is
    open, today's session close (UTC), and the next regular open (UTC).

    This is the STOCK (NYSE) clock only. For what is *tradeable right now*
    across asset classes (crypto/futures/forex have their own hours), read the
    broker MCP's get_available_types / get_market_session — those are broker
    truth. This tool is a scheduling aid, not a tradeability oracle.
    """
    n = _now()
    opn, close = _regular_session_bounds(n)
    regular_open = bool(opn and close and opn <= n <= close)
    nxt = cal.next_session_open(broker=None, start=n)
    return {
        "now_utc": n.isoformat(), "now_et": et_display(n),
        "regular_session_open": regular_open,
        "session_open_utc": opn.isoformat() if opn else None,
        "session_close_utc": close.isoformat() if close else None,
        "next_open_utc": nxt.isoformat() if nxt else None,
        "next_open_et": et_display(nxt) if nxt else None,
    }


# ── blocking waits ─────────────────────────────────────────────────────────

@mcp.tool()
async def wait_seconds(seconds: float) -> dict:
    """Block for `seconds`, then return. Clamped to a floor
    (settings.toml wake_floor_seconds, default 5) — the cadence fuse. Use this for
    active management ("check again in a minute").
    """
    secs = max(float(seconds), WAKE_FLOOR_SECONDS)
    target = _now().astimezone(timezone.utc)
    from datetime import timedelta
    return await _sleep_until(target + timedelta(seconds=secs), label=f"wait_seconds({secs})")


@mcp.tool()
async def wait_until(iso_utc: str) -> dict:
    """Block until the given UTC ISO-8601 time, then return. If the time is
    already past, returns immediately. Use for "wake me at 09:25 ET" by passing
    the corresponding UTC time.
    """
    target = parse_iso(iso_utc).astimezone(timezone.utc)
    return await _sleep_until(target, label=f"wait_until({iso_utc})")


@mcp.tool()
async def wait_until_market_open() -> dict:
    """Block until the next NYSE regular-session open, then return. If the
    regular session is open right now, returns immediately."""
    n = _now()
    opn, close = _regular_session_bounds(n)
    if opn and close and opn <= n <= close:
        return {"waited_seconds": 0.0, "woke_reason": "already_open",
                "now_utc": n.isoformat(), "now_et": et_display(n)}
    nxt = cal.next_session_open(broker=None, start=n)
    if nxt is None:
        return {"woke_reason": "unknown", "error": "next open unavailable (calendar library missing?)",
                "now_utc": n.isoformat()}
    return await _sleep_until(nxt, label="wait_until_market_open")


@mcp.tool()
async def wait_until_session_close() -> dict:
    """Block until today's NYSE regular-session close, then return. If already
    past the close (or not a trading day), returns immediately."""
    n = _now()
    _, close = _regular_session_bounds(n)
    if close is None:
        return {"woke_reason": "no_session_today", "now_utc": n.isoformat(), "now_et": et_display(n)}
    return await _sleep_until(close, label="wait_until_session_close")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
