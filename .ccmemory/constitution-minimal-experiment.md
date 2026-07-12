---
name: constitution-minimal-experiment
description: Minimal experiment amendments: 1.39.0 spine, 1.40.0 look-first, 1.41.0 GATE table, 1.41.2 bars guard, 1.42.0 REVIEW, 1.43.0 session schedule, 1.44.0…
metadata:
  type: project
tags: [constitution, experiment, spine, gate, 1.39.0, 1.41.0, test-week, 1.44.0, news]
---

# Minimal-constitution experiment — amended to minimal+spine (1.39.0), then minimal+spine+GATE-table (1.41.0)

## How the pure-minimal question got answered in one dress-rehearsal day
Launched Thu evening as "generic tools + mandatory mechanical loop; ALL judgment
to the model" ([[1.36.0 entry in CHANGELOG]]). Friday's live evidence, all from
the agents' own journals:
1. **Appetite fails silently** — the hesitation tax: itrader planned a
   hold-branch for a gap-up, executed the exit anyway (204.05), watched its own
   identified leader run, re-entered $5 higher (209.03). Superb risk hygiene,
   omission-bias on entries. (Its self-authored trigger DID fire an entry at
   size later — arm-then-execute works; arming is just late.)
2. **Breadth fails by choice** — with the consolidated tape (284 movers ≥2%),
   rank_instruments (short side included), and honest volumes, BOTH models
   still built one-name books — the SAME name (NVDA).
3. **Leverage is invisible** — $130k BP journaled every cycle, "only $4.5k cash
   anyway" written as the budget, "unlevered" as a virtue. The deleted "margin
   is a tool" sentence left a vacuum trained risk-aversion filled.
Tool layer is COMPLETE and proven (1.36.1→1.38.1); none of the above is a data
or tool problem.

## The spine (1.39.0 — owner-directed, shipped Fri)
Constitution step 4 lettered artifacts (clean-new sub-steps bind — the
[[constitution-enforce-via-step-not-column]] form): (a) RANK ordered list,
(b) GATE (outranks cash/worst holding → TAKEN, or the specific NUMBER),
(c) BOOK (largest same-driver cluster % of equity, surface not gate),
(d) HISTORY, (e) order mechanics. Step 6 journal reproduces RANK/GATE/BOOK.

## Third amendment (1.41.0, Sat 7/11) — the spine's GATE didn't bind gemma; now a FORCED TABLE
Saturday evidence (journal ids 285–294): UNI/USD topped the agent's own
floorless survey SIX consecutive cycles (+5.8→+6.9%, $notional $4k→$14.7k),
never once entered RANK; GATE read "No new entries. Maintaining patience." —
no number — with 82% of equity in cash. Compounders: (1) "patience" was
INHERITED — the ccloop relay prompt injected the prior session's dying posture
("POSTURE: PATIENCE", "Buys: DISABLED", pre-1.36.0 vocabulary) and gemma
templated it forward; (2) wake cadence was pinned at ≤30min by the client's
1800s MCP idle watchdog, feeding error turns every long wait
([[scheduler-wait-1800s-progress-heartbeat]]). Prose GATE = dodgeable; same
lesson as trailing ([[constitution-trail-forced-table-9e]]). 1.41.0 graft
(21,536 → 23,864 B; pre-graft = `.backup-20260711`):
- Mandate: two-failure symmetry (no-edge trade ≡ idle/parked money); "no
  opinions" → "no shortlist" (one momentum prior now lives in the gate).
- 4(a) RANK: survey-surfaced name absent from RANK = step 4 NOT DONE.
- 4(b) GATE = FORCED TABLE: one row per survey-surfaced name + worst holding;
  action = TAKEN (side·size) or the blocking NUMBER — "watch" is not a state;
  stance words are not numbers and are VOID across sessions/relays; buying is
  never globally on/off; passed-before column = first-pass price → now (the
  hesitation tax made visible); momentum prior (extended ≠ done; "it already
  moved" is not a number); idle-money clause (cash + unused BP must win its
  place each cycle or get deployed).
- 6 JOURNAL reproduces the GATE table in full.
- **1.41.2 (same day):** the table's FIRST live cycle (journal id 295) proved
  enforcement — every row/column filled honestly, hesitation tax written
  "~3.50 -> 3.82" — and the model promptly bought UNI at +7.58% (the top of the
  move it had watched all day) off the survey % alone, red in minutes. The one
  41K guard the trim shouldn't have cut, restored in cell form: a TAKEN on a
  NEW name must carry a structure price read off its 5/15-min bars THIS cycle
  in the action cell (stalling / reversing on heavy volume = the FAILED move),
  else step 4 NOT DONE. Forced look, agent's read.
- **1.42.0 (same day, evening):** the red UNI position exposed the EXIT hole —
  nothing ever re-asked "is the thesis still true?": a dead thesis's only exit
  was the stop 11% away, and green AAVE sat on its entry-era stop. Step 4(a)
  REVIEW: one forced row per holding off the bars + the RECORDED entry intent —
  CONFIRM/FALSIFY against the agent's own words; FALSIFIED → EXIT this cycle
  (a stop is never a reason to hold; a patient hold must name its break level);
  green → the trail question (higher-low above the stop → modify the EXISTING
  stop under it; a green stop-out is a SUCCESS). Held name with no row = step 4
  NOT DONE. Folds the 41K build's REVIEW(a) + TRAIL(9e) into one table;
  sub-steps re-lettered (a) REVIEW … (f) act.
- **1.42.1 (same evening):** first REVIEW cycle — bars pulled (3 get_bars),
  then the structure cells filled with the CURRENT PRICE (UNI "HL 3.772" vs
  print 3.77 — above price, impossible) → red momentum thesis wrote
  CONFIRMS·HOLD; AAVE wrote structure 100.095 > stop 94 with verdict HOLD,
  against the prose trail rule in the same bullet. Fix = the 41K validity
  clause as CELL teeth: structure = real swing point several bars back,
  strictly below price (long)/above (short); at-or-near the print = not
  filled = NOT DONE; structure>stop with verdict ≠ TRAIL/EXIT = NOT DONE.
  Lesson RE-proven: prose tail-clauses don't bind gemma — cell-level NOT-DONE
  consequences do ([[constitution-enforce-via-step-not-column]]).
- **1.43.0 (Sat night):** itrader, flat, planned "redeploy Monday 09:30" —
  writing off Sunday-evening futures/forex opens in advance. DATA GAP, not
  just disposition: the only forward-looking schedule fact in the toolset was
  NYSE next_open; futures/forex holiday halts were visible only once already
  in effect. Fix: market_calendar 0.3.0 `week_schedule` (per-class session
  spans — NYSE + CME_Equity library tiers, holiday/half-day aware,
  source-labeled; forex rule-week; crypto 24/7) + scheduler
  `get_market_schedule(days)` + ONCE PER SESSION **C** (read it once at
  session start — owner's design: in context always, not re-pulled every
  cycle) + step 7 long-sleep ends BEFORE the earliest next open. Deploy needs
  the PACKAGE (make world/full + restart), not just make const.
- **1.44.0 (Sun 7/12) — the news-check obligation itself came back.** Owner
  audit: 1.36.0's removal took OFFENSE/DEFENSE/PATIENCE posture (correctly —
  that's prompt-encoded strategy, the model's judgment per the project's own
  Hard Boundary) but ALSO silently took the mandatory "go look at the news"
  forcing function with it — step 4 DECIDE & ACT only ever listed web search
  passively among "whatever helps," no artifact, no NOT-DONE gate. The
  predecessor system had been burned before by not checking news for upcoming
  events; this constitution had quietly drifted to the same gap. Fix (owner
  call, scoped narrowly): new **STEP 2B · CHECK THE NEWS**, right after 2A
  (prospective inbox) and before step 3 SURVEY — mandatory web search of
  market/macro + every held/candidate symbol, written findings, NOT-DONE gate
  if no search line appears; a CATALYST SCOPE sub-bullet forces writing what
  an event gates and what it does NOT (a chip earnings print doesn't gate
  banks). Deliberately did NOT bring back OFFENSE/DEFENSE/PATIENCE or any
  default-posture bias — what the agent DOES with what it found stays its
  judgment, only the act of looking + writing it down is forced. 27,408 B →
  30,689 B. Landed alongside ccprospect integration's 2A/5A steps the same
  session ([[ccprospect-integration]]); placement (2A/2B/5A as lettered
  sub-steps rather than a renumber of the flat 0–7 sequence) chosen to avoid
  touching the ~25 existing "step N" cross-references elsewhere in the doc.
Deliberately NOT restored from the 41K aggressive build: OFFENSE/DEFENSE/
PATIENCE posture machinery (the source of the inherited stance-word), the 4×
deploy-default repetition, the class-edge lens list. Forces the DECISION, not
the trade ([[agent-must-be-guided-not-unguided]] balance kept).

## What the review grades — owner decides when (now measuring minimal+spine+GATE-table+news-check)
- GATE table filled honestly? Every survey top-3 name a row, action-or-number,
  passed-before column accumulating when it hesitates.
- Hesitation tax per entry (identified price vs paid price) — and whether the
  passed-before column shrinks it.
- Book shape: multi-position books? Cluster % trend. Margin: BP engaged with a
  number, or excused with one?
- Churn stays dead (HISTORY + broad feed); survey artifacts stay numbered.
- Cadence: pre-1.41.1 "30-minute leash" wording was the watchdog, not judgment
  — grade cadence only after the heartbeat deploy.
- Baseline moved FOUR times (Fri spine, Fri look-first, Sat gate-table, Sun
  news-check) — all owner-directed; `.minimal` remains the frozen
  pure-minimal reference (now stale on the news point — it predates 1.44.0).
File map: `.backup-20260709` = aggressive revert point (has the full old
REGIME+CATALYSTS step with posture, if ever needed for comparison);
`.backup-20260711` = pre-graft minimal+spine; `.backup-20260712` = pre-2B
(has 2A/5A, no news step); `.backup-20260712-prenews` = same point, taken
right before the 2B edit. Deploys OWNER-run ([[deploys-are-owner-run]]).
Related: [[rank-instruments-tool]], [[survey-feed-delayed-sip]],
[[gemma-crypto-floor-self-blinding]], [[weekend-carry-friday-ab-evidence]],
[[ccprospect-integration]].
