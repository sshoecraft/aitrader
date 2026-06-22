---
name: alpaca-vs-ibkr-bars-start
description: Alpaca get_bars returns bars only chronologically FROM start (ZERO if start past last session); IBKR pads start backwards. Bit the 1D VTI chart.
metadata:
  type: project
---

## `get_bars(start=...)` semantics differ by broker — don't tune to one

**IBKR** `get_bars` (brokers/ibkr.py) converts `start` into a *duration* and pads
it (`days_diff = (today - start).days + 5`), so even `start = today-midnight`
returns recent sessions.

**Alpaca** `get_bars` (brokers/alpaca.py) returns bars **chronologically FROM
`start`** and gives **ZERO** if `start` is after the last available session bar
(weekend / holiday / pre-open). No backward padding.

This bit the dashboard 1D equity chart's **VTI benchmark overlay** (Header.tsx):
`periodStartISO('1D')` used `start = today-midnight`. On the IBKR node it worked;
on the Alpaca node it returned 0 bars on a non-trading day → empty `benchBars` →
no VTI line at all (neither Mode A nor Mode B can draw). Concretely surfaced Sun
2026-06-21 (Fri 06-19 = Juneteenth; last session Thu 06-18).

**Fix (1.7.3):** 1D's VTI `/bars` lookback widened to **7 days** (was midnight) so
the last session is always in the payload, broker-agnostic. `periodStartISO` feeds
ONLY the VTI bars fetch, never the equity series (that's server-side
`portfolio_since`), so widening is safe and doesn't change Mode A's today-only line.

Lesson: when something works on one broker's data path but not another, suspect
`get_bars`/history *windowing* semantics first. Related:
[[data-execution-broker-split]] [[equity-snapshots-order-by-ts]]
[[aitrader-ui-build-deploy]]
