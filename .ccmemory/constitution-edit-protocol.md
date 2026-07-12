---
name: constitution-edit-protocol
description: Standing rule: any edit to prompts/constitution.md must (1) take a dated backup first and (2) get ask_gpt's review of the edit before/while landing i…
metadata:
  type: feedback
tags: [constitution, workflow, standing-rule, ask_gpt, backup]
---

Owner directive (2026-07-12): every time `prompts/constitution.md` is edited,
two steps are MANDATORY, not optional judgment calls:

1. **Backup first.** Copy the current file to
   `prompts/constitution.md.backup-<YYYYMMDD>` (append a short suffix like
   `-prenews` if a second backup is needed same day — see the existing
   backup file naming precedent) BEFORE making any change.
2. **Call `mcp__ask_gpt__query` for edit-suggestions/review.** Send it the
   proposed change (draft text, placement, rationale) and this document's
   known fragility (a persona/voice rewrite once broke the trading agent
   and had to be reverted same day — see ccmemory
   `constitution-persona-reverted`), and ask for the optimal way to land the
   edit so it actually binds (placement, labeling/numbering scheme,
   precedence vs existing fuses, wording that won't get treated as
   optional). Incorporate its feedback before finalizing, the way the
   ccprospect 2A/5A and news-check 2B integrations did.

This applies to EVERY constitution.md edit going forward, not just
first-time integrations — do not skip either step because a change "looks
small." Deploy (`make const`) remains owner-run regardless (see
`deploys-are-owner-run`); this rule is about the edit/preparation step, not
deployment.
