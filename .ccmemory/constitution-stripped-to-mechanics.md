---
name: constitution-stripped-to-mechanics
description: 1.34.0 strip REVERTED — churn cause was the narrow candidate list, not aggression; aggressive constitution restored, stripped kept as .passive.
metadata:
  type: project
tags: [constitution, churn, reverted, 1.34.0, passive]
---

# 1.34.0 constitution strip — REVERTED (2026-07-09)

An earlier cut of 1.34.0 stripped the aggressive/strategy-opinion layer out of
`prompts/constitution.md` (OFFENSE posture, "cash is a FAILURE", "chase the runner", the
forced SURVEY/REVIEW/RANK/GATE tables) down to a mechanics-only brief, to fight the
same-names churn.

**That was treating the symptom.** The churn's real cause was a NARROW CANDIDATE LIST
(the junk `get_top_movers` / near-static `get_most_actives` feeds), not the aggression:
the agent was aggressive AND only had 2–3 names in front of it, so it hammered those.
Both opus (itrader) and the local model (atrader) churned identically → the feed, not
the model or the prose. See [[discovery-feed-get-all-snapshots]] for the diagnosis and
the real fix (whole-tape `get_all_snapshots`; the agent ranks in the sandbox).

**Current state:** the full AGGRESSIVE constitution is RESTORED (step 4 rewired to
`get_all_snapshots`). The stripped mechanics-only version is preserved as
`prompts/constitution.md.passive` as a revert point if the aggressive + broad-feed combo
still churns. The pristine pre-strip original is `prompts/constitution.md.backup`.

**Still-valid lesson from the strip exercise:** the constitution's aggression (OFFENSE
default, cash-is-failure) is real and CAN amplify churn — but only when the candidate set
is narrow. With a broad feed, "fully deployed" spreads across many names instead of
churning two. If churn persists AFTER the feed fix, THEN revisit the aggression (deploy
`.passive` to one instance as an A/B). Related: [[agent-must-be-guided-not-unguided]].
