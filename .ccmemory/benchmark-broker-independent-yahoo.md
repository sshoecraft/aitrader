---
name: benchmark-broker-independent-yahoo
description: 1.16.0: dashboard VTI benchmark moved to broker-independent /benchmark (Yahoo v8 chart); 1.16.1 fix: bar `t` MUST be ISO string or it vanishes off-ho…
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
RTH-only, normalized to the same `{symbol:[{t,o,h,l,c,v}]}` shape as `/bars`.
- Keyed on the chart PERIOD, not bar timeframe — `YAHOO_RANGE_INTERVAL`: 1D→(1d,5m), 1W→(5d,60m),
  2W→(1mo,60m), 1M→(1mo,1d), 3M→(3mo,1d), 6M→(6mo,1d), 1Y→(1y,1d).
- Cached per (symbol,period) for `BENCHMARK_TTL`=60s behind `_benchmark_lock`; ONLY successful pulls
  cached. Yahoo pads non-trading slots with null closes — skipped.
- Needs NO broker connection — benchmark renders even when the broker is down.

UI: `api.ts` adds `getBenchmark(symbol, period)`; `Header.tsx` calls `/benchmark`, and the now-dead
`BARS_TIMEFRAME` + `periodStartISO` were removed.

## 1.16.1 FOLLOW-UP BUG — `t` MUST be an ISO string, not a bare epoch (VTI vanished off-hours)
1.16.0 first emitted bar `t` as bare epoch-seconds. The broker `/bars` it replaced returned `t` as an
ISO STRING, and the UI's `dayKey()`/`lastSessionBars()` (Header.tsx) derive the calendar session by
**regex on a leading `YYYY-MM-DD`**. A bare epoch (`"1782307800"`) doesn't match → every bar gets a
distinct day → `lastSessionBars` keeps only the LAST bar. During RTH the equity+VTI windows overlap →
"Mode A" (uses `tsToEpoch`, handles numbers, fine); OFF-HOURS they don't → "Mode B", which calls
`lastSessionBars` and bails on `session.length >= 2` → NO LINE. Classic "shows in market hours, gone
off-hours."
Fix (api.py 0.6.1): emit `t = datetime.fromtimestamp(t, tz=UTC).isoformat()` — a drop-in for the broker
format. `tsToEpoch` already handled both string/number; `dayKey` is the one helper that assumes a string,
left as-is (matching the existing data contract is lower-risk than touching shared session logic).
LESSON: any bar feed the UI consumes must keep `t` as a leading-`YYYY-MM-DD` ISO string, or session
grouping silently breaks only in the no-overlap (off-hours) render path.

## Source choice
Yahoo, keyless — chosen over Alpha Vantage (user had a key): the multi-user concern that motivated this
(IBKR-only nodes) applies equally to an AV key, and AV free tier is ~25 req/day — unusable for a polling
dashboard. Same Yahoo provider/pattern as the 1.14.0 sector fix [[alpaca-sector-via-yahoo-search]].
Yahoo is unofficial/best-effort (quoteSummary needs a crumb → 401; v8 chart + v1 search are keyless,
stable). Overlay degrades to no line on empty bars.

## Deploy
api.py change → `make build && make install && systemctl restart aitrader-api` per node
([[api-service-deploy-path]]); UI change → `make ui` (rebuilds to `~/.local/share/aitrader/ui`).
