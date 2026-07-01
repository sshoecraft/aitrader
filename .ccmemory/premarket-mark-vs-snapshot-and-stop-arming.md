---
name: premarket-mark-vs-snapshot-and-stop-arming
description: 1.20.3: in pre-market Alpaca position current_price is FRESHER than get_snapshot latestTrade (stuck at prior close); stops arm only in regular sessio…
metadata:
  type: project
tags: [api, alpaca, premarket, heat, stops, boundary]
---

## The near-miss that produced this

WMT showed on `positions`/dashboard: current 110.95, stop 112 (long), Heat
0.00%, To Stp ~1%. Looked doubly broken ("over its stop but shows <1% and never
fired"). First diagnosis was BACKWARDS — assumed 110.95 was a stale IEX mark and
the "real" price was `get_snapshot`'s 113.23. Wrong.

## Ground truth (confirmed vs MarketWatch + Google card, 2026-07-01 08:25 ET)

- **110.90 = the LIVE pre-market price.** Alpaca's `Position.current_price`
  (`alpaca.py:169`) tracks it correctly. This mark is FRESH in pre-market.
- **113.23/113.26 = yesterday's REGULAR close.** `get_snapshot.latestTrade`
  (and Yahoo v8 `regularMarketPrice`) stick at the prior regular close in
  pre-market because IEX has thin/no extended-hours prints. This is the STALE one.
- So in pre/post-market the position mark LEADS the snapshot. NEVER re-mark
  positions FROM the snapshot — a re-mark step was designed and REJECTED because
  it would overwrite the correct live mark with the stale close.

## Why the stop hadn't fired (not a bug)

Simple stop orders arm ONLY in the regular session (9:30–16:00 ET). Alpaca lets
you set `extended_hours=true` ONLY on DAY **limit** orders — never stop /
stop-limit / trailing-stop / market. WMT gapped below 112 pre-market, so the GTC
stop stayed resting; at the 9:30 open it triggers as a market order and fills at
the gapped open (~110.9), worse than 112. Pre-market protection is impossible via
a stop — would need the agent placing a marketable limit in extended hours.

## The ACTUAL bug (fixed 1.20.3, `api.py`)

Both display formulas assumed a long's stop sits BELOW price, so a breached stop
read backwards:
- `to_stp` was `abs(cur−sp)/cur` → sign lost. Now progress-to-stop:
  `stop/current` (long) / `current/stop` (short). 100% = at stop, >100% =
  breached. Renders via UI `formatPercent` (×100) and CLI (×100) unchanged.
- heat was `|mv|×max(0,dist)/cur` → floored a crossed stop to 0 ("no risk"). Now
  `dist>0 ? |mv|×dist/cur : |mv|` — a crossed stop counts full notional (protects
  at no known level; fills at next open).

Still display-only observability per [[heat-observability]]; the agent never reads
/status. Deploy = make build+install+restart aitrader-api ([[api-service-deploy-path]]).
Related version drift: package `__init__.__version__` (1.7.4) ≠ CHANGELOG project
version (1.20.x) — see [[api-multibroker-and-version-drift]].
