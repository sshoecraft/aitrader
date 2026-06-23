---
name: seeded-trader-wisdom-architecture
description: 2026-06-23: seeded prior-research wisdom — 12 judgment principles in constitution + ~16 ccmemory lesson-* notes; anti-passivity rebalanced; skills sk…
metadata:
  type: project
---

## What was done (2026-06-23)
Seeded the live trader with durable wisdom mined from the prior system's research corpus (`/src/archive/trader` + `/src/research`, 109 docs → 643 lessons; **195 fixed-strategy/threshold items dropped**). Two read-only mining workflows did extraction → synthesis → boundary audit. Full mined output persisted under the session's tasks dir at the time.

## Architecture (3-vehicle, sized for the small/open-weights consumer Qwen3.6-A35B)
1. **Constitution (always-in-context):** a 12-principle "How I think about a trade" judgment block — JUDGMENT only, no thresholds/gates (to dodge the rejected screener/scoring pattern and the reverted stop-mandate). Plus a forced `memory_list` retrieval step (step 1) and an end-of-file re-assertion of the 3 hardest non-negotiables (broker-is-truth/verify-exit, don't-re-fire-a-close, regime-before-entry).
2. **ccmemory `lesson-*` notes (retrieved depth):** ~16 dense notes in `prompts/ccmemory-seed/` carrying the specifics + evidence numbers (the ≤150-char description is the load-bearing surface for a weak model). Seeded into run-dir `.ccmemory` by install.sh (no-clobber) and written directly to live nodes after the contamination wipe.
3. **Skills: skipped** — dead channel (see [[skills-channel-status]]).

## Why (it is NOT mainly a knowledge fix)
The principles are mostly latent in the model's weights — the agent recited the right lesson AFTER a bad trade. Seeding (a) **wins the context fight**: puts the wisdom in the same always-on channel as the (now-rebalanced) anti-passivity prod that was overriding it; (b) delivers genuinely-novel specifics (equity↔forex edge inversion, −$51K energy-cluster, ETP −2.02 Sharpe); (c) supplies experiential memory the weights can't update from a live loss.

## Companion actions
- FULL anti-passivity rebalance — see [[agent-must-be-guided-not-unguided]].
- Pre-seed **WIPE** of contaminated agent memory + journal on both nodes. Two documented contaminations: a false "**paper account bug** (stock sells don't fill)" — actually the normal Alpaca gradual-fill / `status:new` behavior misread and calcified (the agent's own stops DID fill) — and a mis-recorded external flatten (see [[shared-alpaca-account-external-flatten-risk]]). Both poisoned weeks of decisions. Wipe keeps equity_snapshots; broker stays source of truth; agent re-derives theses on reconcile.

Full human-readable writeup: `docs/` design doc + `CHANGELOG.md`. Related: [[agent-must-be-guided-not-unguided]], [[skills-channel-status]], [[constitution-stops-and-tool-mechanics]], [[shared-alpaca-account-external-flatten-risk]].
