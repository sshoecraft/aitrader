---
name: constitution-exit-two-sided-thesis
description: 1.52.0: REVIEW gains an upside half — WRONG-IF/WORTH entry intent, TRIM/EXIT verdicts, payoff read; ends trail-only winner-exit doctrine (GPT+Fable)
metadata:
  type: project
tags: [constitution, exit, trail, trim, review, boundary, take-profit, gpt-review, fable-review, not-deployed]
---

## What changed (1.52.0)

`prompts/constitution.md` step 4a REVIEW previously let a GREEN, un-falsified
position resolve to only `HOLD` or `TRAIL` — EXIT was gated on falsification and
there was NO `TRIM`/take-profit verdict. Combined with "the trail is how a winner
gets SOLD, a green stop-out is a SUCCESS" and the mandate's cash-as-failure line,
the agent had no representable way to bank a winner into strength.

Live trigger: itrader (opus) sat up ~$3,500 open on the MPC/VLO/PBF crack-spread
complex, gave back ~$1,100 to ~$2,373, never trimmed — only ratcheted stops
~0.6–1% under price. Owner asked why it "refused to take profit"; the agent was
correctly reciting its own constitution, not being stubborn.

## Classification — boundary DRIFT (GPT-5.6 + Fable-5, independent)

A trend-following exit STRATEGY baked into the prompt, foreclosing an exit
modality that is the agent's cognition (BRIEF §2/§8). The asymmetry that names it:
LOSERS get only existence-of-protection mandated + the agent picks the level (the
legal act-not-number line); WINNERS had the whole philosophy dictated and "take
profit" deleted from the decision surface. Deeper cause (Fable): every position
carried a downside INVALIDATION (the stop) but no upside OBJECTIVE, so a runner
re-won HOLD by construction — the only question ever asked was "thesis intact?"

## The fix (boundary-safe — agent authors every number; NO repo target/threshold/ATR rule)

- Entry records a TWO-SIDED intent via `position_record_upsert`: `WRONG-IF:`
  (invalidation) + `WORTH:` (objective — zone/condition/catalyst/explicit
  open-ended). Missing either tag = step 6 NOT DONE.
- REVIEW(4a) verdicts widen to `HOLD / TRIM n% / TRAIL → X / EXIT`, all legal in
  every state; EXIT no longer gated on falsification.
- New payoff cell: fraction of objective CAPTURED (paper) vs upside left ·
  downside to stop — or a position-specific "wrong lens: <why>".
- Guard: "the objective is not a trigger — reaching it mandates a DECISION, not an
  exit; not reaching it never forbids a trim." An open-ended objective's
  bank-condition must DIFFER from the invalidation (else it's a stop, not an
  objective).
- A named catalyst files a forward-expectation (5A) that pings a future cycle to
  RE-DECIDE, never auto-exit.
- Cash-aversion neutralized: cash is a re-won POSITION; banking a gain / refusing
  a no-edge tape is a decision, never a failure. Anti-passivity kept (don't force
  a trade to deploy cash; don't hold to avoid holding it).

Principle (Fable): **"mandate the confrontation, never the conclusion."**

## The regression Fable's FINAL review caught (do NOT repeat)

The naive fix — add TRIM + "every row needs a verdict and a reason" — RE-LEGALIZED
the exact failure: `HOLD — thesis intact` satisfies it forever. Teeth restored: a
green row whose structure sits above the stop OR whose payoff shows most of the
objective captured may HOLD only with a reason that NAMES that specific fact and
argues against acting THIS cycle; a generic reason = step 4 NOT DONE. Payoff cell
has per-cell teeth (empty/copied = NOT DONE; "wrong lens" needs a real why).
Lesson re-proven: forced artifacts with NOT-DONE consequences bind the (weak
local) model; prose and a bare "require a reason" do not
([[constitution-steps-not-prose]], [[constitution-enforce-via-step-not-column]]).
Fable also flagged the new payoff COLUMN as a binding risk (new column on an
established table can be skipped) — watch it live on the atrader/gemma node.

## Status — NOT deployed

Drafted in `prompts/constitution.md` (source); backup
`constitution.md.backup-20260722`; CHANGELOG 1.52.0; `docs/trading-knowledge.md`
updated. `make const` is owner-run ([[deploys-are-owner-run]]). Reviewed per
[[constitution-edit-protocol]] (GPT + Fable, two rounds — design then final).
Supersedes the trail-only winner-exit doctrine in
[[constitution-trail-forced-table-9e]] and the WINNER half of
[[constitution-stops-and-tool-mechanics]]; the existence-not-level stop rule for
LOSERS from the latter still stands. Watch live: does the weak node fill the new
payoff cell and use TRIM, or fall back to HOLD/TRAIL?
