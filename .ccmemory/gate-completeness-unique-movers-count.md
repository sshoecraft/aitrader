---
name: gate-completeness-unique-movers-count
description: 1.49.1: GATE was dropping ~80% of survey-surfaced names (prose-only completeness check); added unique_movers count so GATE row count is mechanically…
metadata:
  type: project
tags: [constitution, gate, rank-instruments, atrader, itrader, 1.49.1, unique_movers]
---

# GATE completeness gets a mechanical count (1.49.1, 2026-07-13)

## What happened right after 1.49.0 deployed
1.49.0 (mandatory floored/multi-lens survey pass) worked exactly as
designed: atrader's survey correctly surfaced a full candidate set (13
unique stock names via the new lenses, ~9 crypto). But GATE — which has
ALWAYS required one row per survey-surfaced name — wrote only 4 rows total.
itrader, same morning, similarly-sized candidate set, wrote 12 fully
individually-reasoned GATE rows, zero drops. See
[[rank-instruments-lenses-and-forced-floor]] for the 1.49.0 fix this
followed from.

## The precise diagnosis (owner pushed hard on "where EXACTLY")
GATE's *existence* is a forced step — atrader never skips writing a GATE
table. GATE's *completeness* was enforced only by prose: "a survey-surfaced
name with no row = step 4 NOT DONE," with nothing mechanical backing it —
no number the model could check its own row count against. Same shape gap
as step 3(b)'s original "may apply floors" soft clause, one level
downstream, never given the same treatment.

Owner's framing, worth keeping verbatim: *"since we have a step that tells
it to get the movers and we have a step that tells it to get the gate,
shouldn't the step that tells it to do the gate tell it that the number of
items in the gate should match the number of items in the movers?"* — that
is exactly the fix, and it's what both the owner and the independent
`ask_gpt` review converged on independently.

## Fix
- `_rank_multi_lens` (`broker_server.py` 0.10.0→0.10.1): multi-lens
  `rank_instruments` calls now return `unique_movers` — distinct symbol
  count across ALL requested lenses combined (a name topping two lenses
  counts once). Uses data already in hand, no new call.
- Constitution: step 3(c) — "Also record its `unique_movers` count." Step
  4(c) — "For each type, the number of GATE rows whose symbol is one of
  step 3(c)'s floored-cut names must equal that call's `unique_movers` — a
  row covering more than one symbol counts once, not per-symbol." Two
  sentences, no new sub-step, no new column.
- `ask_gpt` review (per [[constitution-edit-protocol]]) caught a real
  problem in the FIRST draft: it included a "name your collapses" escape
  hatch (same sector/driver/quote-currency → one row). Review: this
  directly undermines "one row for EVERY name" by giving the model an out
  to explain away exactly the drops being fixed, and risks teaching a false
  equivalence (same sector ≠ same candidate; a grouped row can't carry an
  individual action/threshold per name). Dropped entirely — landed version
  is a strict count match, no exceptions. Also scoped deliberately to the
  floored-cut set only (not floorless-top-3 or ACT candidates) per review:
  `unique_movers` proves floored-subset coverage, not whole-GATE
  completeness — an honest, narrower claim.

## Verified
Stubbed regression with a fixture DESIGNED for partial lens overlap (one
symbol topping 2 of 4 lenses at n=1): naive per-lens sum=4, true
`unique_movers`=3 — proves real dedup, not just echoing a count. Live smoke
test against the real universe: 12 slots (3×4 lenses) → `unique_movers`=10,
matching the exact symbols from the cycle that exposed the bug
(BMNU/VEEE/AGEN/AXTX/JLHL/KORU/MU/QQQ/SNDK/AMIX).

## This is a TEST, not a guaranteed fix — record the outcome either way
Two live hypotheses this distinguishes between:
1. **Forcing gap** (consistent with every prior finding in this project,
   see [[constitution-enforce-via-step-not-column]]): handing the model a
   hard, checkable number fixes completeness → GATE row count should track
   `unique_movers` next cycle.
2. **Capability ceiling**: atrader still drops rows even with the number
   sitting right there → real evidence the weak model can't reliably
   enumerate >~5-10 items regardless of forcing, needing a structurally
   different fix (`ask_gpt`'s suggestion: tool-side pre-populated GATE row
   stubs — the model fills blanks instead of generating the list from
   memory — a MECHANICAL fix, not more constitution text).
Check atrader's next cycle's journal GATE table against its own survey row
before concluding either way.

## Process note — the growth concern
Owner explicitly flagged: this doc grew ~51% in 2 days (21.5KB→32.7KB
pre-session), and the LAST time it was seen as "too big" (1.34.0 strip) the
strip was WRONG and reverted — the real cause that time was a narrow
candidate feed, not the prose, and the actual fix was ALSO a tool/data
change (whole-tape `get_all_snapshots`), not smaller prose. See
[[constitution-stripped-to-mechanics]]. Every addition since (1.39.0→1.49.1)
has been evidenced by a specific live failure, not speculative hardening —
but the trend is worth watching on its own terms regardless of whether any
single addition was justified. `ask_gpt`'s explicit recommendation: keep
mechanizing into tooling rather than continuing to grow constitution prose
one omission-mode at a time — prepopulated GATE skeletons / mechanical
output validation over more forced-count clauses, if this keeps recurring.

## Deploy
Owner-run (build+install + `make const` + restart) — see
[[deploys-are-owner-run]]. Not live as of this memory.
