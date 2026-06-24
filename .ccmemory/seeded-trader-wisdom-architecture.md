---
name: seeded-trader-wisdom-architecture
description: 1.10.0 (2026-06-24) SUPERSEDED the 12-principle + 16-lesson split: fused to ONE constitution voice (9 seams resolved, 11 folded) + 5 on-demand card-*…
metadata:
  type: project
tags: [constitution, ccmemory, wisdom, architecture, fusion, seams]
---

## SUPERSEDED 2026-06-24 (1.10.0) — fused to ONE voice + 5 cards

The 1.8.0 "3-vehicle" design below (12 constitution principles + ~16 separate
`lesson-*` ccmemory notes) had a structural flaw. An audit of all 17 files found:
- **11 of the 16 lessons were higher-detail DUPLICATES** of the 12 principles; only
  5 carried genuinely asset-specific depth (crypto/forex/futures/options/leveraged-etp).
- **9 dispositional seams** — the same behavior pushed opposite ways by a principle vs a
  lesson ("be awake through the open" vs "let the tape settle"; "margin ENCOURAGED,
  deploy without flinching" vs "size leveraged smaller, earn the right"; "idle cash is
  failure" vs a "cash is a legitimate position" repeated across ~5 lessons).
- The corpus was **~2:1 caution-to-action and polarized by channel** (constitution = the
  action voice, lessons = the caution voice).

When two channels disagree, the model **arbitrates**, and trained risk-aversion wins the
tie. The live agent (Opus, not a weak model) sat in 36% cash through an opening bell and
benched itself 25 min, then wrote a fluent justification. The split itself was the bug.

**Fix (1.10.0):**
1. **One disposition voice.** Each of the 9 seams collapses into a single both-halves
   directive in the constitution — **action-clause first, caution as the bounding
   condition** (no separable statements to pick between). The 11 duplicate lessons fold
   into **~13 principles** (added P13: time-of-day / holding-horizon, previously homeless).
2. **Rebalanced toward action** (NOT just relocated — relocating the lesson-caution would
   have worsened passivity): every free-floating "cash is a legitimate position" is bound
   to its test ("only after surveying every open class and nothing out-ranks it").
3. **5 on-demand `card-*` notes** remain (`card-crypto/-forex/-futures/-options/-leveraged-etp`):
   asset-specific mechanics + disposition only, scrubbed of the general judgment the
   constitution now owns. Sole voice on their asset → no seam. Loaded via `memory_get`
   before trading that class; keeps the always-on prompt lean.
4. **Journal time → LOCAL.** Constitution step 7 + the scheduler `now` tool now give the
   host wall clock (`now().local`); `et` retained as the NYSE session clock. Fixes
   "08:30 ET" reading as the future on a Central host; venue-agnostic.
5. **`install.sh` migrates:** `RETIRED_NOTES` manifest removes the 16 old `lesson-*`;
   curated cards OVERWRITE on install (canon — agent relearning goes to new notes); index
   cleared + restart reminder. So `git pull` + `./install.sh` cleans an existing store.

Writeup: `docs/trading-knowledge.md` §1.10.0 + `CHANGELOG.md` [1.10.0]. Approved plan:
`buzzing-noodling-hare`. Related: [[agent-must-be-guided-not-unguided]],
[[constitution-no-malformed-tool-examples]], [[constitution-persona-reverted]],
[[skills-channel-status]].

---

## HISTORICAL — the original 1.8.0 design (2026-06-23), now superseded

Seeded the live trader with durable wisdom mined from the prior system's research corpus (`/src/archive/trader` + `/src/research`, 109 docs → 643 lessons; **195 fixed-strategy/threshold items dropped**). Two read-only mining workflows did extraction → synthesis → boundary audit.

3-vehicle architecture (sized for the then-consumer Qwen3.6-A35B): (1) constitution 12-principle judgment block; (2) ~16 `lesson-*` ccmemory notes for retrieved depth; (3) skills skipped (dead channel, [[skills-channel-status]]). Rationale was a context/salience fix, not a knowledge fix — the principles are latent in weights but a loud in-context anti-passivity prod was overriding them; seeding won the context fight + delivered novel specifics (equity↔forex edge inversion, −$51K energy-cluster, ETP −2.02 Sharpe). Companion: FULL anti-passivity rebalance ([[agent-must-be-guided-not-unguided]]) + pre-seed WIPE of contaminated agent memory/journal on both nodes (false "paper account bug" + mis-recorded external flatten, see [[shared-alpaca-account-external-flatten-risk]]); wipe kept equity_snapshots, broker stays source of truth.
