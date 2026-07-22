---
name: journal-local-clock-stale-off-by-one-cycle
description: 1.51.2: atrader reconcile Local: line went ~2h stale (off-by-one now() copy across step-6 gap, NOT tool/relay); journal_write 0.2.2 normalizes vs row…
metadata:
  type: project
tags: [journal, clock, gemma, local-model, journal_write, reconcile, root-cause]
---

# Stale reconcile `Local:` clock — off-by-one-cycle (1.51.2)

## Symptom
atrader (gemma) journal entries #375 & #376 had a body `RECONCILE > Local:` line
~2h06m stale — reporting the PREVIOUS cycle's clock. Row `ts` (server-stamped) was
correct. Owner noticed reading the latest entry.

## Forensics (ruled OUT the obvious)
Transcript (`~atrader/.claude/projects/*aitrader-run*/*.jsonl`, parse tool_use→tool_result):
- The `now` tool WAS called every cycle and returned correct wall-clock every time
  (verified live: `now()` == host `date` to the second). Tool is clean.
- Stale cycles 375/376 + fresh 370-374 + fresh 377+ were ALL in ONE continuous
  session (transcript `68277367`). NO relay, NO compaction (atrader runs
  `DISABLE_COMPACT=1`). So NOT a fresh-session/summary artifact. (My initial relay
  theory was WRONG — evidence overrode it.)
- Discriminator: #376 wrote the previous cycle's *now() result* (10:56), NOT the
  previous journal *body* text (08:53) → model selects a now() result from context,
  just the wrong (previous) one. Rules out template-copy AND infra.

## Root cause
Step 6 (journal_write) is ~3 min + several big markdown tables after the step-1
`now()`. Context holds ~6 near-identical prior now() results; the local model
reaches back and grabs the second-most-recent (near-duplicate retrieval /
off-by-one-cycle slip). It's model-side, not tool/infra. Confirmed independently by
GPT-5.6 + Fable-5; both ranked "remove the hand-copy from the data path" as the fix.
Tool choice (`now` vs `date`) is IRRELEVANT — the value was always hand-copied
across the gap. (grep now=17/date=0 only proved the constitution mandates `now`.)

## Fix (journal_server.py 0.2.2, infra-only, NO constitution change)
`normalize_reconcile_clock(body, ts)` at the single write choke point: if the body's
`Local: … / HH:MM UTC` stated UTC drifts from the authoritative row `ts` by
> `CLOCK_DRIFT_TOLERANCE_MIN` (10 min), rewrite the line to the canonical
ts-derived value + tag `[clock auto-corrected — body said HH:MM UTC]` (never
silent). Legit ~2-3 min step1→step6 gap is below tolerance → fresh entries
untouched (keeps reconcile-time, not write-time, meaning). Stated time resolved vs
row date ±1 day so near-midnight isn't mistaken for ~24h drift. NEVER raises
(failure → body unchanged; can't fail a write). `journal_write` also now returns
`local`+`et`. Dashboard was never wrong — `JournalFeed.tsx` already renders time
from `ts`; stale value lived only in body prose.

Verified (Phase 2, as atrader vs live journal.db #369-383): only 375/376 corrected
to their row ts; all fresh untouched; synthetic edges pass. Deploy is owner-run
(make build+install + journal-MCP restart; applies on next agent session/relay).

## Open follow-up (Fable's sibling-bug warning)
Same hand-copy-across-table-heavy-gap mechanism threatens ANY transcribed value —
most dangerously prices / stop levels in theses. Audit those fields.
