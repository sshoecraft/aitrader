---
name: alpaca-sector-via-yahoo-search
description: 1.14.0: AlpacaBroker.get_classification sources sector/industry from Yahoo keyless search endpoint; fixes dashboard "By Sector" all-Unclassified on a…
metadata:
  type: project
---

## Symptom
On the atrader (Alpaca) node the dashboard "By Sector" allocation donut showed every position as
"Unclassified · N".

## Root cause
`enrich_positions_with_sector` (`aitrader/api.py:215`) calls `b.get_classification(sym)` for each
`us_equity` position. Only `IBKRBroker` implemented it (`ibkr.py:694`, via `reqContractDetails`);
`AlpacaBroker` had no such method and it is NOT on the `Broker` ABC. Every call raised
`AttributeError`, swallowed by the enricher's `except Exception: continue`, leaving `sector` null →
all positions bucket as "Unclassified" in `AllocationPanel.tsx`. Frontend was fine; it never received
a sector. **Alpaca's API exposes no fundamental/sector data at all** — the fix required an external
factual source.

## Fix (1.14.0, alpaca.py 0.3.0→0.4.0)
Added `AlpacaBroker.get_classification(symbol)` returning the same `{sector, industry}` shape as the
IBKR path, sourced from Yahoo Finance's **keyless** quote-search endpoint:
`https://query1.finance.yahoo.com/v1/finance/search?q=<sym>`.
- Yahoo's `quoteSummary?modules=assetProfile` endpoint needs a crumb/cookie now → **401**. The
  `search` endpoint does NOT (just a browser `User-Agent`), and each equity quote carries
  `sector`/`industry` (and `sectorDisp`/`industryDisp`).
- Search is fuzzy (q=AAPL also returns AAPL34.SA), so it **exact-matches** the requested symbol.
- Alpaca writes share classes with a dot (`BRK.B`); Yahoo uses a dash (`BRK-B`). Method normalizes
  `.`→`-` for the query and match. Without this, BRK.B/BF.B returned option chains / empty.
- ETFs/funds (no sector in feed) bucket as "ETF"/"Fund" by `quoteType`, mirroring IBKR's `stockType`.
- Lazily-created `requests.Session` on `self.yf_session` (`requests` already a dep). Network/lookup
  failure → `{}` (degrade to "Unclassified", never error); caller caches the definitive answer.

Factual published reference data (like `asset_class`), not a screen/score/opinion — infra side of
CLAUDE.md §2. Routing: pure-Alpaca node → `b` is a raw AlpacaBroker (method found directly); a
BrokerRouter sends `get_classification` (not in `DATA_METHODS`) to the execution broker. Related:
[[data-execution-broker-split]] [[api-multibroker-and-version-drift]].
