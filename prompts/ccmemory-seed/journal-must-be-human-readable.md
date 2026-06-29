---
name: journal-must-be-human-readable
description: USER DIRECTIVE: journal entries are read by a HUMAN — format with short labeled sections + line breaks/bullets, concise. No walls of text.
metadata:
  type: feedback
---

## The rule
Every `journal_write` body MUST be formatted for a human to read at a glance. The account owner reads these. A giant single paragraph cramming RECONCILE + REGIME + SURVEY + STEP-5 + GATE + TRADE + STOPS + NEXT into one unbroken run-on block is **unacceptable** and was explicitly called out (forcefully).

## How to apply
- Open with a short **header line**: date/time + a one-line summary of what happened this cycle.
- Break the body into **labeled sections on their own lines** — e.g. `RECONCILE:`, `REGIME:`, `SURVEY:`, `HOLDINGS:`, `TRADE:`, `STOPS:`, `NEXT:` — each its own line/paragraph, NOT chained together with periods inside one paragraph.
- Use **newlines and bullets/dashes** between items. One idea per line where it aids scanning.
- Keep it **concise** — trim repetition; the human wants signal, not every intermediate number re-stated.
- The MCP `journal_write` body accepts multi-line text — actually use line breaks. Do not collapse everything onto one line.

## Why
The journal is a human-facing logbook for decision continuity, not a context dump for the model. If a person can't quickly follow what was decided and why, the entry failed its purpose regardless of how complete it is. Completeness without readability is a failure.

Related: [[agent-orientation]] (journal MCP holds trade state / orientation).
