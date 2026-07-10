---
name: crypto-volume-venue-only
description: Alpaca crypto day_volume/rel_vol = Alpaca's OWN venue in COIN units (quote-derived bars → 0 normal), NOT market liquidity; 1.36.2 un-floors + labels;…
metadata:
  type: project
tags: [crypto, volume, alpaca, data-quality, get_all_snapshots, 1.36.2, 1.36.3, journal-repair]
---

# Alpaca crypto volume is venue-only — never read it as market liquidity

## The vendor facts (verified in Alpaca docs)
- Alpaca crypto market data comes EXCLUSIVELY from Alpaca's own exchange —
  v1beta3 stopped distributing third-party (formerly Kraken) data.
- Bars are QUOTE-DERIVED when no venue trade printed: volume 0 with valid prices
  is normal. `day_volume`/`rel_vol` describe Alpaca's thin in-house venue in COIN
  units (BTC/USD ~0.25 coins/day) — an equities-style volume floor makes every
  crypto row look dead.
- IBKR side note: paper mirrors live data subscriptions; without one, ~15min
  delayed — mind that before trusting overnight futures volume prints.

## The fix ladder (all deployed 2026-07-09 night, live for the experiment week)
1. **1.36.2 infra:** `get_all_snapshots` keeps crypto `day_volume` FRACTIONAL
   (the old `int()` floor turned 0.4 BTC into 0), and the venue-only semantics
   are stated in the tool docstring AND a `notes` field on every crypto return.
2. **Gemma kept templating anyway** — "PASS (Low volume/conviction)" persisted
   post-fix: its own recent journal tail out-votes fresh guidance (same
   mechanism as [[constitution-enforce-via-step-not-column]]), and every relay
   re-reads the tail. Honest channels alone did not correct it.
3. **1.36.3 knowledge channel:** `card-crypto` now carries the fact in its BODY
   and its `description:` line (seen in every session-start `memory_list`).
   Installed into both agents' run-dir stores directly.
4. **1.36.3 journal repair (owner-directed):** atrader journal.db entries
   234–238 corrected IN PLACE (stop services → UPDATE → checkpoint → restart;
   backup `journal-volume-taint.backup`; NEVER rm/recreate —
   [[live-journal-db-edit-in-place]]). Bug-derived reasons replaced with true
   facts; the agent's actual decisions kept verbatim. Rationale: the tainted
   reasons were residue of the data bug, and the week's experiment
   (review 2026-07-18) must run on a clean tail — else each relay re-seeds the
   dead reflex. Replacement text chosen to be TRUE and SAFE TO TEMPLATE:
   "PASS (focus on held AI book; note: crypto day_volume is Alpaca venue-only —
   not a liquidity signal)".

## Deploy-flow gotcha (cost one round)
`make install` installs the NEWEST EXISTING `dist/` wheel — it does NOT build.
Use `make world` (build+install+const+restarts) or `make build` first.

## Open nit
card-* bodies still reference the OLD constitution's step numbers (step 4/7/11)
which don't exist in the minimal build — harmless prose but stale; revisit at
the 2026-07-18 review. Related: [[snapshots-stale-latesttrade-guard]],
[[constitution-minimal-experiment]], [[alpaca-data-feed-iex-default]].
