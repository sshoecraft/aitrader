---
name: snapshot-csv-bounds-widen-aggregation-lag
description: 1.48.2: residual day_high/day_low violations after 1.48.1 (14.3%→3.83%) were vendor same-session aggregation lag, not session mismatch; widen bounds…
metadata:
  type: project
tags: [snapshots, get_all_snapshots, broker_server, data-quality, 1.48.2, alpaca]
---

# Residual day_high/day_low violations — fix 1.48.2 (2026-07-13)

## Context
Follow-on to [[snapshot-csv-stale-dailybar-rollover-fix]] (1.48.1). itrader's
own acceptance test (journal 378/379) re-ran its arithmetic-impossibility
check post-1.48.1 and found 14.3% → 3.83% (496/12,939 rows) — improved, but
short of its stated PASS bar (~0%).

## Diagnosis (don't assume the detector is wrong before checking)
Split the 496 live: itrader's OWN detector (`csv_accept.py`, this cycle's
version) only flags a row when `range_pos`/`price`/`day_low`/`day_high` are
actually POPULATED and inconsistent — it does NOT count legitimately-blank
rows as corrupt (an earlier, cruder version of itrader's own script did; the
current one doesn't). So the 496 were real: ~230 rows with `price` outside a
POPULATED `[day_low, day_high]`, ~477 `range_pos` violations (overlapping).

Live re-pull of 4 named symbols (IYK/AVD/BRKU/OPTH) nailed the mechanism:
IYK's CSV row (written earlier) had `day_high=74.87` against `price=75.01`;
a FRESH pull minutes later showed the vendor's own `dailyBar.h` had caught up
to 75.03. This is NOT a session mismatch (bar_is_today was already correctly
True) — it's the vendor's own same-session `dailyBar` aggregate lagging the
very latest tick by seconds, worst on thin/leveraged/preferred names (all 8
named-bad symbols: OPTH, BFH.PRA, AIFF, EWV, BBLG, IYK, BRKU, AVD — thin or
leveraged/preferred).

## Fix (`snapshot_type_to_csv`, right after `price` is finalized)
```python
if bar_is_today:
    price_f = float(price)
    if day_h is not None and price_f > day_h:
        day_h = price_f
    if day_l is not None and price_f < day_l:
        day_l = price_f
```
Not a guess — a print that genuinely happened today (bar_is_today already
established this) means today's true high is AT LEAST that print and true
low AT MOST that print. `day_low <= price <= day_high` and `range_pos` in
`[0,1]` hold by construction afterward. Only touches the `bar_is_today`
branch — the not-yet-rolled branch stays correctly blank (1.48.1's job).

## Verified
Stubbed IYK-shaped fixture (bar rolled today, `dailyBar.h` below live price)
→ widens correctly, `range_pos == 1.0`. Live re-check against the real full
universe (12,939 rows) using itrader's own exact Check-1 script: **0.00%
corrupt**, down from 3.83%. All 8 named-bad symbols individually clean.

## What this does NOT change
itrader's own permanent `get_snapshot`-before-order verification gate and
Check-1 detector stay exactly as designed — this closes a specific residual,
it doesn't argue the CSV never needs independent verification before an
order (itrader's own conclusion, correct, unaffected by this fix).

## Deploy
Source-only edit — owner-run build+install+restart to reach live agents
(see [[deploys-are-owner-run]]).
