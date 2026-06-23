---
name: agent-must-be-guided-not-unguided
description: Zero-bias experiment dead; agent must be guided. 2026-06-23: anti-passivity prods REBALANCED so trade quality dominates activity (survey kept).
metadata:
  type: feedback
---

## 2026-06-23 — anti-passivity REBALANCED (supersedes the "prods at full strength" reading below)
The anti-passivity teeth were diagnosed as the cause of a falling-knife trade (bought BTC into a confirmed downtrend, rationalized as "idle capital hurts my score"). Per user decision (FULL rebalance), the live `prompts/constitution.md` was rebalanced so **trade quality dominates activity**:
- Softened: "cash is an underperforming allocation by default" → "cash is a position like any other; do not deploy into a poor setup to avoid idle cash"; step-5 "100% of capital" → "best risk-adjusted allocation, may be largely/fully cash"; deleted "Uncertainty is not a reason to skip".
- KEPT (the part of anti-passivity that still matters): the SURVEY discipline — look at every open class every cycle, use the LIVE broker universe (not training-data tickers), read news. Looking is mandatory; finding a trade is not.
- ADDED: a 12-principle "How I think about a trade" judgment block + a ccmemory `lesson-*` knowledge base (see [[seeded-trader-wisdom-architecture]]).

Net: the model is still GUIDED and still hunts actively across all classes; it is no longer PUSHED to deploy into low-edge trades.

---
## (historical) The stance changed — don't resurrect the unguided one
The earlier "fully open-ended / zero-bias / observe-it-unguided" stance is **abandoned** (its `no-biasing` memory was deleted 2026-06-20). User, verbatim: *"clearly that's not going to be possible — the model MUST be prodded to do the right thing."*

**Why the unguided experiment failed (observed):** left unguided, the agent was passive — only ever traded US stocks/ETFs, named tickers from its **training data** instead of the live broker universe, never touched crypto/forex/futures/options, idled, under-used news. (The SURVEY discipline above is what cures this and is retained.)

## Operating principle
- **ADDING strategy / risk / capability / data-hygiene / motivation guidance to the constitution OR to ccmemory `lesson-*` notes is CORRECT and wanted** — not "bias to avoid."
- **Opinion-free STILL applies to INFRA/tools:** keep code, defaults, and the universe unbiased — no screeners, no decision logic in code. Guidance lives in the prompt and ccmemory, never in the plumbing.
- User experiments with constitution variants (`.v1/.v2/.no/.save/.persona` backups) — **read the live `prompts/constitution.md`** for the active stance.

Supersedes the deleted `no-biasing`; partially supersedes [[constitution-stops-and-tool-mechanics]] (risk is now explicitly in the objective). Related: [[skills-channel-status]], [[seeded-trader-wisdom-architecture]].
