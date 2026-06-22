---
name: equity-snapshots-order-by-ts
description: aitrader 0.15.3: equity_read orders by ts (not id). day_pl & /portfolio_history assume time order; backfilled/imported history has out-of-order ids a…
metadata:
  type: project
---

`journal_db.equity_read` must order by **`ts DESC, id DESC`**, NOT `id DESC`.

`day_pl` (api.py: baseline = earliest snapshot of the ET day, taken as `rows[-1]`)
and `/portfolio_history` (reverses the rows to get a chronological curve) both
assume equity_read returns rows newest-first **by time**. `id DESC` only equals
time order when snapshots are written in chronological order.

**How it broke (2026-06-18):** after importing the trader account's
`equity_snapshots` history into aitrader's journal.db (a migration the user asked
for — see [[equity-snapshot-recorder-cron]]), the backfilled rows got HIGHER ids
than today's already-written cron rows even though their ts were earlier. So
`day_pl`'s `rows[-1]` (lowest id today) picked the first **cron** row (mid-day
64707.67) instead of the imported **00:xx daily** (64489.15), and day_pl read
+59/+76 instead of the true ~+350. `/portfolio_history` returned the series in
insertion order → wrong base_value, scrambled chart.

**Fix:** order by ts (ts is a uniform UTC ISO8601 `+00:00` string, so lexical ==
chronological; id is the tiebreak for equal ts). Fixes day_pl, /portfolio_history,
and the journal MCP `equity_snapshot_read` at once.

**Lesson:** any "first/earliest/latest by time" query over a table that can be
backfilled must order by the timestamp column, never by the autoincrement id.
Verified day_pl then matched Alpaca's authoritative `equity − last_equity`. The
imported trader daily (64489.15) ≈ Alpaca `last_equity` (64489.26) — same account
lineage, so it's the correct prior-day-close baseline. See
[[api-multibroker-and-version-drift]].</body>
