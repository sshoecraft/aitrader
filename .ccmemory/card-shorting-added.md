---
name: card-shorting-added
description: 1.47.0: new neutral card-shorting.md (execution mechanics only, no selection/sizing view); first draft over-encouraged shorting per ask_gpt review, r…
metadata:
  type: project
tags: [ccmemory, cards, shorting, 1.47.0]
---

## Why this card exists
Following `ibkr-long-only-guard-removed`: shorting was silently blocked for
weeks by inherited code, and its rediscovery tonight happened via a leading
owner question that visibly biased the running agent's behavior (see
`futures-zeros-and-mcp-bypass` and the scrubbing work — journal entries,
session transcripts, and two memory notes were removed, NOT to disable
shorting, only to remove the biasing narrative). The owner wanted the
underlying FACT (shorting works, here's the risk shape) captured cleanly,
separate from that narrative — same category as the existing `card-crypto`/
`card-forex`/`card-futures`/`card-options`/`card-leveraged-etp` asset cards.

## Draft 1 → ask_gpt review → draft 2 (what changed and why)
First draft read too much like encouragement despite trying to be neutral:
- "not special, exotic, or riskier-by-policy" — persuasive/corrective framing, not a fact statement.
- "mirror of a long, sized and stopped the same way" — inaccurate (real asymmetries: borrow, dividends owed, gap-through-stop, no price ceiling) and strayed into sizing/stop POLICY, which isn't this card's job.
- "This isn't a reason to avoid shorting... stop discipline matters MORE" — explicit prescription, not fact.
- The event-gap/squeeze "shape test" paragraph was setup/selection advice, not mechanics — removed (that judgment already lives in the agent's own reasoning + the constitution, not a card).
- "same risk/reward arithmetic as a long" — false for stocks specifically (bounded ~100% gain/capped loss on a cash long vs. uncapped loss on a short).
- Crypto "CANNOT be shorted" — narrowed to "via this account's configured Paxos/ZeroHash spot route" (a fact about the configured execution path, not a blanket claim about crypto shorting anywhere).
- Missing facts added: borrow availability/rate can change, recall/margin-change can force a cover, short seller owes dividends, a resting stop does not cap loss (gaps/halts/squeezes fill through it), paper accounts don't model these frictions realistically.
- Closing line adopted near-verbatim from the review: "This card records execution mechanics and short-specific exposures only. It does not alter candidate selection, directional preference, sizing, or qualification standards, which are defined elsewhere."

## Where it lives
- Source (canonical, reaches every instance via `make const`):
  `prompts/ccmemory-seed/card-shorting.md`.
- Landed directly into itrader's LIVE `.ccmemory` too (bypassing the need
  for a restart) — `MEMORY.md` index updated, search index (`index.db`)
  cleared so it's discoverable immediately.
- atrader (the other instance) gets it on its next `make const` — not done
  automatically as part of this change; that's the owner's deploy step per
  `deploys-are-owner-run`.

## Standing rule this triggered
`constitution-edit-protocol` (ccmemory) was broadened same night to cover
ANY curated card under `prompts/ccmemory-seed/*.md`, not just
`prompts/constitution.md` — backup-before-editing (existing files) +
higher-order-model review (`ask_gpt`/`ask_fable`) before landing, for
exactly the reason this card's own draft-1→draft-2 history demonstrates: a
card is read with constitution-level authority ("hard-won per-asset
evidence... consult with judgment"), so sloppy framing in a small file
biases behavior just as much as a constitution edit would.

Related: `ibkr-long-only-guard-removed`, `futures-zeros-and-mcp-bypass`,
`constitution-edit-protocol`, `constitution-minimal-experiment`.
