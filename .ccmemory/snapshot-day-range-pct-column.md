---
name: snapshot-day-range-pct-column
description: 1.49.5: snapshot CSV gains day_range_pct (today's high-low spread as % of price) — itrader self-caught raw-%-move ranking burying mid-caps under penn…
metadata:
  type: project
tags: [broker_server, snapshot, rank_instruments, itrader, mid-cap, hard-boundary]
---

## Origin (2026-07-13)

Owner's wife (Julie) asked itrader, in a live Q&A, why its candidate lists
never seem to include small/mid-caps despite them "rockin' lately." itrader's
own answer self-diagnosed a real structural gap: ranking the whole
12,941-name stock universe by raw `pct_1d` ("biggest % move, top 3") is
mechanically won by low-priced names every time — a $4 stock can physically
post a bigger % move than a $300 one on the same dollar move, so a genuine
move in a quality mid-cap is invisible to that ranking. itrader named this
the exact blindness that hid MPC (its best trade that day) for five straight
cycles, and said it wanted "a screen filtered by tradeable geometry
(volatility under ~5% of price, real dollar volume) rather than raw % move."

## Why this was a small infra fix, not a cognition change

Per the constitution's Hard Boundary (§2): ranking by a raw FACT is infra,
ranking by an opinion of edge/quality is cognition. `day_range_pct` = (day_high
− day_low) / price × 100 is a pure arithmetic fact about today's trading —
same category as `pct_intraday`/`gap_pct`/`range_pos` (CHANGELOG 1.40.0),
which were added for the identical reason: make a useful derived fact cheap
and always-there instead of every agent hand-deriving it in a scratch script.
It sets no threshold, picks no shortlist — the agent still supplies `by`,
floors, and direction, and still decides everything downstream.

Important nuance caught before implementing: itrader saying "I'd like to
build that" was somewhat misleading — it has no path to edit aitrader's code;
only the owner/Claude-Code-on-/src/aitrader does. Most of what it wanted
(volatility-normalized ranking) was ALREADY available to it via
`rank_instruments(by=<any snapshot column>)` plus its own sandbox (it had
just proven it's willing to write scratch scripts, e.g. the ATR script and
the tanker/pipeline segment script same session) — deriving
`(day_high-day_low)/price` itself would have cost nothing new. The one
genuinely-missing piece was making that specific fact a zero-cost, always-on
column instead of something hand-rolled per cycle — that's the actual, narrow
gap this fix closes.

## What changed (1.49.5)

`aitrader/mcp/broker_server.py` 0.10.3 → 0.10.4:
- New snapshot CSV column `day_range_pct`, computed alongside
  `pct_intraday`/`gap_pct`/`range_pos` in `snapshot_type_to_csv` (same
  blank-when-bar-hasn't-rolled-to-today rule).
- `get_all_snapshots` and `rank_instruments` docstrings updated with the new
  column.
- No new tool, no wiring: `rank_instruments(by="day_range_pct", ...)` works
  immediately because `by` is validated dynamically against whatever columns
  the row actually has.

Verified via a throwaway script (`/tmp`, not committed) with synthetic
snapshot dicts for a $4 and a $300 name (not real market data — this is
testing the arithmetic/plumbing, not asserting anything about real
symbols): `day_range_pct` correctly puts both on comparable footing, is
blank exactly when the bar hasn't rolled to today, and
`rank_instruments(by="day_range_pct")` ranks by it end-to-end with zero
other code changes.

Deploy is owner-run — prepared in `/src/aitrader` only, not yet deployed as
of this writing.

## Verification still needed

After deploy: confirm the column appears in a live `snapshots_stock.csv` and
that itrader can successfully call `rank_instruments(by="day_range_pct")`
without error. Whether it actually STARTS using it to surface mid-caps is
itrader's own judgment call, per the Hard Boundary — not something to force
or check for compliance.
