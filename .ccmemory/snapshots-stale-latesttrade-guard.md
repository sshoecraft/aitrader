---
name: snapshots-stale-latesttrade-guard
description: 1.36.1: thin pairs carry months-stale latestTrade (LTC/BTC +1175% "1-day") → survey price now falls back to bar close when trade date < dailyBar date.
metadata:
  type: project
tags: [snapshots, get_all_snapshots, data-quality, crypto, stale-price, 1.36.1]
---

# Stale latestTrade in survey CSV — guard added 1.36.1 (2026-07-09)

## Symptom
atrader's (gemma) first minimal-constitution survey listed crypto movers
LTC/BTC +1175%, SUSHI/USDT +293%, AVAX/USDT +272%, DOGE/USDT +238% pct_1d.
Verified via sudo read of `/home/atrader/.local/state/aitrader/snapshots_crypto.csv`:
the CSV really contained those rows — the model read its file FAITHFULLY (no
hallucination) but also consumed the junk at face value ("high-volatility spikes")
without questioning plausibility. Opus would likely have flagged it; gemma did not —
infra owes the agent true facts (§2).

## Root cause
On Alpaca's thin non-USD-quoted pairs, `latestTrade` is the last time the pair EVER
traded on the venue — months/years old (DOGE at $0.24, AVAX at $24.83, LTC/BTC at
0.0088) — while dailyBar/prevDailyBar are current. `get_all_snapshots` row-builder
used `latestTrade.p or dailyBar.c` → stale print vs current prev_close → absurd
pct_1d. Same family as [[premarket-mark-vs-snapshot-and-stop-arming]] (stale
latestTrade premarket) and the 1.35.0 `-1` no-quote guard.

## Fix (broker_server.py, get_all_snapshots row-builder)
If `latestTrade.t` date-prefix < `dailyBar.t` date-prefix (both ISO-ish strings from
either broker's `normalize_snapshot`), the print is stale → `price = dailyBar.c`.
Snapshots without timestamps keep old trust-the-trade behavior (IBKR-safe no-op).
Result on the observed rows: LTC/BTC pct_1d collapses from +1175% to ~0.03%.

## Deploy
Broker MCP runs from the INSTALLED package on each instance — needs package
reinstall + `systemctl --user restart aitrader` (or full ./install.sh) per instance
to take effect; a repo edit alone changes nothing live
(see [[api-service-deploy-path]]). Shipped as 1.36.1 during the
[[constitution-minimal-experiment]] week — mechanics-only, does not touch the
experiment's judgment question (it strengthens it: the survey step's value depends
on trustworthy CSVs).
