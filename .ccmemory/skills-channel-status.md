---
name: skills-channel-status
description: skills/*.md is a DEAD channel — not deployed to the run dir, not referenced by the constitution. Live agent knowledge = constitution + run-dir .ccmem…
metadata:
  type: project
---

Verified 2026-06-23 while planning the trading-wisdom seeding.

**The live trading agent loads knowledge from exactly two channels:**
1. `prompts/constitution.md` → installed as the run-dir `CLAUDE.md` (install.sh / `make run-dir`), auto-loaded into EVERY session — always in context.
2. The run-dir `.ccmemory` store → read because the constitution's step-1 "CHECK MEMORY" mandates `memory_list`. Seeded by install.sh (agent-orientation + the curated `lesson-*` notes; never clobbers existing notes).

**`/src/aitrader/skills/*.md` is NOT a channel:** nothing in install.sh or `make run-dir` copies `skills/` anywhere; there is no `.claude/skills/`; the constitution never references skills; and Claude Code would reload them per session anyway. The `agent-must-be-guided-not-unguided` memory's old `skills-disabled` wikilink was dangling (target never existed / was deleted) — this note replaces it.

**Decision:** skip skills as a delivery vehicle. Load-bearing judgment → constitution (always-on); situational/evidence depth → ccmemory `lesson-*` notes (mandated retrieval). If skill prose is ever wanted, it must FIRST be wired (copied to the run dir + referenced) — until then, writing to `skills/` ships nothing to the agent. The old `morning-routine` / `exit-thinking` / `journaling-and-idempotency` prose was folded into the constitution + lesson notes.

Related: [[seeded-trader-wisdom-architecture]], [[agent-must-be-guided-not-unguided]].
