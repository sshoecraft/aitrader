---
name: constitution-persona-reverted
description: Persona voice added to constitution.md 2026-06-22 broke the agent; reverted same day to v6 + 3 plain-voice ports. Keep the constitution direct/impera…
metadata:
  type: project
---

2026-06-22: A "persona" / role-play framing was added to `prompts/constitution.md` — opening *"You are a trader. Twenty-five, monster energy sweating on the desk, a seat at a New York shop... security walks you to the elevator with a cardboard box,"* with EVERY section rewritten in that aggressive second-person career-stakes voice.

It confused the model and degraded trading behavior — user: *"the whole role playing thing is absolutely killing the trader."* **Reverted the SAME DAY** to the prior technical voice (`prompts/constitution.md.v6`): *"You are an autonomous portfolio allocation system... maximize a single scalar performance score S = ..."*. The persona version is preserved at `prompts/constitution.md.persona` (no git — banned in this project).

**RULE GOING FORWARD:** keep the constitution in DIRECT, TECHNICAL, IMPERATIVE voice. No persona, no role-play, no character, no career-stakes melodrama. State the objective (S), the AT-SESSION-START steps, THE CYCLE, and the tool mechanics plainly. If asked to "improve" the constitution, do NOT reach for narrative voice.

**Current `constitution.md` = v6 base + 3 de-personafied ports** (the genuinely-good content the persona rewrite had introduced, kept WITHOUT the voice; user-approved 2026-06-22):
1. **"S is a ranking heuristic, not a precise calculation"** note — added right after "maximize S at every decision cycle." Fixes a REAL hole: v6 presents S as a formula but NEVER defines the weights λ₁…λ₆, so "maximize S" taken literally isn't computable. The note tells the agent not to fabricate a decimal S / invent weights, and to rank by judging each term.
2. **ASCII fallback for the S formula** (`L1*Risk …`) beneath the unicode one — guards against subscript mangling.
3. **Step 0 uses the `now` tool** instead of "run the date command."

**Deliberately NOT ported:** the persona's "Your seat at the table" concentration/sizing rule (*"don't bet so big on one name… the blow-up door"*). It injects a sizing/risk opinion the Hard Boundary rejects (the agent owns ALL sizing); S's λ₁·Risk + λ₂·Drawdown terms already encode blow-up aversion. Same anti-pattern as the reverted mandatory stop-loss (see constitution-stops-and-tool-mechanics) and the dead zero-bias experiment (see agent-must-be-guided-not-unguided).

**The persona rewrite had also silently DROPPED two good v6 things** — restored by the revert: the explicit WRONG/failed-call examples (malformed `client_tag`, escaped-quote `side` — cases that failed REAL orders) and the "skip straight to the cycle if mid-session" note.

**DEPLOYMENT (important):** editing the /src source is NOT enough — the live agent reads the DEPLOYED copy. `make install` / `install.sh` copy `prompts/constitution.md` → `$RUN_DIR/CLAUDE.md` (= `~/.local/share/aitrader/run/CLAUDE.md`) AND `$DATA_DIR/prompts/constitution.md`. On this revert+ports, both deployed copies were updated directly via single-file `install -m 644` (no full reinstall, no service touch). An already-running session keeps its loaded prompt until the next fresh session (ccloop relay on context-fill) or a `systemctl --user restart aitrader` — the trader runs as a `--user` service (system-scope `aitrader` is inactive).

Related: constitution-stops-and-tool-mechanics, agent-must-be-guided-not-unguided, constitution-ten-step-cycle.
