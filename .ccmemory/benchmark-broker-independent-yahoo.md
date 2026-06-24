---
name: benchmark-broker-independent-yahoo
description: 1.16.0: dashboard VTI benchmark moved OFF the broker feed to a broker-independent /benchmark endpoint (Yahoo v8 chart, cached); fixes per-node VTI% m…
metadata:
  type: project
---

## Symptom
The header relative-performance chart showed VTI at different values per node for the SAME timestamp —
e.g. 1D last entry +0.43% on atrader (Alpaca) vs +0.05% on itrader (IBKR).

## Root cause
The benchmark line was sourced from each node's OWN broker feed. The UI's benchmark fetch called
`getBars('VTI', …)` with NO `asset_type`, so the router's safety refinement ([[data-execution-broker-split]],
`brokers/router.py`) kept the call on the EXECUTION broker: Alpaca's IEX/SIP tape (incl. pre/post) on
atrader, IBKR's RTH paper feed on itrader. The chart's % is rebased to the FIRST bar of the window, so a
different base anchor (pre-market vs RTH open) + different ticks → divergent VTI%. Compounded by
[[alpaca-vs-ibkr-bars-start]] (Alpaca returns bars FROM start, IBKR pads backwards).

## Fix (1.16.0, api.py 0.6.0)
A benchmark is a single shared reference and must NOT depend on the broker — also an IBKR-only node has
no Alpaca feed. New broker-INDEPENDENT endpoint:
`GET /benchmark?symbol=VTI&period=1D` → `fetch_benchmark_bars()` pulls from Yahoo's keyless v8 chart
endpoint `https://query1.finance.yahoo.com/v8/finance/chart/<sym>?range=&interval=&includePrePost=false`,
RTH-only, normalized to the same `{symbol:[{t,o,h,l,c,v}]}` shape as `/bars` (t = epoch seconds).
- Keyed on the chart PERIOD, not bar timeframe — `YAHOO_RANGE_INTERVAL`: 1D→(1d,5m), 1W→(5d,60m),
  2W→(1mo,60m), 1M→(1mo,1d), 3M→(3mo,1d), 6M→(6mo,1d), 1Y→(1y,1d). (1W vs 2W are both hourly, 1M..1Y all
  daily — period distinguishes the span.)
- Cached per (symbol,period) for `BENCHMARK_TTL`=60s behind `_benchmark_lock`; ONLY successful pulls
  cached (empty/failed → retry next poll). Yahoo pads non-trading slots with null closes — skipped.
- Needs NO broker connection — benchmark renders even when the broker is down.

UI: `api.ts` adds `getBenchmark(symbol, period)`; `Header.tsx` calls `/benchmark` instead of `/bars`,
and the now-dead `BARS_TIMEFRAME` map + `periodStartISO` (the old Alpaca-vs-IBKR bar-window workaround)
were removed. Equity series unchanged. `tsc --noEmit` clean.

## Source choice
Yahoo, keyless — chosen over Alpha Vantage (user had a key) because the multi-user concern that motivated
this (IBKR-only nodes) applies equally to an AV key, and AV free tier is ~25 req/day — unusable for a
polling dashboard. Same Yahoo provider/pattern as the 1.14.0 sector fix [[alpaca-sector-via-yahoo-search]].
Yahoo is unofficial/best-effort (quoteSummary needs a crumb → 401; the v8 chart + v1 search endpoints are
keyless and stable). Overlay already degrades to no line on empty bars.

## Deploy
api.py change → `make build && make install && systemctl restart aitrader-api` per node
([[api-service-deploy-path]]); UI change → `make ui` (rebuilds to `~/.local/share/aitrader/ui`).
