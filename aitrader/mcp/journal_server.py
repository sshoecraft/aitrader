"""journal MCP — the agent's durable notebook + reconciliation records.

Infrastructure only. This server stores and returns what the agent writes; it
NEVER decides anything. `thesis`, `planned_exit`, and `intent` are free-form
prose the agent authors in its own words.

Run: aitrader-journal-mcp  (stdio)
"""

__version__ = "0.2.2"

import re

from mcp.server.fastmcp import FastMCP

from aitrader import journal_db as J
from aitrader.asset_types import clean_symbol
from aitrader.timeutil import utcnow_iso, parse_iso, local_display, et_display

mcp = FastMCP("aitrader-journal")

# One process-wide connection. sqlite WAL handles concurrent readers; this
# server is single-threaded over stdio so a shared handle is fine.
_conn = None


def conn():
    global _conn
    if _conn is None:
        _conn = J.get_db()
    return _conn


# ── reconcile-clock normalization ──────────────────────────────────────────
# The agent hand-types a "Local: <date> HH:MM TZ / HH:MM UTC" line in its
# reconcile body. Over a long looping session the local model can reach past the
# big step-3..5 tables and copy a PRIOR cycle's now() result, writing a
# ~one-cycle-stale time (observed live: journal entries 375/376 sat ~2h06m
# behind their own row ts). The row's server-stamped ts is always authoritative,
# so a grossly-drifted Local line is rewritten to the canonical ts-derived
# value. The legitimate ~2-3 min gap between the step-1 now() read and this
# write is BELOW tolerance and left untouched (fresh entries keep their
# reconcile-time semantics); only gross lag is corrected, and the correction is
# marked in-body, never silent.
CLOCK_DRIFT_TOLERANCE_MIN = 10
LOCAL_LINE_RE = re.compile(
    r'^(?P<prefix>[ \t]*[-*]?[ \t]*Local:[ \t]*)(?P<val>[^\n]*)$',
    re.IGNORECASE | re.MULTILINE)
UTC_TOKEN_RE = re.compile(r'(\d{1,2}):(\d{2})\s*UTC', re.IGNORECASE)


def normalize_reconcile_clock(body, ts):
    """Rewrite a grossly-stale 'Local: … / HH:MM UTC' line to match the row's
    authoritative `ts`. Returns `body` unchanged when there is no such line, no
    parseable UTC token, or the stated time is within tolerance. NEVER raises —
    a normalization failure must not fail the write."""
    from datetime import timedelta
    try:
        m = LOCAL_LINE_RE.search(body)
        if not m:
            return body
        um = UTC_TOKEN_RE.search(m.group("val"))
        if not um:
            return body
        dt = parse_iso(ts)
        stated_h, stated_m = int(um.group(1)) % 24, int(um.group(2)) % 60
        base = dt.replace(hour=stated_h, minute=stated_m, second=0, microsecond=0)
        # Resolve the stated HH:MM against the row date ±1 day so a legitimate
        # near-midnight time is never mistaken for a ~24h drift.
        drift = min(abs((base + timedelta(days=off)) - dt) for off in (-1, 0, 1))
        if drift <= timedelta(minutes=CLOCK_DRIFT_TOLERANCE_MIN):
            return body
        parts = local_display(dt).split()
        ldate, ltime = parts[0], parts[1][:5]
        ltz = parts[2] if len(parts) > 2 else ""
        canon = f"{ldate} {ltime}" + (f" {ltz}" if ltz else "") + \
                f" / {dt.strftime('%H:%M')} UTC"
        canon += f" [clock auto-corrected — body said {stated_h:02d}:{stated_m:02d} UTC]"
        return body[:m.start("val")] + canon + body[m.end("val"):]
    except Exception:
        return body


# ── notebook ──────────────────────────────────────────────────────────────

@mcp.tool()
def journal_write(kind: str = None, body: str = None, symbol: str = None, tags: str = None) -> dict:
    """Append a timestamped entry to the durable notebook.

    kind: a free tag you choose (e.g. thesis, entry, exit, watch, note,
          reconcile). symbol/tags optional. The entry is stamped with the
          current UTC time. Returns {id, ts, local, et} — `ts` is the
          authoritative UTC stamp; `local`/`et` are that stamp rendered in the
          host and NYSE clocks so you never hand-derive them.

    A grossly-stale reconcile `Local:` line in the body (a prior cycle's clock
    copied across the survey tables) is rewritten to match `ts` — see
    normalize_reconcile_clock.
    """
    # The local model's parser mangles long calls: it appends a stray backtick
    # to the last string arg and can FUSE the next arg into it (observed:
    # body ending `...exposure.\n`,kind: "reconcile"` with kind missing).
    # Recover the fused kind from the body tail instead of failing the write.
    body = str(body or "")
    if not kind:
        m = re.search(r'[`\s]*[,;]\s*kind\s*[:=]\s*["\']?([\w-]+)["\']?\s*$', body)
        if m:
            kind = m.group(1)
            body = body[:m.start()]
    body = body.rstrip().rstrip("`").rstrip()
    if not body:
        raise ValueError("journal_write needs a non-empty body")
    kind = (str(kind).strip().strip("`") if kind else "") or "note"
    tags = str(tags).strip().strip("`") if tags else tags
    ts = utcnow_iso()
    body = normalize_reconcile_clock(body, ts)
    rowid = J.journal_write(conn(), ts, kind, body, symbol=clean_symbol(symbol), tags=tags)
    dt = parse_iso(ts)
    return {"id": rowid, "ts": ts, "local": local_display(dt), "et": et_display(dt)}


@mcp.tool()
def journal_read(limit: int = 50, kind: str = None, symbol: str = None,
                 since: str = None) -> dict:
    """Read recent notebook entries, newest first, as {count, entries: [...]}.

    Filter by kind, symbol, and/or since (UTC ISO-8601). Read this at the top
    of every cycle to recover what you were thinking and waiting for.
    """
    entries = J.journal_read(conn(), limit=limit, kind=kind, symbol=clean_symbol(symbol), since=since)
    return {"count": len(entries), "entries": entries}


@mcp.tool()
def journal_search(query: str, limit: int = 50) -> dict:
    """Full-text-ish substring search over notebook bodies, newest first, as
    {count, entries: [...]}."""
    entries = J.journal_search(conn(), query, limit=limit)
    return {"count": len(entries), "entries": entries}


# ── positions of record (the "why" behind broker positions) ───────────────

@mcp.tool()
def position_record_upsert(symbol: str, asset_type: str = None, thesis: str = None,
                           entry_rationale: str = None, planned_exit: str = None,
                           status: str = None) -> dict:
    """Record/update the *intent* behind a position — the thing the broker
    cannot tell you. All text fields are your own prose; only fields you pass
    are changed. planned_exit is a NOTE, not a rule the system enforces.
    """
    return J.por_upsert(conn(), utcnow_iso(), clean_symbol(symbol), asset_type=asset_type,
                        thesis=thesis, entry_rationale=entry_rationale,
                        planned_exit=planned_exit, status=status)


@mcp.tool()
def position_record_get(symbol: str) -> dict:
    """Get the position-of-record for a symbol, or null if none."""
    return J.por_get(conn(), clean_symbol(symbol))


@mcp.tool()
def position_record_list(status: str = None) -> dict:
    """List positions-of-record, optionally filtered by status
    (open/closing/closed/watch), as {count, records: [...]}."""
    recs = J.por_list(conn(), status=status)
    return {"count": len(recs), "records": recs}


@mcp.tool()
def position_record_delete(symbol: str) -> dict:
    """Remove a position-of-record (e.g. after a fully closed position is reconciled)."""
    symbol = clean_symbol(symbol)
    J.por_delete(conn(), symbol)
    return {"deleted": symbol}


# ── equity snapshots ──────────────────────────────────────────────────────

@mcp.tool()
def equity_snapshot_write(equity: float = None, cash: float = None,
                          buying_power: float = None, realized_pnl: float = None,
                          unrealized_pnl: float = None, notes: str = None) -> dict:
    """Record a point-in-time account snapshot (your own time series, for
    tracking P&L over the run). Stamped with the current UTC time.
    """
    ts = utcnow_iso()
    rowid = J.equity_write(conn(), ts, equity=equity, cash=cash,
                           buying_power=buying_power, realized_pnl=realized_pnl,
                           unrealized_pnl=unrealized_pnl, notes=notes)
    return {"id": rowid, "ts": ts}


@mcp.tool()
def equity_snapshot_read(limit: int = 50, since: str = None) -> dict:
    """Read recent equity snapshots, newest first, as {count, snapshots: [...]}."""
    snaps = J.equity_read(conn(), limit=limit, since=since)
    return {"count": len(snaps), "snapshots": snaps}


# ── orders of record (idempotency) ────────────────────────────────────────

@mcp.tool()
def order_record(client_tag: str, symbol: str, side: str, qty: float = None,
                 intent: str = None, broker_order_id: str = None,
                 status: str = None) -> dict:
    """Record an order under a DETERMINISTIC client_tag BEFORE/AFTER placing it.

    The client_tag is your idempotency key: derive it deterministically (e.g.
    from symbol + side + date + thesis) so that if you crash and relaunch you
    can look it up and recognize your own in-flight order instead of double-
    submitting. Upsert — call again with broker_order_id/status to update it.
    """
    return J.order_record(conn(), utcnow_iso(), client_tag, clean_symbol(symbol), side,
                          qty=qty, intent=intent, broker_order_id=broker_order_id,
                          status=status)


@mcp.tool()
def order_record_get(client_tag: str) -> dict:
    """Look up an order-of-record by client_tag, or null. Use on reconcile to
    detect whether an order you intended was already placed/filled."""
    return J.order_get(conn(), client_tag)


@mcp.tool()
def order_record_list(status: str = None, symbol: str = None) -> dict:
    """List orders-of-record, optionally filtered by status and/or symbol, as
    {count, records: [...]}."""
    recs = J.order_list(conn(), status=status, symbol=clean_symbol(symbol))
    return {"count": len(recs), "records": recs}


# ── transactions (your own trade history) ──────────────────────────────────

@mcp.tool()
def transactions_read(symbol: str = None, since: str = None, limit: int = 100) -> list:
    """Your own trade history — every fill you've had (bought / sold), newest
    first, each with its reason.

    This is the durable record of what you ACTUALLY DID, synced from the broker:
    `transaction_time, side, symbol, qty, price, reason`. `reason` is your own
    recorded rationale where you wrote one, otherwise the factual exit mechanism
    (stopped out / take profit / manual) — never a score or opinion.

    Filter by `symbol` and/or `since` (UTC ISO-8601) to see exactly what you did
    with a name over a window BEFORE you act on it again — e.g. whether you have
    been buying and selling the same ticker back and forth. It reports the facts;
    what you conclude from them is yours to decide.

    Returns {count, transactions: [...]} — the same shape at 0, 1, or many;
    count==0 is the ONLY form of "no recent activity".
    """
    tx = J.tx_read(conn(), symbol=clean_symbol(symbol), since=since, limit=limit)
    return {"count": len(tx), "transactions": tx}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
