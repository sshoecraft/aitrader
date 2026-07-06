---
name: crypto-hard-lessons-provenance
description: Crypto scars: 6.7% autopsy (names/structure/stops), v3.1.15 tier record incl. SOL; weekend-entry veto DISPROVEN by own data (1.28.0: priced condition…
metadata:
  type: project
---

# Crypto hard-lessons provenance + card channel (2026-07-03, through 1.28.0)

## The scars that are REAL (evidence-backed)
- **6.7% win-rate autopsy** (/home/trader/etc/crypto_system_prompt.md + trading.db):
  (1) chasing "confirmed recoveries" that were distribution/markdown; (2)
  re-entering after stop-outs — "single biggest source of losses"; (3)
  equity-width (sub-1%) stops = noise-harvesters. DB: 502 crypto trades
  2026-02-23→06-22; of 195 sells only 9 full_tp (84 trail, 59 stop_loss).
- **v3.1.15 six-name allowlist record** (settings.py:707, archive CHANGELOG 6090,
  ~/research/crypto/notes/findings.md): Tier-1 BTC/ETH/DOGE/AAVE/SHIB/SKY
  +$3,485/52 trades; catastrophic ten (PEPE DOT UNI GRT PAXG **SOL** FIL CRV
  LTC XTZ) −$19,672/50; exit-tightening DISPROVEN. In aitrader this lives as
  card EVIDENCE with a burden-of-proof disposition — NEVER as a coded
  allowlist (§2/§8).
- Alpaca crypto protective stops are stop-LIMIT → a fast gap through the
  limit band can skip the fill (mechanic, in the card).

## The lesson that was WRONG (do not re-learn it)
The 1.26.0 card's "never ENTER crypto before a (long) weekend" veto was
DISPROVEN by the account's own data and removed in 1.28.0: FIFO by entry
weekday — Sat 41% WR/−$2.4k, Sun 47%/−$0.2k vs Mon 53%/−$4.2k, Wed
40%/−$6.0k. Losses tracked names/structure, not calendar. The veto had
imported the PREDECESSOR's daytime-cron architecture (genuinely unwatched
weekends) into a 24/7 agent. First live cycle also showed the
channel-arbitration failure (card used as blanket veto for 5 names, step-4/7
numbers skipped — the 1.10.0 disease). 1.28.0 reframe: **weekend = priced
condition (structural stop sized for gap-through + STAY ON WATCH), never a
calendar veto**; card closes with an action clause (card sharpens step-4/7,
never replaces; "because of the card" with no step-7 number is an excuse).
Constitution step 11 gained the off-hours leash: holding any open-class
position (crypto nights/weekends) → sleep ≤~2h around the clock; only a flat
book earns a long sleep.

## Card channel status
- 1.27.0 constitution step-7 **CARD LINE**: first carded-class entry per
  session forces memory_get of the card; every carded entry writes
  `CARD <class>: "<line arguing hardest AGAINST this trade>" — <why it
  survives / overriding evidence>`; no line = step-7 failure; memory error →
  line says so, trade proceeds. Verified live 2026-07-03: first post-deploy
  cycle read card-crypto unprompted and cited it (declined XRP/ADA adds).
  The formal line fires on the next actual carded entry.
- Cards are canon: deploy = copy prompts/ccmemory-seed/* + clear index +
  restart trader (live memory MCP holds the old index inode). 1.28.0 shipped
  to BOTH nodes 2026-07-03 evening.

## Watch items
- Next crypto cycle: step-4 table WITH numbers, step-7 per-candidate numbers,
  CARD line on entries, wait ≤2h while holding crypto.
- Trigger context: 2026-07-03 13:23 ET the agent bought ~$20k BTC+SOL into
  the July-4 weekend; SOL (catastrophic-tier name) later trailed to a
  LOCKS-GAIN stop 82.10 > entry 81.87 — the 9(e)/(f) machinery working.
Related: [[shared-alpaca-account-external-flatten-risk]],
[[constitution-enforce-via-step-not-column]],
[[seeded-trader-wisdom-architecture]], [[holiday-aware-session-gate]].
