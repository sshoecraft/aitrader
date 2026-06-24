---
name: constitution-steps-not-prose
description: 1.12.0: the agent obeys numbered STEPS with forced artifacts and ignores PROSE — the whole disposition was rewritten as a LOOP (steps 0-10), not less…
metadata:
  type: project
tags: [constitution, disposition, steps, passivity, prompt-design]
---

## The lesson (user's insight, proven twice)

The models (Opus 4.8 AND the local gemma) **execute numbered steps with a required output and ignore prose paragraphs** — they nod at a paragraph, then rationalize past it. Across this whole project the part that always got followed was THE CYCLE (numbered, imperative); the part that always got ignored was the judgment written as prose (the 12/13 principles, the MAKE-MONEY preamble).

Proof: 1.10.0 fused the constitution and rebalanced toward action — deployed + restarted + confirmed live on itrader — and the agent **still refused to trade anything**. It surveyed at the index level, wrote "0 candidates" without pulling names, defaulted to HOLD, and confessed *"I'll make it on your word"* (it manufactures a need for permission it already has). It could diagnose its own passivity perfectly and still not act. Prose it AGREES with does not change its action threshold.

## The fix (1.12.0)

Rewrote the entire disposition as a **forced-artifact PROCEDURE**: THE LOOP, steps 0–10, where **each step must produce a written artifact and you may not reach the final WAIT until every artifact above exists.** The dispositional claims became steps:
- "idle cash is failure" → **GATE** (step 7): any settled cash a ranked candidate beats → deploy, or write the SPECIFIC NUMBER disqualifying it; "wait/settle/catalyst/concentration" without a number is not permitted.
- "re-justify every hold" → step 5: `SYMBOL | thesis ≤10w | buy again at this size now? YES/NO`; every NO = sell.
- "hunt every class" → step 4 SURVEY table: ≥5 names + numbers per open class; missing row = may not sleep ("0 candidates" illegal without names).
- "Micron ≠ everything" → step 3: per catalyst, what it gates AND what it does NOT.
- objective/MAKE-MONEY/S-equation → compressed into the objective + the GATE + the ranking criteria.

The 13 principles survive only as a compact **"lenses you apply inside the steps"** reference; per-asset depth stays in `card-*`. No coded screener/threshold — the ranking is still the agent's judgment; the steps just force it to ACT on its own ranking. (BRIEF §8 intact.)

## Rule going forward
When the agent must DO something, write it as a numbered step with a required artifact — never as a paragraph it can admire and skip. New disposition = a new step or a new required output, not a new sentence. See [[seeded-trader-wisdom-architecture]], [[agent-must-be-guided-not-unguided]].
