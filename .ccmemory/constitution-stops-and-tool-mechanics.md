---
name: constitution-stops-and-tool-mechanics
description: Constitution stop history: a mandatory-stop rule was reverted 2026-06-18 as bias, then a guided-regime PROTECT step (existence not level) was ADDED 2…
metadata:
  type: project
---

Timeline of how `prompts/constitution.md` handles protective stops. **Read the
whole arc before touching this — the 2026-06-18 revert is NOT the final word.**

## 2026-06-18 — mandatory stop rule ADDED then REVERTED same day
After the agent botched `place_stop_order` calls and left positions naked, a
"Risk Protection Requirement" was added: a resting stop required on every
position, and the EXISTENCE of a stop "overrides S" (could justify a hold). It
was reverted that day as **injecting a conservative bias the agent didn't reason
to** — same category as the `check_risk_limits` engine the brief rejects, moved
from code into the prompt. Two things made it bias: (1) it assumed the agent
would otherwise reason its way to exits, and (2) it let a stop's existence be a
reason to HOLD.

## 2026-06-24 — PROTECT step (1.15.0) ADDED — and this is COMPATIBLE with the revert, not a reversal of it
Why the objection no longer governs: the zero-bias premise is dead
([[agent-must-be-guided-not-unguided]]), and the live model is a weak local one
(gemma) that ignores prose and only follows numbered steps
([[constitution-steps-not-prose]]). Live failure that forced it: a 1.83x book
held overnight with 2 of 9 stops, the model REPORTING "every position protected"
while citing a 2-order list (confabulation). Account owner explicitly chose the
step over boundary purity ("better that than losing all my money").

What keeps it on the legal side of the line — the distinction the 2026-06-18
rule blurred:
- **Mandate the EXISTENCE of a stop = OK** (mechanical lifecycle invariant).
- **Mandate the LEVEL/distance = NOT OK** — that's `compute_order_prices` /
  `check_risk_limits`. The agent still chooses `stop_price` (structural anchor,
  never a fixed %).
- A stop is STILL never a reason to hold — the step ends by reaffirming step 5
  (a name that fails step 5 is a SELL, stop or no stop). This is the exact thing
  the 2026-06-18 version got wrong and why it was bias.

Step 9 PROTECT, every cycle, every position: (a) LIST positions, (b) MATCH each
to a live stop in get_orders or mark NONE, (c) PLACE a stop for each NONE via
`place_stop_order(..., tif="gtc")`, (d) VERIFY by re-reading get_orders for the
order id. Forced LIST+VERIFY kills the confabulation; `tif="gtc"` (day stops die
at the close) and stop-MARKET not stop-limit (limit rests unfilled in a gap) are
baked in because the model's own stops had both holes. JOURNAL (now step 10)
records the coverage list. Renumbered: PROTECT 9, JOURNAL 10, WAKE 11.

**Bottom line for a future editor:** do NOT re-add a stop *level/sizing* rule or
let a stop justify a hold — those are the bias. An explicit *existence + verify*
step is intended and load-bearing; do not strip it as "the reverted mandate."

## KEPT from 2026-06-18 (mechanics, not policy — no boundary issue)
- **Pacing** — end every cycle in a `wait_*`; never loop back-to-back.
- **Tool Call Mechanics** — raw structured field args, side exactly buy|sell,
  bare numbers, exact order/position signatures, verify-it-landed. NEVER add a
  malformed/"WRONG" example ([[constitution-no-malformed-tool-examples]]).

Deploy constitution edits to a node via `make run-dir` (or `make install`); each
node serves its own run-dir CLAUDE.md, loaded on next session start.
