---
name: journal-vocab-action-terminal-fingerprint
description: VERIFIED 7/12: 620 journal entries, both models — ZERO named chart patterns & ~zero indicators; models volunteer only action-terminal vocab (breakout…
metadata:
  type: project
tags: [journal, vocabulary, pattern-recognition, constitution, verified, elicitation]
---

# Journal vocabulary fingerprint — models emit only action-terminal language (verified 2026-07-12)

## The scan (read-only, both live DBs)
`/home/{itrader,atrader}/.local/state/aitrader/journal.db`, word-boundary regex, case-insensitive.
- itrader (opus): 347 entries, 2026-06-15 → 07-12. atrader (gemma): 273 entries, 06-23 → 07-12.

| category | itrader (entries) | atrader (entries) |
|---|---|---|
| named patterns (wedge/triangle/pennant/H&S/double-top/cup) | **0 / all six** | **0 / all six** |
| indicator frameworks (RSI/MACD/Bollinger) | 0 | 0 |
| VWAP · ATR · SMA/EMA | 5 · 1 · 1 (leakage) | 0 |
| breakout / breakdown | 117 / 34 | 23 / 5 |
| support / resistance | 24 / 12 | 13 / 2 |
| consolidat* / coil* / squeeze | 43 / 23 / 1 | 18 / 0 / 4 |
| higher-low / lower-low | 115 / 16 | 20 / 3 |

All 7 bare "flag" hits = "CONCENTRATION FLAG"/verb — zero flag-pattern usage. Named-pattern count is a perfect 0 across 620 entries on two different models.

## Attribution (the decisive layer)
- "breakout" appears in NO constitution version (live/minimal/passive/aggressive-41K) — only 3 CAUTIONARY card mentions (forex: breakout-chasers lose; crypto: loud breakouts are fakeouts; futures: chasing disappoints). Yet 117 entries on opus → largely VOLUNTEERED.
- "coiling" appears in NO prompt file at all → fully volunteered (23 entries, opus).
- higher-low/lower-low/swing/structure = constitution-seeded. consolidat* seeded only in the 41K aggressive build (itrader's window). squeeze = card-crypto.
- RSI "hit" in live constitution = substring false positive ("reveRSIng").

## The law this proves
Models DO volunteer un-seeded vocabulary — but ONLY action-terminal words: names for a level or event some loop slot consumes (entry trigger, stop placement, wake-leash imminence). Classification nouns (wedge) and indicator frameworks (RSI) terminate in a DIAGNOSIS, and no loop slot consumes a diagnosis → never generated once in 27 days, either model. Extends [[constitution-steps-not-prose]] / [[constitution-enforce-via-step-not-column]]: not just "steps bind, prose doesn't" — generation itself collapses onto slot-consumable content.

## Infra facts found alongside
- BRIEF.md line 55 sanctions an optional chart renderer ("turn bars into an image so the agent can look"). Never built (only `_render_transcript` in api.py, unrelated).
- Trader sandbox python: pandas 3.0.3 present, **matplotlib ABSENT** → the agent could not render a chart today even by choice. The perceptual channel where shape-reading is cheap is closed in practice.
- Survey CSV columns (broker_server.py): price, prev_close, pct_1d, pct_intraday, gap_pct, rel_vol, range_pos, day_volume, day_notional — ALL single-session scalars. A multi-day coil/compression state is UNREPRESENTABLE at the survey layer by construction; shape info exists nowhere upstream of step-4 per-name bars pulls.

## Status
Analysis + incorporation proposal (SHAPE sub-step, chart-render infra, optional compression fact column) delivered to owner 2026-07-12 — decision pending. No constitution edit made.
