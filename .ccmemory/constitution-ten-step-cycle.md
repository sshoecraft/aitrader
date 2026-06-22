---
name: constitution-ten-step-cycle
description: 1.4.1: constitution = AT SESSION START (memory+journal, once) + THE CYCLE (8 steps reconcile→wakeup, every wakeup); wakeup is a step rule ≤1h, NOT an…
metadata:
  type: project
---

## Structure (prompts/constitution.md, 1.4.1)
Three parts: (1) the **S-objective** definition + TransactionCosts table (the score to maximize),
(2) **AT SESSION START** + **THE CYCLE**, (3) **Tool Call Mechanics**.

**AT SESSION START — once per fresh/relayed session (recover state):**
- check memory · check journal (positions-of-record, theses, planned exits).
- Mid-session (already have context, just woke) → skip straight to the cycle.

**THE CYCLE — every wakeup, in order, then sleep and repeat from step 1:**
1 reconcile (broker = truth; every wakeup, fills/orders move while sleeping) · 2 what's-open
(get_available_types) · 3 news (web search) · 4 cover EVERY open class incl. crypto — coverage
table, LIVE universe via get_tradeable_assets NOT training tickers · 5 score+pick by S (100%,
cash counts) · 6 act (client tag = idempotent, verify) · 7 journal (position_record_upsert,
**ET times**) · 8 pick wakeup **15m/30m/1h, NEVER >1h**, sleep via wait_seconds.

## Why this shape (don't undo it)
- Replaced ~11 scattered MANDATORY blocks (Decision/Holding/Universe/Coverage/Pacing/News/…) the
  weak local model couldn't follow (it skipped crypto+news, over-slept 41.5h). One ordered
  checklist is the format it actually follows. Do NOT re-scatter into blocks.
- memory/journal are SESSION-START, not per-cycle (1.4.1 fix) — they rarely change mid-session;
  reconcile-from-broker is the per-wakeup state refresh.
- Wakeup cadence is a MODEL RULE (cycle step 8, ≤1h), **NOT** an infra cap. A scheduler
  `max_wait_seconds` cap was built then **reverted at operator direction** — the model owns its
  wake time. Do NOT re-add a scheduler cap.
- Sleep only via scheduler wait_* — never CronCreate (parallel runs → lease/journal collisions →
  double-submit). Consider removing Cron* via --disallowedTools too.

## Writing style
Write for a DUMB model: short, blunt, imperative, concrete — not prose written for a smart
reader. See [[agent-must-be-guided-not-unguided]].
