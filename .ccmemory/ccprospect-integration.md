---
name: ccprospect-integration
description: ccprospect wired into prompts/constitution.md as STEP 2A (inbox) + STEP 5A (forward expectations); edit source, run make const to deploy
metadata:
  type: project
tags: [ccprospect, constitution, prompts]
---

## Binding surface

The constitution (`prompts/constitution.md`) is a BUILT artifact — `make const`
installs it to `$(RUN_DIR)/CLAUDE.md` (`~/.local/share/aitrader/run/CLAUDE.md`)
and restarts the `aitrader` systemd service. Never edit the run-dir copy
directly. Always edit `prompts/constitution.md` (the source) and let the
owner run `make const` to deploy — that restart is owner-run, not something
an integration/session does automatically.

## What was landed (2026-07-12)

Two new lettered loop steps, NOT a renumber of the existing flat 0-7
sequence (steps 2-7 are cross-referenced by number ~25 times throughout the
doc's prose — renumbering would have meant touching all of them, high risk
in a document already proven fragile to editing mistakes; see memory
`constitution-persona-reverted`):

- **STEP 2A · PROSPECTIVE INBOX** — right after step 2 (OPEN NOW), before
  step 3 (SURVEY). Calls `prospect_inbox()`, forces one disposition row per
  returned item, complete only at `pending_count: 0`.
- **STEP 5A · FORWARD EXPECTATIONS** — right after step 5 (PROTECT), before
  step 6 (JOURNAL). Up to 3 candidates drawn from step 3/4 material, one row
  each; a `NONE`/`NO_CONTRACT` sentinel row required if nothing qualifies
  (empty table is not legal, matching this doc's own idiom of never allowing
  a silently-skipped table).

Also added:
- A House-fuses bullet: existing safety fuses (naked position, liquidation
  cushion) outrank 2A/5A — never delay a stop/exit/naked-position fix to
  finish a prospective step.
- A `TOOL_ERROR` fail-open clause on 2A — a ccprospect outage never blocks
  RECONCILE/SURVEY/DECIDE/PROTECT.
- An explicit step-order sentence in the loop intro: `0,1,2,2A,3,4,5,5A,6,7`.
- Step 6 JOURNAL's artifact-reproduction list now also names the 2A and 5A
  tables.

Placement (2A after OPEN NOW rather than RECONCILE; 5A after PROTECT rather
than SURVEY) and the fail-open/precedence language were arrived at via
ask_gpt review of the original P1/P2 draft — GPT's case: positional labels
(`2A`/`5A`) read as ordinary loop members rather than a bolted-on subsystem,
and safety-fuse precedence must be explicit given this doc's strict
NOT-DONE gating could otherwise let a prospective-memory hiccup compete with
position-safety work.

Backup of the pre-edit file: `prompts/constitution.md.backup-20260712`.

`.ccprospect/integration.json` records shape=`custom`,
binding_file=`prompts/constitution.md`.

## Still to do (owner action, not automatic)

Run `make const` to actually deploy this into the live agent — an
already-running session keeps its old prompt until the next relay or a
`systemctl --user restart aitrader` (which `make const` does for you).
