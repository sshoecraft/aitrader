---
name: constitution-stops-and-tool-mechanics
description: Constitution stop history: mandatory-stop reverted 2026-06-18 as bias; PROTECT step ADDED 1.15.0 (existence not level); TRAIL-WINNERS pass ADDED 1.18…
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

## 2026-06-24 — PROTECT step (1.15.0) ADDED — COMPATIBLE with the revert, not a reversal
Why the objection no longer governs: the zero-bias premise is dead
([[agent-must-be-guided-not-unguided]]), and the live model is a weak local one
(gemma) that ignores prose and only follows numbered steps
([[constitution-steps-not-prose]]). Live failure that forced it: a 1.83x book
held overnight with 2 of 9 stops, the model REPORTING "every position protected"
while citing a 2-order list (confabulation). Account owner explicitly chose the
step over boundary purity ("better that than losing all my money").

THE LINE that keeps it legal (the distinction the 2026-06-18 rule blurred):
- **Mandate the EXISTENCE of a stop / the ACT of managing it = OK** (mechanical
  lifecycle invariant).
- **Mandate the LEVEL/distance/% = NOT OK** — that's `compute_order_prices` /
  `check_risk_limits`. The agent always chooses the price (structural anchor).
- A stop is STILL never a reason to HOLD — reaffirm step 5 (a name that fails
  step 5 is a SELL, stop or no stop). That's what 2026-06-18 got wrong.

Step 9 PROTECT, every cycle, every position: (a) LIST, (b) MATCH each to a live
stop in get_orders or mark NONE, (c) PLACE a stop for each NONE via
`place_stop_order(..., tif="gtc")`, (d) VERIFY by re-reading get_orders for the
order id. Forced LIST+VERIFY kills confabulation; `tif="gtc"` (day stops die at
close) and stop-MARKET not stop-limit (limit rests unfilled in a gap) baked in
because the model's own stops had both holes.

## 2026-06-25 — (e) TRAIL WINNERS ADDED to step 9 (1.18.0) — same existence-not-level logic
Cause: both live models held winners up several % still on their ENTRY-era stops
and had NEVER sold an instrument for a profit. Root cause = the exit model is
"stop + reversal exit" with no trailing instruction, and "cash is a FAILURE"
makes banking a winner feel like a rule violation. Opus self-diagnosed it ("I say
'trail the stop up' and then don't"); gemma claimed its static stops "lock in
profit as price rises" (FALSE), then admitted ZERO trailing stops, then backfilled
"avoid early shakeout."
- A fixed TAKE-PROFIT is NOT the fix — it IS the `compute_order_prices` injected
  logic §8 bans, and it caps the runner. A TRAILING stop banks the gain via the
  stop (the only way a winner is sold here) with no target.
- (e): for every position green since entry, RAISE the stop via `modify_order`
  (move existing — never stack a second) to just under the recent higher-low
  (long)/lower-high (short) or a fast MA. Mandates the ACT, not a number (agent
  picks the level → legal). Forced artifact: per winner `old → new → structure
  level`, so "too early to trail" is only defensible when price truly made no
  higher-low above the stop — closes gemma's perpetual-deferral dodge.
- Caveat baked in: trail UNDER STRUCTURE with room, NOT a hair-trigger (absorbs
  gemma's early-shakeout worry AND Opus's SMH bad-tick wick-out — don't swing to
  over-tightening).
- Closing line reframes a profitable stop-out as a SUCCESS (freed capital re-ranks
  at step 6), NOT the "idle cash" failure — counters the cash-is-failure bias.
- JOURNAL (step 10) records each winner's `old → new` trailed stop + structure.
Renumbered earlier (1.15.0): PROTECT 9, JOURNAL 10, WAKE 11.

**Bottom line for a future editor:** do NOT re-add a stop/TP *level/sizing/%* rule,
and do NOT let a stop justify a hold — those are the bias. The explicit
*existence + verify* stop step AND the *act-of-trailing* winners pass are intended
and load-bearing; do not strip them as "the reverted mandate."

## KEPT from 2026-06-18 (mechanics, not policy — no boundary issue)
- **Pacing** — end every cycle in a `wait_*`; never loop back-to-back.
- **Tool Call Mechanics** — raw structured field args, side exactly buy|sell, bare
  numbers, exact order/position signatures, verify-it-landed. NEVER add a
  malformed/"WRONG" example ([[constitution-no-malformed-tool-examples]]).

Deploy constitution edits to a node via `make run-dir` (or `make install`); each
node serves its own run-dir CLAUDE.md, loaded on next session start.
