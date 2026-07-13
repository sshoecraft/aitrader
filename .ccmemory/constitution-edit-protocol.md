---
name: constitution-edit-protocol
description: Standing rule: edits to prompts/constitution.md OR any curated card (prompts/ccmemory-seed/*.md) need a backup + review by a higher-order model (GPT/…
metadata:
  type: feedback
tags: [constitution, cards, workflow, standing-rule, ask_gpt, ask_fable, backup]
---

Owner directive (2026-07-12, broadened 2026-07-12 to cover cards too): every
time `prompts/constitution.md` OR any curated card under
`prompts/ccmemory-seed/*.md` is edited or created, two steps are MANDATORY,
not optional judgment calls:

1. **Backup first (constitution.md only — cards are new/small files, a
   backup is moot for a brand-new card; still back up before EDITING an
   existing card).** Copy the current file to
   `prompts/constitution.md.backup-<YYYYMMDD>` (append a short suffix like
   `-prenews` if a second backup is needed same day — see the existing
   backup file naming precedent) BEFORE making any change.
2. **Get review from a higher-order model — `mcp__ask_gpt__query` or
   `mcp__ask_fable__query`.** Send it the proposed text (draft, placement,
   rationale) and any known fragility of the target doc (constitution.md:
   a persona/voice rewrite once broke the trading agent and had to be
   reverted same day — see ccmemory `constitution-persona-reverted`; a
   card: whether the framing reads as neutral fact or as an implicit nudge
   toward a behavior — see `card-shorting`'s review history, where a first
   draft was flagged as over-encouraging shorting and had to be rewritten
   as pure mechanics). Ask specifically: does this read as neutral
   fact/mechanics, or does repeated phrasing function as a behavioral nudge
   in either direction? Incorporate the feedback before finalizing.

Why cards are now in scope, not just the constitution: a card is read by
the agent with the SAME authority as constitution text — "your card-*
notes are this account's hard-won per-asset evidence... consult with
judgment" — so a card that reads as encouragement rather than fact biases
behavior exactly like a constitution edit would, just via a smaller file
that's easier to add without thinking it needs the same scrutiny. It does.

This applies to EVERY constitution.md edit AND every new/edited card going
forward — do not skip either step because a change "looks small." Deploy
(`make const`) remains owner-run regardless (see `deploys-are-owner-run`);
this rule is about the edit/preparation step, not deployment.
