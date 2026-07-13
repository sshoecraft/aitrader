---
name: rank-instruments-lenses-and-forced-floor
description: 1.49.0: atrader (gemma) only ever makes ONE floorless rank_instruments call/cycle, never a floored follow-up (was optional prose); added lenses= para…
metadata:
  type: project
tags: [rank-instruments, constitution, gemma, atrader, itrader, 1.49.0, survey]
---

# rank_instruments gets `lenses`; constitution makes the floored pass mandatory (1.49.0, 2026-07-13)

## The diagnosis (owner-directed: "why didn't atrader even EVAL a stock buy?")
Live transcript inspection: atrader's cycle made exactly 2 `rank_instruments`
calls total — one per open type (stock, crypto), BOTH `min_price=0,
min_volume=0, n=3` (floorless). Nothing else. Constitution step 3(b) only
FORCES the floorless call; applying a floor after was prose: "Floors are a
lens you may apply AFTER..." — optional, and atrader never exercises it.

On a ~13k-name stock tape, floorless-top-3-by-%-move is nearly always penny/
warrant noise (verified same cycle: EVLVW +172.7% on $4k traded, QTEXW
+81.4% on $1.6k, MVSTW +75% on **$4** total) — correctly PASSed as junk, and
then the cycle never looks at stocks again.

## Why itrader (opus) doesn't have this problem
Checked 6+ of itrader's own transcripts: it NEVER calls `rank_instruments`.
Every cycle it writes its own sandboxed pandas script against the raw CSV
with its own ad hoc floor + multiple lenses (biggest %up/down, most dollars
traded `day_notional`, highest `rel_vol`) — plus a self-built corruption
filter (independently defending against the bug in
[[snapshot-csv-stale-dailybar-rollover-fix]] before the fix even shipped).
This is EXACTLY what `rank_instruments` (see [[rank-instruments-tool]],
1.38.0) was built to give the WEAKER model a reliable tool-call equivalent
of — the constitution just never forced the second call for the model that
actually needs the tool to do it (opus doesn't need the tool at all).

## Fix — two parts

**Code** (`broker_server.py` 0.9.2→0.10.0): `rank_snapshot_csv`/
`rank_instruments` gain `lenses` — a comma-string (or list) of `"<by>"` or
`"<by>:<direction>"` (direction defaults `up`), e.g.
`lenses="pct_1d:up,pct_1d:down,day_notional:up,rel_vol:up"`. Runs the shared
filter pass (min_price/min_volume/fresh_only/exclude_held) ONCE, sorts per
lens. Deliberately a FLAT list of short scalar strings, not nested objects —
gemma's tool-call JSON breaks past short scalar args (same reason
rank_instruments exists over "rank it in the sandbox"). `lenses=None`
(default) is the ORIGINAL code path, untouched — multi-lens is new/additive,
zero risk to existing callers. Also tightened the `direction` docstring:
for an unsigned magnitude column (day_notional/day_volume/rel_vol),
up/down is a largest-first/smallest-first SORT, not a bullish/bearish
signal (`ask_gpt` review flagged this as a real misreading risk).

**Constitution** (`prompts/constitution.md`, backup+`ask_gpt` review per
[[constitution-edit-protocol]]): step 3(b)'s "may apply" → "come only AFTER
... (c) makes that MANDATORY." New step 3(c): one more required
`rank_instruments` call, the lenses string above, `n=3`, agent's own
min_price/min_volume with **at least one > 0** (both-0 satisfies "multi-lens"
in letter but not "floored") — its own forced sub-step + "= step 3 NOT DONE"
line, per [[constitution-enforce-via-step-not-column]] (a soft clause folded
into an existing step is what gemma skips; its own enforcement line is what
it follows). Old (c) VERDICT renumbered (d). Table/enforcement
paragraph/step-4 RANK+GATE cross-references extended to the floored-cut
column so surfaced names actually flow into the decision, not just display.

`ask_gpt` review caught and fixed BEFORE landing: the direct (b)/(c)
contradiction (most important catch), the both-floors-0 loophole, an
underspecified required-artifact list, unbounded `n` risk (fixed at 3), and
one sentence that read as advocacy ("surfaces liquid movers...") rather than
neutral mechanics — rewritten as "supplements, does not replace."

## Verified
Stubbed regression: `lenses=None` reproduces the exact pre-1.49.0 shape;
multi-lens applies the shared floor once, correct per-lens movers/no_data,
cross-checked against an equivalent single-lens call. Live smoke test
against the REAL current 12,939-row universe: `day_notional:up` →
MU/QQQ/SNDK/NVDA/SPY — matching, almost verbatim, itrader's own hand-written
"biggest movers by notional" cut from the same morning's journal.

## Deploy
Code: owner-run build+install+restart. Constitution: owner-run `make const`
+ restart (see [[deploys-are-owner-run]]). Neither is live yet as of this
memory.
