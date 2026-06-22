---
name: agent-must-be-guided-not-unguided
description: Open-ended/zero-bias experiment is DEAD — agent MUST be prodded; the S-objective constitution exists to MOTIVATE ACTION (anti-passivity), not as a ri…
metadata:
  type: feedback
---

## The stance changed — record this, don't resurrect the old one
The earlier "fully open-ended / zero-bias / observe-it-unguided" stance is **abandoned**
(its `no-biasing` memory was deleted 2026-06-20). User, verbatim: *"clearly that's not
going to be possible — the model MUST be prodded to do the right thing."*

**Why the unguided experiment failed (observed):** left unguided, the agent was passive —
only ever traded US stocks/ETFs, named tickers from its **training data** instead of the
live broker universe, never touched crypto/forex/futures/options, idled, under-used news.

## What the S-objective constitution actually IS (user's framing)
The live `prompts/constitution.md` is a full S-objective optimizer
(`S = E[R] − λ₁·Risk − λ₂·Drawdown − λ₃·OpportunityCost − …`). **Its purpose is to
MOTIVATE the model to TAKE ACTION** — it is NOT primarily a risk-management model. All the
teeth — "cash is an underperforming allocation," IdleCapitalPenalty, "Hold is not a valid
standalone outcome," generate ≥10 candidates each cycle, every held position must
re-justify vs alternatives — exist to **counter passivity**, the exact failure of the
unguided run. Read the λ-penalties as prods toward decisive reallocation, not as a
risk-budget to calibrate.

## Operating principle
- **ADDING strategy / risk / capability / data-hygiene / motivation guidance to the
  constitution is CORRECT and wanted** — not "bias to avoid." Prodding the model toward
  right behavior (act; use the live universe; read news; weigh all asset classes) is the
  intended approach. (Added 2026-06-20: a Universe Constraint + an options row in the cost
  table.)
- **Opinion-free STILL applies to INFRA/tools:** keep code, defaults, and the universe
  unbiased — no screeners, no stock-default shortlists, no decision logic in code. Guidance
  lives in the **prompt (constitution)**, never in the plumbing.
- User experiments with constitution variants (`.v1/.v2/.no/.save` backups) — **read the
  live `prompts/constitution.md`** for the active stance rather than assuming.

Supersedes the deleted `no-biasing`; partially supersedes
[[constitution-stops-and-tool-mechanics]] (risk is now explicitly in the objective).
Related: [[skills-disabled]].
