---
name: constitution-stops-and-tool-mechanics
description: Constitution: a mandatory stop-loss rule was added then REVERTED same day (2026-06-18) as biasing the agent conservative — violates the no-injected-r…
metadata:
  type: project
---

On 2026-06-18, after the live agent botched `place_stop_order` calls and left
positions naked, three sections were added to `prompts/constitution.md`. One was
then deliberately REVERTED the same day.

**REVERTED — "Risk Protection Requirement" (mandatory stop-loss).** It required a
resting stop on every position and said the EXISTENCE of a stop "overrides S."
The user (correctly) judged this as **injecting a conservative bias the agent
didn't reason its way to** — the same category as the `check_risk_limits` engine
the brief rejects, just moved from code into the prompt. It violates the hard
boundary (agent owns sizing/exits BY REASONING) and the [[no-biasing]] principle.
Do NOT re-add a stop mandate. The agent can still use stops — `place_stop_order`
is infra and always available — but whether/where is the agent's call under S, not
a constitutional rule. Stops emerging from the agent's own reasoning = fine;
mandated stops = bias.

**KEPT — both are mechanics, not policy/strategy, so no boundary issue:**
- **Pacing Requirement** — end every cycle in a scheduler blocking `wait_*`; never
  loop back-to-back (the ccloop never-stop loop otherwise re-prompts and burns
  quota re-deciding the same state). See [[agent-sleep-pacing]].
- **Tool Call Mechanics** — tool args are structured fields with RAW values (no
  surrounding quotes, no backticks, no escaped quotes, no multiple params in one
  field); side is exactly buy|sell; numbers bare. Includes exact broker
  order/position tool signatures + correct-vs-wrong examples + a verify-it-landed
  rule. Added because the model kept mangling tool JSON.

Deploy constitution edits to a node via `make run-dir` (or `make install`), which
rewrites that node's run-dir CLAUDE.md; the agent loads it on next session start.
Each node serves its own copy. Lesson: when tempted to add a safety/risk RULE to
the constitution, stop — that's bias; only mechanics and the objective (S) belong
there.</body>
