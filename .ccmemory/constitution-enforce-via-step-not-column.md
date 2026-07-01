---
name: constitution-enforce-via-step-not-column
description: VERIFIED 2026-07-01: to bind the local model, enforcement must be its OWN step/sub-step. A column/field added to an already-established artifact gets…
metadata:
  type: project
tags: [constitution, prompt-engineering, forced-artifact, local-model, verified]
---

## The rule

To make the local trader model reliably DO something, it must be its **own
numbered step or lettered sub-step** (a discrete "you MUST" obligation). Do NOT
bury the requirement as a **column/field inside an artifact the model already
produces** — it treats a step as mandatory but a detail inside a step's output as
optional, and fills those details from habit. Extends [[constitution-steps-not-prose]]
(steps > prose) with a finer boundary: **step-level = obeyed; detail-inside-an-
established-artifact = ignored.**

## What steps CAN and CANNOT enforce

- **CAN enforce discrete CHECKS + ACTIONS** — a verifiable binary with a forced
  corrective: "is each winner's stop above entry? if NO and it's up, raise it and
  confirm the new order id." The model can evaluate and act on this.
- **CANNOT enforce SKILL** — "pick the right higher-low with room." That's
  judgment, not a checkbox; no step-structure fixes it (the hair-trigger / bad-
  structure-level problem is ceiling-bound regardless of how it's framed).

## The verified evidence (why we know)

1.23.0 added a `locks a gain?` COLUMN to step 9(e)'s trail table (to force the
profit-lock check). Timeline, all confirmed:
- 15:33:58 UTC — `make const` wrote 1.23.0 to run-dir CLAUDE.md
- 15:33:59 UTC — aitrader service restarted (fresh session loads 1.23.0)
- 15:47:46 UTC — journal entry 125, 14 min into the 1.23.0 session
Entry 125 reproduced the OLD 5-column trail table with NO `locks a gain?` column.
So the model LOADED the new spec and ignored the added column, templating off its
own prior 5-column journal entries (its own outputs out-vote the instruction —
same mechanism as [[constitution-no-malformed-tool-examples]], turned inward).

## Corollary — clean-new vs modification

A brand-new step/artifact introduced clean STICKS (1.21.0's trail table and the
step-5 (a)/(b)/(c) restructure were adopted immediately). MODIFYING an already-
established artifact's format does NOT (the model's accumulated prior examples
dominate). So iterating on an existing table's columns is exactly the edit that
won't take — add a NEW step/sub-step instead.

## How to apply

- Profit-lock fix: REVERT the 9(e) `locks a gain?` column, add a discrete **9(f)**
  sub-step (verify each winner's stop > entry; if not and up, raise + confirm id).
- General: any new enforcement → its own numbered step/sub-step, never a field
  grafted onto an existing artifact. Related: [[constitution-trail-forced-table-9e]],
  [[premarket-mark-vs-snapshot-and-stop-arming]].
