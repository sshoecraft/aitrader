"""Journal storage — the agent's durable notebook + reconciliation records.

This is a NOTEBOOK, not a state machine. It stores the things the broker
cannot tell you: *why* a position exists, what the agent is watching, what it
is waiting for. It contains ZERO cognition — no thresholds, no scoring, no
exit logic. `planned_exit` and `thesis` are free-form prose the agent writes
in its own words; nothing here ever decides anything.

Four record kinds:
  journal              free-form timestamped notebook entries (theses, notes)
  positions_of_record  the agent's intent layer over broker positions (the "why")
  equity_snapshots     account-state time series the agent writes for itself
  orders_of_record     client_tag -> order intent, for idempotent reconcile

Times are stored as UTC ISO-8601 strings. The caller supplies timestamps
(the journal does not invent a clock — `register_now` lets the broker MCP's
clock drive it, but a plain UTC string is accepted everywhere).
"""

__version__ = "0.1.0"

import os
import sqlite3
import time

from aitrader.paths import JOURNAL_DB


def get_db(path=None, check_same_thread=True):
    """Open (and initialize) the journal database. Returns a sqlite3.Connection.

    check_same_thread=False lets a single connection be shared across threads
    (e.g. the API's FastAPI threadpool, which only reads). The stdio MCP servers
    are single-threaded and keep the default True.
    """
    if path is None:
        path = JOURNAL_DB
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None,
                           check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    create_schema(conn)
    return conn


def create_schema(conn):
    """Create tables if absent. Idempotent."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS journal (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT NOT NULL,            -- UTC ISO-8601
            kind      TEXT NOT NULL,            -- free tag: thesis|entry|exit|watch|note|reconcile|...
            symbol    TEXT,                     -- nullable
            body      TEXT NOT NULL,
            tags      TEXT                      -- optional free text / csv
        );
        CREATE INDEX IF NOT EXISTS idx_journal_ts     ON journal(ts);
        CREATE INDEX IF NOT EXISTS idx_journal_kind   ON journal(kind);
        CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal(symbol);

        CREATE TABLE IF NOT EXISTS positions_of_record (
            symbol           TEXT PRIMARY KEY,
            asset_type       TEXT,
            thesis           TEXT,    -- why we hold it (agent's prose)
            entry_rationale  TEXT,    -- why we entered (agent's prose)
            planned_exit     TEXT,    -- agent's prose plan, NOT a deterministic rule
            status           TEXT DEFAULT 'open',  -- open|closing|closed|watch
            opened_at        TEXT,
            last_reviewed_at TEXT,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_por_status ON positions_of_record(status);

        CREATE TABLE IF NOT EXISTS equity_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              TEXT NOT NULL,
            equity          REAL,
            cash            REAL,
            buying_power    REAL,
            realized_pnl    REAL,
            unrealized_pnl  REAL,
            notes           TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_equity_ts ON equity_snapshots(ts);

        CREATE TABLE IF NOT EXISTS orders_of_record (
            client_tag       TEXT PRIMARY KEY,  -- deterministic idempotency key
            symbol           TEXT NOT NULL,
            side             TEXT NOT NULL,     -- buy|sell
            qty              REAL,
            intent           TEXT,              -- agent's prose: why this order
            broker_order_id  TEXT,              -- filled in once the broker accepts it
            status           TEXT DEFAULT 'intended',  -- intended|placed|filled|canceled|rejected
            placed_at        TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_oor_status ON orders_of_record(status);
        CREATE INDEX IF NOT EXISTS idx_oor_symbol ON orders_of_record(symbol);
        """
    )


def _exec(conn, sql, params=(), retries=4, base_delay=0.05):
    """Execute with retry on transient 'database is locked'."""
    for attempt in range(retries):
        try:
            return conn.execute(sql, params)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


# ── journal (notebook) ────────────────────────────────────────────────────

def journal_write(conn, ts, kind, body, symbol=None, tags=None):
    cur = _exec(
        conn,
        "INSERT INTO journal (ts, kind, symbol, body, tags) VALUES (?,?,?,?,?)",
        (ts, kind, symbol, body, tags),
    )
    return cur.lastrowid


def journal_read(conn, limit=50, kind=None, symbol=None, since=None):
    sql = "SELECT * FROM journal WHERE 1=1"
    params = []
    if kind is not None:
        sql += " AND kind = ?"; params.append(kind)
    if symbol is not None:
        sql += " AND symbol = ?"; params.append(symbol)
    if since is not None:
        sql += " AND ts >= ?"; params.append(since)
    sql += " ORDER BY id DESC LIMIT ?"; params.append(int(limit))
    return _rows(_exec(conn, sql, tuple(params)))


def journal_search(conn, query, limit=50):
    cur = _exec(
        conn,
        "SELECT * FROM journal WHERE body LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{query}%", int(limit)),
    )
    return _rows(cur)


# ── positions of record (the "why") ───────────────────────────────────────

def por_upsert(conn, now, symbol, asset_type=None, thesis=None,
               entry_rationale=None, planned_exit=None, status=None,
               opened_at=None, last_reviewed_at=None):
    """Insert or update a position-of-record. Only provided fields change."""
    existing = por_get(conn, symbol)
    if existing is None:
        _exec(
            conn,
            """INSERT INTO positions_of_record
               (symbol, asset_type, thesis, entry_rationale, planned_exit,
                status, opened_at, last_reviewed_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (symbol, asset_type, thesis, entry_rationale, planned_exit,
             status or "open", opened_at or now, last_reviewed_at, now),
        )
    else:
        fields = {
            "asset_type": asset_type, "thesis": thesis,
            "entry_rationale": entry_rationale, "planned_exit": planned_exit,
            "status": status, "opened_at": opened_at,
            "last_reviewed_at": last_reviewed_at,
        }
        sets, params = [], []
        for k, v in fields.items():
            if v is not None:
                sets.append(f"{k} = ?"); params.append(v)
        sets.append("updated_at = ?"); params.append(now)
        params.append(symbol)
        _exec(conn, f"UPDATE positions_of_record SET {', '.join(sets)} WHERE symbol = ?", tuple(params))
    return por_get(conn, symbol)


def por_get(conn, symbol):
    rows = _rows(_exec(conn, "SELECT * FROM positions_of_record WHERE symbol = ?", (symbol,)))
    return rows[0] if rows else None


def por_list(conn, status=None):
    if status is None:
        return _rows(_exec(conn, "SELECT * FROM positions_of_record ORDER BY symbol"))
    return _rows(_exec(conn, "SELECT * FROM positions_of_record WHERE status = ? ORDER BY symbol", (status,)))


def por_delete(conn, symbol):
    _exec(conn, "DELETE FROM positions_of_record WHERE symbol = ?", (symbol,))


# ── equity snapshots ──────────────────────────────────────────────────────

def equity_write(conn, ts, equity=None, cash=None, buying_power=None,
                 realized_pnl=None, unrealized_pnl=None, notes=None):
    cur = _exec(
        conn,
        """INSERT INTO equity_snapshots
           (ts, equity, cash, buying_power, realized_pnl, unrealized_pnl, notes)
           VALUES (?,?,?,?,?,?,?)""",
        (ts, equity, cash, buying_power, realized_pnl, unrealized_pnl, notes),
    )
    return cur.lastrowid


def equity_read(conn, limit=50, since=None):
    # Order by ts (the actual snapshot time), NOT id. id is insertion order, which
    # only matches chronological order when rows are written in time order — false
    # when history is backfilled/imported (e.g. migrating another account's
    # equity_snapshots in). Callers (day_pl baseline, /portfolio_history curve)
    # assume newest-first-by-time, so an id/ts mismatch picks the wrong baseline
    # and scrambles the curve. ts is a uniform UTC ISO8601 string (+00:00), so
    # lexical DESC == chronological DESC; id is the tiebreak for equal ts.
    sql = "SELECT * FROM equity_snapshots WHERE 1=1"
    params = []
    if since is not None:
        sql += " AND ts >= ?"; params.append(since)
    sql += " ORDER BY ts DESC, id DESC LIMIT ?"; params.append(int(limit))
    return _rows(_exec(conn, sql, tuple(params)))


def equity_ts_set(conn):
    """Set of all equity-snapshot timestamps — lets the broker MCP's one-time backfill
    skip points already recorded, so a broker-history import composes with the live
    recorder without duplicates (broker = daily, recorder = 15-min → no collision).
    Pure storage: no broker, no network."""
    return {r[0] for r in _exec(conn, "SELECT ts FROM equity_snapshots").fetchall()}


# ── orders of record (idempotency) ────────────────────────────────────────

def order_record(conn, now, client_tag, symbol, side, qty=None, intent=None,
                 broker_order_id=None, status=None):
    """Record an order intent under a deterministic client_tag (upsert)."""
    existing = order_get(conn, client_tag)
    if existing is None:
        _exec(
            conn,
            """INSERT INTO orders_of_record
               (client_tag, symbol, side, qty, intent, broker_order_id,
                status, placed_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (client_tag, symbol, side, qty, intent, broker_order_id,
             status or "intended", now, now),
        )
    else:
        fields = {"symbol": symbol, "side": side, "qty": qty, "intent": intent,
                  "broker_order_id": broker_order_id, "status": status}
        sets, params = [], []
        for k, v in fields.items():
            if v is not None:
                sets.append(f"{k} = ?"); params.append(v)
        sets.append("updated_at = ?"); params.append(now)
        params.append(client_tag)
        _exec(conn, f"UPDATE orders_of_record SET {', '.join(sets)} WHERE client_tag = ?", tuple(params))
    return order_get(conn, client_tag)


def order_get(conn, client_tag):
    rows = _rows(_exec(conn, "SELECT * FROM orders_of_record WHERE client_tag = ?", (client_tag,)))
    return rows[0] if rows else None


def order_list(conn, status=None, symbol=None):
    sql = "SELECT * FROM orders_of_record WHERE 1=1"
    params = []
    if status is not None:
        sql += " AND status = ?"; params.append(status)
    if symbol is not None:
        sql += " AND symbol = ?"; params.append(symbol)
    sql += " ORDER BY updated_at DESC"
    return _rows(_exec(conn, sql, tuple(params)))
