---
name: gemma-crypto-floor-self-blinding
description: 7/10: gemma ranked crypto with stock-template floors (price≥1 + vol≥1M coins = structurally ~empty on venue units) → hourly "None meeting filters" vs…
metadata:
  type: project
tags: [crypto, gemma, rank-instruments, survey, 1.40.0, day-notional, test-week, ibkr-live]
---

# gemma crypto floor self-blinding → 1.40.0 look-first survey (2026-07-10)

## The finding (transcript-verified via sudo on atrader's session jsonl)
gemma's survey calls, exact args off the wire:
- 13:56 ET `rank_instruments(crypto, by=pct_intraday, min_price=0.1, min_volume=100000)` → USDC-ish survivors → journal "no significant movers beyond USDC" (faithful).
- 15:06 ET it RATCHETED to `min_price=1, min_volume=1000000` (same cycle's stock call: `min_price=10, min_volume=1e6` — the stock template, price scaled 10→1, volume copied verbatim) → re-issued identically at 16:08 and 17:10 ET.
- Those floors are STRUCTURALLY ~empty on Alpaca venue units: ≥1M-unit pairs are sub-$1 memes (PEPE 1.4B, BONK 1.1B — killed by min_price=1); every ≥$1 coin prints hundreds of units max (BTC 1.26, AAVE 245, DOT 655 — killed by min_volume=1M). Replay on the real CSV: 73 rows → 36 killed by price, 36 by volume, ONE survivor = USDC (stablecoin, $3.6M/3.6M coins) — which the journal rounded to "None meeting filters · PASS: No signals" while the tape had PEPE +6.7→7.5%, AAVE +5.6%, DOT +5.4% (AAVE/SKY = Tier-1 on its own card-crypto; card never consulted — CARD LINE fires on ENTRIES only, a survey-blinded session never reaches one).
- Mechanism: the venue-volume dead reflex (see [[crypto-volume-venue-only]]) survived the 1.36.2 data fix + 1.36.3 card by MOVING from prose reasoning into TOOL-CALL ARGUMENTS — honest channels (docstring, notes field, card) never fire when the model pre-filters itself blind. Cell wording then templates off the journal tail cycle-over-cycle.

## The fix (1.40.0 — code in /src, deploy OWNER-run)
Three layers, §2-split intact (tools = facts, constitution = forced look, judgment = agent's):
1. `day_notional` CSV column = price × day_volume DOLLARS (stock+crypto; futures/forex honestly empty — futures needs multiplier, rows already carry `notional`). Coin units inverted activity ranking (1.4B PEPE ≈ $4k vs 1.26 BTC ≈ $80k); dollars restore it. NOT a fabricated "global volume" — owner floated inflating venue volume by a per-coin factor; rejected (no stable factor exists; violates no-mock-data; poisons journals + the own-data post-mortem method that killed the weekend veto and built the tier list).
2. `rank_instruments` returns `universe` + `excluded` per-filter tallies {no_data,min_price,min_volume,stale,held} — count=0 names its own cause — and crypto results carry the venue-coins `notes` (PARITY: get_all_snapshots had it since 1.36.2; the newer 1.38.0 tool had lost the guard).
3. Constitution step 3(b) "look FIRST, filter AFTER": first ranked call per type FLOORLESS; survey row quotes its top 3 as symbol · %move · $notional; floored zero-result must paste `excluded`; session's first crypto survey reads card-crypto (`CARD: read` in the cell). Table header + NOT-DONE line updated to match. Second same-day constitution amendment after the 1.39.0 spine — the review must note the baseline moved twice Fri (re-freeze of `.minimal` = owner's call).
Verified on the REAL atrader CSV (ast-extracted function, stubbed settings, exclude_held=False): floorless → 20 movers PEPE-led w/ notes; gemma floors → count=1 USDC w/ 36/36 excluded; by=day_notional → USDC $3.6M > BTC $80k > ETH $37k. Compile clean.

## Why it matters beyond gemma (owner's objective, stated 7/10 evening)
#1 objective = make money; Alpaca crypto's job = LEARN the crypto loop so IBKR LIVE crypto (Paxos/Zero Hash — live-only, CANNOT paper, 8 majors, same single-venue coin-unit volume trap) inherits working knowledge via the two artifacts that survive a broker swap: the cards (seed = prompts/ccmemory-seed/) and the broker/tool code. A dead survey = no learning = nothing to inherit. Guard therefore keys on ASSET CLASS, not broker.

Related: [[weekend-carry-friday-ab-evidence]], [[rank-instruments-tool]], [[constitution-minimal-experiment]], [[constitution-enforce-via-step-not-column]], [[deploys-are-owner-run]].
