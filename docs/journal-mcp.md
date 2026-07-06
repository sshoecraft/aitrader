# journal MCP

The agent's durable notebook + reconciliation records. **Pure infrastructure —
zero cognition.** It stores and returns what the agent writes; it never decides.

- Server: `aitrader/mcp/journal_server.py` (FastMCP, stdio) → `aitrader-journal-mcp`
- Storage: `aitrader/journal_db.py`, sqlite at `$AITRADER_JOURNAL_DB`
  (default `~/.local/state/aitrader/journal.db`), WAL mode.

## Why it exists (BRIEF §3)
Context is scratch; the journal is the real memory. The agent reads it at the
top of every cycle to recover its theses and what it was waiting for. The broker
is the source of truth for *what is*; the journal is the source of truth for
*why*. Together they make crash-and-relaunch safe.

## Schema (5 record kinds)
| table | purpose | key fields |
|---|---|---|
| `journal` | free-form timestamped notebook | ts, kind, symbol, body, tags |
| `positions_of_record` | intent layer over broker positions (the "why") | symbol(PK), thesis, entry_rationale, planned_exit, status |
| `equity_snapshots` | account-state time series the agent writes for itself | ts, equity, cash, buying_power, pnl |
| `orders_of_record` | client_tag → order intent, for idempotent reconcile | client_tag(PK), broker_order_id, status |
| `transactions` | the agent's trade-history ledger — one row per broker FILL, synced from the broker (1.32.0) | fill_id(PK), symbol, side, qty, price, transaction_time, order_ref, reason |

`thesis`, `planned_exit`, `intent` are **free-form prose** in the agent's own
words. `planned_exit` is a NOTE, never a rule the system enforces — exit logic
lives in the agent's reasoning, not here.

## Tools (13)
- Notebook: `journal_write`, `journal_read`, `journal_search`
- Positions of record: `position_record_upsert`, `position_record_get`,
  `position_record_list`, `position_record_delete`
- Equity: `equity_snapshot_write`, `equity_snapshot_read`
- Orders of record (idempotency): `order_record`, `order_record_get`,
  `order_record_list`
- Trade history: `transactions_read(symbol, since, limit)` — the agent's own fills,
  newest-first, with reasons; read to see what it did with a name before acting again

## Transactions ledger (1.32.0)
The `transactions` table is the agent's durable trade history: one row per broker
fill, **synced FROM the broker by the broker MCP** (`sync_transactions`, see
broker-mcp.md) — the journal MCP only READS it here. It is an append-only log of
FACTS (a fill happened), so unlike positions/orders it never conflicts with "trust
the broker over the journal": it is reconstructed from the broker and persists
beyond the broker's ~30d retention. `reason` is the agent's own recorded `intent`
(joined via `order_ref`→`orders_of_record.client_tag`) or a factual exit label
(`stopped out`/`take profit`/`manual`, read off the order type) — **never a computed
P&L, score, or opinion.** No FIFO, no realized-P&L: the raw buy/sell sequence is the
signal. The agent reads it; what it concludes is its own decision (§2).

## Idempotency contract (BRIEF §5)
Before placing an order the agent records it under a **deterministic**
`client_tag` (e.g. `SYMBOL-side-YYYY-MM-DD-thesisslug`). After a crash+relaunch
it looks the tag up; if present it recognizes its own in-flight order and does
not double-submit. The same tag should be passed to the broker as the order's
client id / tag so broker truth and journal intent line up on reconcile.

## Status
Built and unit-tested (2026-06-15) without a broker — sqlite only. All 12 tools
register; DB CRUD + partial-update semantics verified.

## Provenance
Clean-room schema. The old `/src/trader/trader/db.py` was inspected for shape
only; its pyramid/trail/rejection/heat/opening-bell tables (engine state-machine
cognition) were deliberately NOT ported. The `reviews` table (old LLM-reviewer
pipeline) was dropped per BRIEF §A.1.
