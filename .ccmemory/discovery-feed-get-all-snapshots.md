---
name: discovery-feed-get-all-snapshots
description: 1.34.0: removed get_top_movers/get_most_actives screeners → get_all_snapshots (whole universe→CSV, agent ranks in sandbox). Fixes narrow-list churn.
metadata:
  type: project
tags: [broker-mcp, get_all_snapshots, churn, discovery, screener, 1.34.0, alpaca]
---

# get_all_snapshots — whole-tape self-survey replaces the canned screener feeds (1.34.0, 2026-07-09)

## The churn diagnosis that led here
atrader churned the same 2–3 AI names (NVDA/AMD: buy→stop→rebuy→stop). Ground truth:
- **BOTH models churned identically** — local vLLM (atrader) AND opus (itrader) — so it
  was never the model. They share the Alpaca data feed ([[aitrader-deployment-topology]]).
- The candidate FEEDS were junk: `get_top_movers` = only penny/warrant pumps (a
  $0.01→$0.02 warrant is +100%; vendor ranks by % then truncates, so the liquid leaders
  never even appear to be filtered); `get_most_actives` = near-static leveraged ETFs
  (SOXS/BITO/TZA) by raw daily volume.
- KEY behavioral fact: **an LLM agent does whatever a tool returns and NOTHING else** —
  so a list tool silently becomes the screener, and the list's shape IS the strategy.
  Starved of tradeable candidates, the agent looped on its own positions + self-seeded
  web searches ("AI infrastructure … NVDA AMD ORCL") and re-bought what it held.
Transcript/ledger proof: NVDA 4 buys/2 sells, AMD 3/2 in 7d; searxng queries literally
named the held tickers. Neither MCP feed ever surfaced NVDA/AMD — they came from
thesis + positions + websearch, not from any list tool.

## The fix
Removed `get_top_movers` + `get_most_actives` (broker MCP wrappers + `AlpacaBroker`
methods + the dead `ScreenerClient` import/construction). Added
**`get_all_snapshots(asset_type)`** (`broker_server.py` 0.8.0, `alpaca.py` 0.6.0): pulls
a raw snapshot for EVERY tradeable name in one call, WRITES it to
`{state_dir}/snapshots_{asset}.csv`, returns `{path,count,asset_type,as_of,columns}`
(NOT the rows — ~12k names). Columns: symbol, price, pct_1d, day_volume, rel_vol,
day_open/high/low, prev_close. Ranks/filters/scores NOTHING — the agent reads the CSV
and ranks it itself in the sandbox (its own liquidity floor + metric). Pure
orchestration over the ROUTED `get_tradeable_assets` + `get_snapshots` → cross-asset
(stock/crypto→Alpaca, forex/futures→IBKR). MORE §2-pure than the screeners (infra ranks
nothing). Constitution step 4 rewired to "get_all_snapshots → rank the CSV yourself,"
plus an anti-tunnel clause and an IEX-volume note.

## Verified live (as atrader, real Alpaca)
`get_all_snapshots("stock")` → 12,731 names in ~7s. Sandbox filter `price>5 &
day_volume>1M` → 82 liquid movers (OPEN +10%, HPE, MARA, RIVN, NOK, SOFI…) the old feeds
buried; NVDA present but RED on the day, now one row among 82, not the only option.
crypto → 73 names in 1.3s. Both files compile; the two screener tools are gone.

## Gotchas
- `day_volume` is IEX-feed share count on an IEX-only node (a fraction of consolidated) —
  calibrate volume floors to the data's own distribution, not full-tape numbers
  ([[alpaca-data-feed-iex-default]]).
- Full-universe stock pull ≈ 7s + a burst of ~55 Alpaca batch calls — a SURVEY-time
  tool, not every-wake.
- Deploy: `make build && make install` (broker code) + `make const` (constitution) +
  restart, per node.
Related: [[constitution-stripped-to-mechanics]] (the reverted strip), [[data-execution-broker-split]].
