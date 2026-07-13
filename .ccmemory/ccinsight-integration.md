---
name: ccinsight-integration
description: ccinsight wired into prompts/constitution.md as STEP 2C (pending-synthesis resolution), adjacent to ccprospect's 2A; edit source, run make const to d…
metadata:
  type: project
tags: [ccinsight, constitution, integration, step-2c]
---

ccinsight integrated 2026-07-13 via the ccinsight-integrate skill. Shape:
custom loop, same as [[ccprospect-integration]]. Binding file:
`prompts/constitution.md` (source) → `make const` → `$(RUN_DIR)/CLAUDE.md`
+ restart, owner-run.

Landed as **STEP 2C · RESOLVE PENDING SYNTHESIS**, right after 2B (news
check), before step 3 (survey) — adjacent to, not merged with, ccprospect's
2A, per the skill's own instruction that they answer different questions.
Forced table: `insight_survey()` → one `insight_hypothesize` response per
pending trigger (`candidate` / `no_actionable_pattern` /
`insufficient_coverage`), complete only when `pending` is empty.

`ask_gpt` review (per [[constitution-edit-protocol]]) caught real issues
before landing, all fixed: replaced a vague "real annotation" requirement
with the exact `insight_hypothesize` schema shape (`{ref_id, action:
tombstone|downweight|reviewed, reason}`); added an explicit
anti-filler line ("do not manufacture a candidate merely to clear a
trigger"); widened the TOOL_ERROR fail-open clause to cover
`insight_hypothesize` too (not just survey/observe), since a failed
hypothesize call could otherwise trap the agent retrying forever to force
`pending_count: 0`; softened `insight_observe`'s "cheap, uncapped" framing
to "not a per-cycle quota" to avoid reading as a logging requirement.

Reviewer's other major point: don't stack a 4th mandatory-step addition on
an unvalidated batch. This session had already made three OTHER
constitution/tool changes the same day, none deployed yet — landing a 4th
before validating the first three compounds risk. Owner explicitly
directed landing it anyway ("make the changes... follow the protocol")
after that tradeoff was surfaced — recorded here so a future session
understands this was a deliberate, informed call, not an oversight.

Three cross-reference touch-points updated for consistency (same pattern
ccprospect's own integration required): House-fuses outrank line (now
2A/2B/2C/5A), step-order enumeration (0,1,2,2A,2B,2C,3,4,5,5A,6,7), step 6
JOURNAL's reproduce-in-full list (now includes the step-2C table).

Backup: `prompts/constitution.md.backup-20260713-preccinsight`. Not live on
either agent (itrader/atrader) until the owner runs `make const` +
restart. `.ccinsight/integration.json` holds the full technical record.
