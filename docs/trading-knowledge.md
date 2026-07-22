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
> 1.10.0 fusion and THEN by the 1.12.0 step-procedure rewrite — and since
> 2026-07-09 the DEPLOYED constitution is the 1.36.0 minimal experiment build
> (first section below). The rest is kept for provenance.

## 2026-07-22 (1.52.0) — REVIEW gains the upside half: two-sided thesis, TRIM/EXIT verdicts, per-cycle payoff read

itrader sat up ~$3,500 open on the refiner complex and never trimmed — because
REVIEW(a) only ever asked the DOWNSIDE question. Every position carried an
invalidation (the stop) but no OBJECTIVE, and the verdict set was `HOLD / TRAIL /
EXIT`-on-falsification, so a green runner re-won HOLD by construction and "bank
some" was never a representable action. Two external reviews (GPT-5.6, Fable-5)
called it boundary drift: a trend-following exit STRATEGY ("the trail is how a
winner is sold," cash-as-failure) baked into the prompt, deleting a modality that
is the agent's cognition. The asymmetry named it — losers get existence-of-stop +
agent picks the level; winners had the whole philosophy dictated and "take profit"
removed from the decision surface.

Fix (boundary-safe — no target/threshold/ATR rule added; the agent authors every
number): entry records a TWO-SIDED intent via `WRONG-IF:` / `WORTH:` tags (missing
either = step 6 NOT DONE); REVIEW(a) verdicts widen to `HOLD / TRIM n% / TRAIL → X
/ EXIT`, all legal in every state; a new payoff cell forces "fraction of the
objective CAPTURED vs upside left · downside to stop" (or a position-specific
"wrong lens"); the trend-following absolutism and cash-aversion are removed; a
named catalyst files a RE-DECIDE ping (5A). Principle (Fable): "mandate the
confrontation, never the conclusion." The forced-artifact binding lesson re-proven
AGAINST my own first draft — Fable's final review caught that "add TRIM + require a
verdict+reason" re-legalized `HOLD — thesis intact` forever (the original failure
with a fig leaf); teeth restored by forcing a green extended winner to NAME the
structure/captured fact and argue against acting, generic reason = step 4 NOT DONE.
Supersedes the 1.42.0 REVIEW(a)+TRAIL(9e) "a green stop-out is THE way a winner is
sold" framing.

## 2026-07-17 (1.51.0) — thesis-inheritance loop broken: provenance, fixed discovery query, three-kind GATE numbers

Theme lock on energy, verified in both nodes' data in different degrees —
the shared context-inheritance design is the common cause; model strength
sets the severity. atrader (gemma), FULL failure: 100%-energy book, macro
news queries pre-shaped by the theme (only confirmation can return),
survey-surfaced non-energy movers dismissed AT GATE for being non-energy,
and the saturated context misattributed to a human ("The user's context …
strongly suggests Energy is the driver") because journal, prospect inbox,
and relay summaries are all delivered in user-role messages. itrader (opus),
mechanism WITHOUT full capture: a crack-spread thesis carried 4+ days, 30/30
recent journal entries theme-saturated, 3 of 4 open positions oil-complex —
yet it took an explicitly-uncorrelated bet (ORCL short) and self-audited its
alpha. The loop in both cases: theme fills book + journal + prospect notes →
queries and attention shaped by it → book stays themed → next cycle's
context more saturated.

Three amendments, review-hardened per the standing edit protocol (ask_gpt):

- **Preamble provenance rule.** Journal / position records / prospect inbox /
  memory / relay summaries are mechanically replayed self-authored notes even
  when they arrive in user-role messages — never a human instruction,
  preference, or theme assignment; the space a theme occupies in the notes is
  evidence neither for nor against it. Deliberately scoped to those record
  types so a genuine owner instruction typed into the session still binds.
- **2B DISCOVERY.** The first search each cycle is a FIXED query — `global
  financial markets economy central banks geopolitics news DATE` — because a
  fixed string is mechanically checkable where "thesis-blind" self-
  classification is not (is "commodities" a theme word while holding energy?
  the model would decide, badly, in both directions). Artifacts: exact query ·
  LEADING SUBJECTS (first three, recorded before interpretation — the
  anti-cherry-pick tooth) · one MACRO line. Blind process, free outcome: a
  held theme dominating the results is a legal finding. Holdings searched
  after; a new-name entry requires its search line before the order.
- **GATE three-kind blocking NUMBER.** Candidate-vs-threshold, portfolio-
  impact-vs-threshold, or comparison-vs-incumbent/cash, each written as value
  AGAINST its level. The reviewer caught that the first draft (numbers from
  the candidate's own row/bars only) would itself have FORCED rotation by
  outlawing comparative and portfolio-impact blocks — the inverse bias.
  "Not my theme" is a stance, = step 4 NOT DONE. Inherited-stance VOID now
  covers inherited THEMES.

§2-clean: every rule is process (what to write, what counts as a written
reason), zero opinion about what to trade — concentration stays legal when it
wins on written numbers, and the theme is free to keep winning on merit.

## 2026-07-11 (1.43.0) — the week's schedule in context from session start

itrader, flat on Saturday, planned "redeploy Monday 09:30" — writing off
Sunday evening's futures/forex opens in advance. Root cause was a data gap,
not (only) disposition: no tool could state a future open for anything but
NYSE. ONCE PER SESSION gains **C**: read the scheduler's new
`get_market_schedule` (per-class session spans, next opens, holidays in the
window, source-labeled) once at session start so the schedule is always in
context, and step 7's long-sleep rule now ends BEFORE the earliest next open
on that schedule — sleeping through an open you knew about is a step-7
failure. Facts only, §2-clean: the tool states when markets open; whether and
what to trade at that open stays the agent's.

## 2026-07-11 (1.42.1) — REVIEW structure cell hardened against price-copy

First 1.42.0 cycle: bars were pulled, then the structure cells got the current
price copied in (UNI "HL 3.772" against a 3.77 print — above the price,
definitionally impossible), letting a red momentum thesis write CONFIRMS·HOLD
and a green name dodge the trail its own row's numbers demanded. Restored the
41K build's validity clause as cell-level teeth: the structure cell is a real
prior swing point several bars back, strictly below price (long) / above
(short); at-or-near the print = not filled = step 4 NOT DONE; structure above
the stop with a verdict other than TRAIL/EXIT = step 4 NOT DONE. Lesson
re-proven: prose tail-rules don't bind the local model — cell validity rules
with NOT-DONE consequences do.

## 2026-07-11 (1.42.0) — REVIEW: every holding re-wins its place

The exit-side counterpart to the GATE graft, restored after the UNI entry made
the hole concrete: nothing in the minimal+spine loop ever asked "is the reason
I bought this still true?" — a dead thesis's only exit was the broker stop
(11% away on UNI), and a green name could sit on its entry-era stop forever
(AAVE was). Step 4(a) REVIEW is one forced table per holding, filled off this
cycle's bars and the RECORDED entry intent: CONFIRM or FALSIFY the thesis
against the agent's own words; FALSIFIED → EXIT this cycle (a stop caps a
loss, never a reason to hold; a patient hold must be written with its break
level); green → answer the trail question (higher-low above the stop → modify
the existing stop under it; a green stop-out is a SUCCESS). Held name with no
row = step 4 NOT DONE. This folds the 41K build's REVIEW(a) + TRAIL(9e) into
one artifact — the two forms independently verified to bind the local model.

## 2026-07-11 (1.41.2) — GATE entries read the bars first

The 1.41.0 table's first live cycle both proved the enforcement (the local
model filled every row and column honestly, including the hesitation tax) and
exposed the trimmed-out guard: it bought the top of the move it had watched
all day, off the survey percentage alone, red within minutes. Restored from
the 41K build in table-cell form: a TAKEN on a new name must carry a structure
price read off that name's 5/15-minute bars THIS cycle (the higher-low /
lower-high being entered beyond) in its action cell — stalling or reversing on
heavy volume is the FAILED move; no bars-read price = step 4 NOT DONE. Forced
look, agent's read — the same split as the look-first survey.

## 2026-07-11 (1.41.0) — GATE becomes a forced table: TAKEN or a number (the appetite graft)

Saturday's live journal: UNI/USD topped the agent's own floorless survey six
consecutive cycles and never appeared in RANK; GATE read "No new entries.
Maintaining patience." — no number — with 82% of equity in cash. Three causes:
the 1.39.0 GATE was prose and prose is dodgeable; "patience" was a stance
inherited from the prior session's relay summary (pre-1.36.0 posture
vocabulary), not a current decision; and the minimal build's deleted appetite
layer left a vacuum trained risk-aversion filled. The agent's own post-mortem
confirmed all three.

The graft (21,536 → 23,864 B; pre-graft = `constitution.md.backup-20260711`)
states each restored idea ONCE, inside the artifact layer the local model
verifiably obeys (steps-not-prose):

- **Mandate**: the two-failure symmetry — a forced no-edge trade and
  idle/parked money cost the same. "No opinions" honestly weakened to "no
  shortlist" (the gate now carries one momentum prior).
- **4(a) RANK**: survey-surfaced names (ACT + floorless top-3) must appear,
  else step 4 NOT DONE.
- **4(b) GATE**: prose → FORCED TABLE, one row per survey-surfaced name +
  worst holding. Action cell = TAKEN (side · size) or the blocking NUMBER —
  "watch" is not a state. Stance words are not numbers and do not survive
  relays; buying is never globally on or off. Passed-before column carries
  first-pass price → current print: the hesitation tax, written down every
  cycle it recurs. Momentum prior: extended ≠ done, reject only the FAILED
  move. Idle-money clause: cash + unused buying power above a small working
  buffer must win its place each cycle or get deployed.
- **6 JOURNAL** reproduces the GATE table in full.

Deliberately NOT restored from the 41K build: the OFFENSE/DEFENSE/PATIENCE
posture machinery (the source of the stance-vocabulary this failure rode in
on), the 4× repetition of the deploy-default, and the class-edge lens list.
The graft forces the DECISION, not the trade — a pass with a real number still
passes everything (the guided-not-unguided balance kept). The review — owner
decides when — now grades minimal+spine+gate.

## 2026-07-11 (1.40.3) — card-crypto carries no track record

The crypto card had accumulated a quantified per-name record mined from the
predecessor's trade ledger (a profitable/catastrophic coin tiering, a 6.7% win
rate, a "$23.7k universe-restriction swing", a weekend win-rate table). That
ledger is inadmissible — its window is covered by documented order-management
bugs (dropped stop-loss exits, zombie/REARM stops manufacturing phantom
positions), so its per-name P&L is engineering noise — and agents were observed
citing the tiers inside live buy/pass decisions: a de-facto symbol allowlist,
the exact class the original adversarial audit DROPPED 195 items to keep out.

The card was rewritten to carry market/venue mechanics and behavioral
principles only — no predecessor references, no withdrawal notice, no coin
names carrying judgment (naming coins to exonerate them keeps the association
alive; provenance forensics in a force-read card is a per-session attention
tax). Incident history lives in the CHANGELOG (1.40.3), not in the agent's
head. Standing rule: a card never carries a quantified track record or
per-name dispositions. The contaminated `crypto-hard-lessons-provenance`
ccmemory note was deleted the same day.

## 2026-07-09 (1.36.0) — EXPERIMENT: minimal process-only constitution

With the 1.34.0 broad-feed fix in place (`get_all_snapshots`; the narrow movers
feeds had been acting as the de-facto screener behind the same-names churn), the
standing confound over every earlier "trust the model" result is gone — unguided
had never been tried with a real view of the tape. 1.36.0 deploys that clean
experiment: `prompts/constitution.md` is now a ~19k **process-only** build. Hard
mechanical obligations stay — READY gate, RECONCILE, SURVEY the whole tape per
open type with `path`+`count` proof and an ACT/PASS verdict, HISTORY
(`transactions_read` rows pasted before any entry; surfaces, never gates),
status-aware PROTECT (working-state stop off `get_orders` or a written
self-managed exit), JOURNAL format, WAKE cadence floors, tool mechanics, friction
— and ALL trading judgment (posture, deployment, sizing, leverage, entries,
exits, trailing) returns to the model. Cards remain in memory, consulted at the
model's judgment (no forced CARD line).

File map: frozen baseline `constitution.md.minimal`; aggressive build preserved
at `constitution.md.backup-20260709` (revert = copy back + `make const`);
`.backup` = Jul 6 pre-strip original; `.passive` = the 1.34.0 strip.

Review timing is the owner's call. Success needs churn to stay dead; the known
passivity signature (fluent PASS verdicts + idle cash cycle after cycle in an up
tape) means disposition was load-bearing after all → revert to the aggressive
build. Memory: `constitution-minimal-experiment`.

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

## Constitution editing principles

Four rules, each proven against the local (weaker) model in production, that
govern HOW a constitution edit is written — not what it says:

- **Numbered steps with forced artifacts bind; prose doesn't.** The model
  executes numbered STEPS with a required written output and rationalizes past
  prose it merely agrees with — proven twice (1.10.0's fused-but-still-prose
  disposition still got a "0 candidates, I'll make it on your word" refusal to
  trade). When the constitution must make the agent DO something, write it as
  a numbered step with a required artifact, never a paragraph it can nod at.
  See `[[constitution-steps-not-prose]]`.
- **New enforcement is its own step/sub-step, never a column grafted onto an
  existing artifact.** A field added inside a table the model already produces
  gets filled from habit, not from the new instruction — 1.23.0's `locks a
  gain?` column on the trail table was loaded and then silently ignored,
  reproducing the OLD 5-column table verbatim. A clean NEW step/sub-step
  introduced fresh sticks immediately. See `[[constitution-enforce-via-step-not-column]]`.
- **Never show malformed/"WRONG" tool-call examples, even to warn against
  them.** A weak model templates off the LAST concrete example it saw, not the
  negation around it — a constitution section ending on a `**WRONG**` block
  taught the model to reproduce exactly that malformed form in live orders.
  Show clean examples only; state formatting rules positively (e.g. "side is
  bare: sell") without ever printing the bad token. See
  `[[constitution-no-malformed-tool-examples]]`.
- **Keep the constitution in direct, technical, imperative voice — never
  persona/roleplay.** A 2026-06-22 persona rewrite ("You are a trader. Twenty-
  five, monster energy sweating on the desk...") confused the model and
  measurably degraded trading behavior; it was reverted the SAME DAY back to
  the plain "You are an autonomous portfolio allocation system..." voice. If
  asked to "improve" the constitution, do not reach for narrative voice. See
  `[[constitution-persona-reverted]]`.

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
