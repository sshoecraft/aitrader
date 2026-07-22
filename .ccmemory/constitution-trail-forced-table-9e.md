---
name: constitution-trail-forced-table-9e
description: SUPERSEDED 1.52.0 by constitution-exit-two-sided-thesis: 1.21.0 step 9(e) trail-winners forced table; trail-only-exit framing now replaced by TRIM/EX…
metadata:
  type: project
tags: [constitution, stops, trail, forced-artifact, verified, superseded]
---

> **SUPERSEDED 2026-07-22 (1.52.0) → [[constitution-exit-two-sided-thesis]].** The
> "green → the trail is how a winner is SOLD / a green stop-out is THE success /
> HELD only if structure ≤ stop" doctrine below was ruled boundary drift and
> REPLACED: REVIEW verdicts now include `TRIM` + discretionary `EXIT`, positions
> carry an authored `WORTH:` objective + a per-cycle payoff read, and being green
> forces NEITHER trail nor trim. The forced-artifact binding lesson here still
> holds. Kept for provenance.

## What

Step 9(e) (TRAIL WINNERS) in `prompts/constitution.md` was rewritten from an
emphatic PROSE paragraph into a FORCED TABLE — one row per position green since
entry: `symbol | entry→current (%grn) | structure price read off the bars | old
stop → new stop | action (modify_order id or HELD+reason)`. `HELD` is legal only
when the structure price is ≤ current stop. Step 10 (JOURNAL) now requires the
STOPS section to reproduce that table; a list of static stop levels = 9(e)
skipped. Deployed via `make const` → run-dir CLAUDE.md + agent restart.

## Why it was needed

For a week the agent left NVDA/TSLA/PM winners on their entry-era stops
(188/400/178.50) while journaling "all holdings justified for hold" every cycle —
zero structure analysis. Asked why, it recited 9(e)'s own "trail under structure,
not price / avoid hair-triggers" language fluently but had never actually pulled
bars or trailed. Classic weak-model failure: recite the rule, do nothing. Prose
didn't bind it; per [[constitution-steps-not-prose]] this model obeys forced
artifacts. No WRONG/malformed examples used ([[constitution-no-malformed-tool-examples]]).

## VERIFIED live 2026-07-01

Deploy 12:48 UTC → first cycle 12:54 UTC (journal id 117) emitted the TRAIL TABLE
and actually ratcheted: TSLA 400→416, NVDA 188→195, PM 178.50→179.50. The exact
behavior it refused for a week. Primary goal (make it ACT + emit artifact) MET.

## Known residual weakness (the table bounds ACTION, not QUALITY)

1. **Structure cell can still be gamed — detectably.** NVDA's row cited structure
   price 196.46 = its CURRENT price. A higher-low must be BELOW current; it filled
   the cell to satisfy the format. Now visible in the journal (cross-check the
   cited price against real bars), but not prevented.
2. **Over-corrected into hair-triggers.** All three new stops sat ~0.6–0.75% under
   current — the very "normal wiggle wicks you out" 9(e) warns against.

Candidate follow-up (not yet done): require structure price STRICTLY below current
(kills the NVDA-style fill) + a minimum stop-to-current gap (kills hair-triggers).
Separate unaddressed issue: over-concentration (5 correlated staples) + no
thesis-review-or-exit on losers (WMT/COST/PG) — 9(e) only covers winners. Related:
[[agent-must-be-guided-not-unguided]], [[constitution-stops-and-tool-mechanics]].
