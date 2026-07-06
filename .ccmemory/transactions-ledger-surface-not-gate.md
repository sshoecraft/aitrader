---
name: transactions-ledger-surface-not-gate
description: 1.32.x: transactions ledger (broker fills → journal.db, by symbol/timeframe) fixes churn; constitution SURFACES history via FORCED TABLE, never gates…
metadata:
  type: project
tags: [transactions, churn, constitution, journal_db, broker_mcp]
---

## Why (churn root cause)
The agent churns (XRP: ~$1k lost re-buying a just-stop-churned name, then re-buying it AGAIN next cycle) because it has **no memory of its own executions**. Journal = prose; `orders_of_record` had 15 rows for 548 real fills; `positions_of_record` purged to 0. Real trade history lived only at the broker, undigested.

## What (1.32.0)
A plain **transaction ledger**, NOT a P&L engine (user explicitly rejected FIFO/realized-P&L — the raw buy/sell sequence is self-evidently the churn signal).
- `transactions` table in journal.db (`journal_db.py` 0.2.0): one row per broker FILL, PK `fill_id`, idempotent `tx_upsert` (ON CONFLICT COALESCE so a re-sync that can't re-classify never wipes a found reason), `tx_read(symbol, since, limit)`, `tx_latest_time`.
- `sync_transactions(b)` (broker MCP `broker_server.py` 0.7.0): mirrors `get_fill_activities` into the table. Modeled on `maybe_backfill_equity` (same "broker MCP writes journal.db after a confirmed-good read" precedent, [[equity-backfill-on-first-sync]]) but INCREMENTAL + throttled (≤1/45s via `_last_tx_sync`). Called from `get_account`+`get_positions` (NOT `broker_status` — keep readiness poll fast). Backfills the broker's ~30d; persists beyond it. A fill is a FACT (append-only log), so it does NOT violate §6.
- `reason` best-effort, degrades to null: agent's own `intent` (join `order_ref`→`orders_of_record.client_tag`) OR factual exit label off order type (`stopped out`/`take profit`/`manual`). One `get_orders(status="all")` per sync.
- `transactions_read(symbol, since, limit)` tool on journal MCP (`journal_server.py` 0.2.0).

## The load-bearing design principle (user's steer)
The constitution SURFACES the history and STOPS — never gates, never demands justification, never labels a name "bad." Infra reports facts; the agent decides (§2). If it buys something it stopped out of 4× today, that's its call. An anti-churn brake in code OR prompt would be cognition-in-infra — the inversion we reject.

## 1.32.1 — the enforcement lesson (CRITICAL, reconfirms [[constitution-enforce-via-step-not-column]])
1.32.0 wrote HISTORY as a prose LINE with an "or 'no recent activity'" escape. First live cycle: the local model wrote `HISTORY BTC/USD: No recent activity` **from memory, NEVER calling `transactions_read`** — and it was FALSE (ledger showed BTC bought→stopped→re-bought→stopped in 3 days); it then bought more BTC on the fabricated line. Lesson: **a required LINE of prose can be authored from memory; only a forced artifact whose cells ARE a live tool's output resists fabrication.** Fix: HISTORY → a FORCED TABLE on the step-9(e) pattern (one row per name about to be bought, fills column = the `transactions_read` RETURNED ROWS pasted verbatim, "cannot be asserted from memory", "no recent activity" legal ONLY when the tool returned zero). The proven-compliant constitution artifacts (9(e) trail table, step-4 movers table) all share this shape: a table whose cells must be read off a tool call. Prose riders and fakeable lines get a hollow pass. See [[constitution-steps-not-prose]], [[constitution-trail-forced-table-9e]].

## Verified
Plumbing verified end-to-end against REAL Alpaca fills (548 fills, idempotent, exit-classification + intent-join work, XRP+BTC churn legible) AND live in production (agent's own broker MCP populated journal.db on first reconcile). BEHAVIORAL compliance (does it call the tool + paste rows) = the open question the 1.32.1 forced-table is meant to fix; watch the transcript for `transactions_read` calls before entries.
