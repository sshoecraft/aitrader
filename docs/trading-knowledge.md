# Trading Knowledge — the agent's cognition layer

The agent's *trading judgment*: the always-in-context judgment core in
`prompts/constitution.md` plus per-asset depth in the 5 `card-*` ccmemory
notes (`prompts/ccmemory-seed/`). Distinct from the infrastructure docs
(broker/journal/scheduler/api). **It contains no strategy code.** By mandate
(BRIEF §2/§8) all cognition is the agent's reasoning; this layer supplies
*judgment to reason with*, never fixed rules, thresholds, scores, or screeners.

> **Architecture note:** §"Why it exists", "Background", and "Delivery
> architecture (3 vehicles)" below describe the ORIGINAL 1.8.0 design (12
> principles + 16 `lesson-*` notes). It was superseded on 2026-06-24, FIRST by the
> 1.10.0 fusion and THEN by the 1.12.0 step-procedure rewrite — read the 1.12.0
> section immediately below first; the rest is kept for provenance.

## 2026-06-24 (1.12.0) — the disposition is now a PROCEDURE, not prose

1.10.0 fused the two channels and rebalanced toward action — and itrader (Opus 4.8) **still
refused to trade** (deployed, restarted, confirmed live). It surveyed at the index level, wrote
"0 candidates" without pulling names, defaulted to HOLD, and confessed *"I'll make it on your
word."* That proved the actual lever: **the model executes numbered STEPS with a required output
and ignores PROSE it merely agrees with.** THE CYCLE always got followed; the 13 prose principles
and the MAKE-MONEY preamble always got rationalized around.

So `prompts/constitution.md` was rewritten end-to-end as **THE LOOP, steps 0–10**, where *each
step must produce a written artifact and you may not reach the final WAIT until every artifact
above exists.* The dispositional claims became steps: idle-cash-is-failure → the **GATE** (deploy
any settled cash a ranked candidate beats, or write the number that disqualifies it; margin is a
tool to reach for on real edge); re-justify-every-hold → a forced `YES/NO` verdict per position;
hunt-every-class → the SURVEY table (≥5 names + numbers, missing row = can't sleep); Micron-≠-
everything → catalyst-scope. The 13 principles survive only as a compact "lenses you apply inside
the steps" reference; per-asset depth stays in `card-*`. No coded screener — the ranking is still
the agent's judgment; the steps force it to ACT on that ranking. See ccmemory
[[constitution-steps-not-prose]].

## 2026-06-24 (1.10.0) — fused into ONE disposition voice + 5 asset cards

## 2026-06-24 (1.10.0) — fused into ONE disposition voice + 5 asset cards

The 1.8.0 design split judgment across **two channels**: the constitution (12
principles) and **16 separate `lesson-*` notes**. An audit of all 17 files found 11
of the 16 lessons were higher-detail *duplicates* of the 12 principles, and the two
channels carried **9 dispositional seams** — the same behavior pushed one way by a
principle and the opposite way by a lesson ("be awake through the open" vs "let the
tape settle"; "margin is ENCOURAGED, deploy without flinching" vs "size leveraged
smaller, earn the right"; "idle cash is failure" vs a "cash is a legitimate position"
repeated across ~5 lessons). When two channels disagree the model *arbitrates*, and
RLHF caution wins the tie — the live agent (Opus) sat in 36% cash through an opening
bell and "settled" by sleeping 25 min, then rationalized it. The corpus was also ~2:1
caution-to-action and **polarized by channel** (constitution = action voice, lessons =
caution voice), so loading lessons skewed the agent passive.

**The fix:**
- **One disposition voice.** The 9 seams collapse into single both-halves directives
  in the constitution, **action-clause first, caution as the bounding condition** (the
  open: "stay present on a ~5-min leash — *settle* means don't act hastily, never *be
  unconscious while it settles*"). The 11 duplicate lessons fold into ~13 principles
  (new P13: a time-of-day / holding-horizon axis that had no prior home), then deleted.
- **Rebalanced toward action.** Every free-floating "cash is a legitimate position" is
  bound to its test ("only after you surveyed every open class and nothing out-ranks
  it"). Relocating the lesson-caution verbatim would have *worsened* passivity — it was
  rewritten, not moved.
- **5 asset cards remain as on-demand depth.** Only genuinely asset-specific material
  (`card-crypto` / `-forex` / `-futures` / `-options` / `-leveraged-etp`) stays in
  ccmemory, scrubbed of the general disposition the constitution now owns. Each is the
  sole voice on its asset → no seam. Loaded via `memory_get` before trading that class,
  keeping the always-on prompt lean (matters for the local-model node).
- **Journal time → LOCAL.** Constitution step 7 and the scheduler `now` tool now expose
  the host's local wall clock (`now().local`) for journal prose, not hardcoded ET; the
  NYSE session clock stays available as `now().et`. Fixes "08:30 ET" reading as the
  future on a Central-time host; venue-agnostic (TXSE-ready). Pairs with the UI fix
  (`ui/.../JournalFeed.tsx` renders browser-local).
- **Installer migrates existing stores.** `install.sh` now removes the 16 retired
  `lesson-*` notes (its `RETIRED_NOTES` manifest) and OVERWRITES the curated cards on
  every install (cards are canon; agent relearning goes to new notes / the journal), so
  `git pull` + `./install.sh` cleans a previously-seeded store instead of orphaning it.

## Why it exists (2026-06-23)

Two live failures, one root cause — the agent had no seeded trade-quality wisdom
and was being driven by the loudest instructions it could see.

1. **Falling-knife trade.** The agent bought BTC into a confirmed downtrend,
   rationalizing *"idle capital hurts my score / cash sucks."* That was the
   faithful output of the constitution's anti-passivity prods (`IdleCapitalPenalty`,
   *"cash is an underperforming allocation by default,"* step-5 *"100% of
   capital,"* *"uncertainty is not a reason to skip"*) with nothing to push back.
   The agent recited the correct lesson *after* the loss.
2. **A false "paper account bug."** Investigation of the live atrader store found a
   self-authored memory (`broker-constraints.md` → *"stock SELL orders don't fill
   on paper feed"*) that was **false** — a misread of the normal Alpaca gradual-fill
   / `status: new` behavior, calcified into a standing belief and contradicted by
   the agent's *own* stop-outs that did fill. It vetoed stocks for weeks and
   funneled the agent into crypto-only knife-catches.

Conclusion: deliver the prior system's hard-won wisdom as **judgment** in the
channels the agent actually reads, dial back the anti-passivity pressure, and wipe
the contaminated experiential layer.

## Background — provenance of the wisdom

Mined from the prior system (`/src/archive/trader`) and its research
(`/src/research`) — **109 docs** of backtests, post-mortems, and external research.
Two read-only multi-agent workflows did extract → synthesize → adversarial boundary
audit: **643 candidate lessons**, of which **195 fixed-strategy/threshold items were
deliberately DROPPED** (RSI/ADX/ATR multiples, R:R targets, score coefficients,
symbol allowlists, fixed stop %) — that is the screener/scoring pattern the project
rejects. 17 themes synthesized → a 12-principle always-on core + ~16 depth notes.

## Delivery architecture (3 vehicles)

Sized for the production consumer **Qwen3.6-A35B** — a mid-size open-weights model
that under-retrieves and holds a weaker, noisier prior than a frontier model. The
live agent reliably sees only two channels, so:

1. **Constitution — always-in-context.** `prompts/constitution.md` → run-dir
   `CLAUDE.md`, auto-loaded every session. Holds the 12 load-bearing judgment
   principles. This is where the *override* of the bad prod lives.
2. **ccmemory `lesson-*` notes — retrieved depth.** `prompts/ccmemory-seed/*.md` →
   run-dir `.ccmemory`. The **≤150-char `description:` is the load-bearing surface**
   (often all a weak model reads via `memory_list`); bodies carry specifics +
   evidence. Retrieval is *mandated* by the constitution's step-1 `memory_list`.
3. **Skills — skipped.** `skills/*.md` is not deployed or referenced (see ccmemory
   `skills-channel-status`); discretionary + reload-per-session, wrong for a weak
   model.

**Why this works even though the principles look obvious:** the model already
*knows* most of them — the failure was a control/salience problem (a loud
in-context prod overriding a quiet training prior) plus genuinely-novel specifics
absent from any training set (equity↔forex edge inversion, the −$51K energy-cluster,
ETP −2.02 Sharpe). Seeding (a) wins the context fight, (b) delivers the specifics,
(c) supplies the experiential memory weights can't update from a live loss.

## What changed in the constitution

- **"How I think about a trade"** — 12 judgment principles (no thresholds/gates):
  1. where-in-a-move you enter dominates which name; 2. no score/rank predicts
  outcome; 3. regime before any single-name thesis; 4. count real bets, not tickers;
  5. an instruction is not an outcome (verify; `status: new` ≠ failed fill;
  don't re-fire a close); 6. size from survivable drawdown (and *no stop mandate*);
  7. edge direction is asset-class-specific; 8. oversold only if structure still
  advances; 9. leverage/options/ETP-decay amplify fragile edges; 10. stops don't
  survive gaps; 11. price is not risk (catalysts); 12. don't open what you can't
  flatten in time, net of cost.
- **FULL anti-passivity rebalance** — softened *"cash underperforms by default,"*
  step-5 *"100% of capital,"* removed *"uncertainty is not a reason to skip."* KEPT
  the survey discipline (every open class, live universe, news). Trade quality now
  dominates activity; the agent still hunts but is no longer pushed into low-edge
  trades.
- **Forced retrieval** — step-1 now names `memory_list`/`memory_get` and says to
  treat any recorded "bug"/"constraint" as a hypothesis to re-verify against the
  live broker (inoculates against the contamination class).
- **End-of-file re-assertion** of the 3 hardest non-negotiables (broker-is-truth /
  verify-exit, don't-re-fire-a-close, regime-before-entry) — recency for a weak model.

## The 5 asset cards (1.10.0)

`card-` crypto · forex · futures · options · leveraged-etp — per-asset depth only,
loaded on demand via `memory_get` before trading that class. Each carries the asset's
mechanics AND its asset-specific disposition together (they can't be cleanly separated),
evidence numbers inline as the *why*, never a rule. The general/cross-asset disposition
the old `lesson-*` notes duplicated now lives once, in the constitution's 13 principles.

_Historical (pre-1.10.0): the 16 `lesson-*` notes were entry-quality,
regime-and-momentum, mean-reversion, exits-and-stops, sizing-and-leverage, crypto,
forex, futures, stocks-etfs-leveraged, options, timing-and-open, overnight-and-gaps,
catalysts-and-news, execution-and-cost, research-dead-ends, discipline-and-process —
11 folded into the constitution, 5 renamed to `card-*`._

## Contamination wipe (rollout step)

Before the new constitution + notes take effect on a node, the contaminated
experiential layer is wiped: agent-authored memory + journal theses/notes/
positions-of-record on **both** nodes (atrader/Alpaca, itrader/IBKR).
**Kept:** `equity_snapshots` (telemetry continuity). **Source of truth:** the broker
— the agent re-derives theses on the next reconcile. **Method:** stop the node's
services, wipe **in place** (never `rm` the live `journal.db` — long-lived holders
keep the inode → split-brain), reseed the curated notes, restart. Do **not** delete
a live `.ccmemory/index.db` (the MCP reindexes new `.md` files on next read).

## Boundary discipline (load-bearing)

Everything here is judgment, not rules. A mandatory stop-loss rule was once added to
the constitution and **reverted** (2026-06-18) for injecting conservative bias the
agent didn't reason to — principle #6 therefore states explicitly that whether/where
to stop is the agent's call. The 195 dropped items and the adversarial audit exist
to keep this layer from re-becoming the screener/scoring machine the project rejects.

## Maintaining / extending

- **Change cross-asset / general judgment:** edit `prompts/constitution.md` — it is the
  single disposition voice. Then `make run-dir` (or `./install.sh`) to rewrite the
  run-dir `CLAUDE.md`; the agent loads it on next session start. Resolve any new
  action-vs-caution tension *inside one directive* (action first, caution as the bound)
  — do not add a second note that says the opposite, or you re-create a seam.
- **Add/maintain an asset card:** edit or drop a `card-<asset>.md` in
  `prompts/ccmemory-seed/` (frontmatter `name`/`description`≤150c/`metadata.type:
  reference`; body = asset-specific mechanics + disposition with evidence — keep general
  judgment OUT; that belongs in the constitution). `install.sh` OVERWRITES curated cards
  on every install (they are canon — keep agent relearning in differently-named notes)
  and removes anything in its `RETIRED_NOTES` manifest; to retire a card add its basename
  there. The installer clears the derived index and prints a restart reminder (a live
  ccmemory MCP holds the old index inode).
- **Never** add decision code, a screener, a score, or a threshold gate (BRIEF §8).

## Status / open items

- Behavioral verification is the real test: watch the live agent's next cycles
  (dashboard `/review`, journal) on a downtrend setup — it should decline / hold cash
  with a stated edge-based reason, read regime first, and not re-fire closes.
- The `positions` CLI port bug (hardcoded `7099` instead of the `api_port` file) is
  tracked separately and is unrelated to this layer.

## References

BRIEF §2/§8; the approved plan (`jazzy-juggling-moonbeam`); ccmemory
`seeded-trader-wisdom-architecture`, `agent-must-be-guided-not-unguided`,
`skills-channel-status`, `constitution-stops-and-tool-mechanics`,
`alpaca-paper-fills-gradual-iex`, `shared-alpaca-account-external-flatten-risk`.
