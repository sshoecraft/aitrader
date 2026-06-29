---
name: journal-malformed-toolcall-kind-corruption
description: Malformed journal_write spilled body/symbol+}}} flood into the kind field (31KB on entry 92, broke UI badge); repaired in place; real fix = vLLM pars…
metadata:
  type: project
---

## What happened (2026-06-29)
The dashboard JournalFeed couldn't render journal entry id 92 — a flood of `}}}`
ran off the screen. Root cause: a malformed `journal_write` tool call. The agent
wrote a clean reconcile note (the **body was fine**), but the `symbol` arg + a
runaway-`}` flood spilled into the **`kind`** field — a 31KB `kind` of literal
`}` chars, `symbol` left NULL. `kind` renders as a short UI badge, so it blew out
the layout and bloated `journal_read` to 66KB. Same bug in milder form on
entries 40–43, 57 (`entry**, symbol: "GIS"`, `note\``, `"reconcile"`). This is
the weak-model malformed-tool-call mode — see
[[constitution-no-malformed-tool-examples]].

## Fix
- **Root cause fixed at the vLLM tool-parser layer** (separate session) — the
  correct layer. Lineage: [[vllm-gemma4-quotefix-patch]]. We deliberately did
  NOT add MCP-side input sanitization to `journal_write`: fix the cause, not the
  symptom. (A `sanitize_tag` clamp was briefly added then reverted once the
  parser fix was confirmed — don't re-add it.)
- **Live data repaired IN PLACE** (UPDATE, never rm+recreate — see
  [[live-journal-db-edit-in-place]]): entries 40,41,42,43,57,92 — `kind`
  normalized to its real tag, `symbol` recovered where unambiguous (40→GIS,
  92→PORTFOLIO), stray wrapping quote stripped from 42. Originals saved to
  `journal-row92.backup` + `journal-malformed-kinds.backup` in
  `~/.local/state/aitrader/`.

## How to apply
If a malformed/huge `kind` badge shows up again, the model/parser regressed —
fix it at the model layer, then repair the DB rows in place. Quick triage:
`SELECT DISTINCT kind, length(kind) FROM journal` — sane kinds are short tags
(entry/note/reconcile/thesis/trade_plan). Deploy path for journal-MCP code (if
ever needed) is `make full` (build+install+restart); the live MCP runs the
installed package, not `/src` (see [[api-service-deploy-path]]).
