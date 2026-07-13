---
name: journal-write-step6-never-named-tool
description: 1.49.3 VERIFIED LIVE: step 6 now names journal_write explicitly; post-deploy cycle called it (confirmed in transcript), journal.db entry #340 landed.
metadata:
  type: project
tags: [constitution, journal, gemma, steps-not-prose, resume, ccloop, verified]
---

## What happened (2026-07-13)

Owner ran `make world` on atrader. The service restarted while the prior
session (6) was mid-`wait_seconds` (it had already done everything right:
closed positions, wrote position records, wrote journal entry #339 at
17:36:02Z, then went to sleep). `make world` restarted the service at
17:39:38Z, ~3.5 min later, killing that blocking wait. ccloop's resume saw
no clean final turn and seeded session 7 with "previous session may have
crashed" framing (`resume.md`).

Session 7 woke, saw nothing had changed (still flat, same AAVE stop-out,
same CPI watch), and re-ran essentially the same cycle — rendered
RECONCILE/SURVEY/GATE/FORWARD-EXPECTATIONS faithfully as chat text — but
never called `journal_write`. Confirmed by scanning the raw transcript
(`.../5574dcf7-....jsonl`) for every `tool_use` block: that session called
`journal_read`×3 and `position_record_list`×1, and zero `journal_write` —
not an error, never attempted. `journal.db`'s last row stayed at id 339
(pre-restart) through the entire session-7 cycle.

No information was actually lost — session 7 was a redundant re-derivation
of session 6's already-journaled state — but the gap was real and would
have bitten on a cycle that *did* contain a new decision.

## Root cause

`prompts/constitution.md` step 6 (JOURNAL) was the only step in THE LOOP
whose forced artifact is a tool call but which never named that tool.
Sibling steps that need a call say so explicitly in backticks (2A: "submit
... via `prospect_ack`"; 2C: "submit ... via `insight_hypothesize`"). Step 6
named only `position_record_upsert` (secondary) and otherwise said "Write
what you did and why" — text-rendering language, not a persistence
directive. The tool itself was already fine: `journal_write`
(`aitrader/mcp/journal_server.py:34`) raises `ValueError` on an empty body
rather than silently no-op'ing — nothing wrong on the tool side, purely a
missing-name gap in the prompt.

Same failure family as [[constitution-steps-not-prose]] and
[[constitution-enforce-via-step-not-column]]: the local model (gemma)
reliably complies with a prose-described chat artifact and just as reliably
drops a call that isn't named as its own forced step — especially, it now
appears, on a resumed/redundant cycle where nothing new happened.

## Fix (1.49.3)

Backed up to `prompts/constitution.md.backup-20260713-prejournalfix` per
[[constitution-edit-protocol]]; `ask_gpt` review obtained (flagged and fixed
three secondary risks in the first draft: ambiguous `kind`, a premature call
before the text was finished, and "lands" wording that could read as license
to retry indefinitely). Landed step 6 addition: "After assembling that
complete text, call `journal_write(kind, body[, symbol, tags])` —
`kind=\"reconcile\"` for this per-cycle entry, the full text above as
`body` — exactly once," plus "Rendering the text in your response does not
persist it: step 6 is NOT DONE until `journal_write` succeeds, no matter how
complete the written text looked."

## VERIFIED LIVE (same day)

Owner deployed (`make const`/`make world`) — deployed run-dir `CLAUDE.md`
diffed identical to source post-deploy. The very next atrader session
(transcript `f7d840b0-e198-425e-90a2-c783f9c57925.jsonl`) called
`journal_write` exactly once; its `body` matches `journal.db` entry #340
(`ts 2026-07-13T18:16:24Z`, `kind=reconcile`, `symbol=PORTFOLIO`) verbatim.
Confirmed by scanning the transcript's raw `tool_use` blocks, not just by
timestamp correlation. Fix holds — closed, no further action pending.
