---
name: alpaca-data-feed-iex-default
description: 1.20.1: alpaca_data_feed setting (default iex). Shared Alpaca account is IEX-only (SIP blocked); SIP default made intraday bars silently ~15min stale.
metadata:
  type: project
---

Both nodes (atrader exec=alpaca, itrader exec=ibkr + `data_broker=alpaca`) share ONE
Alpaca account (identical keys). That account is **free/basic = IEX only**: a SIP
snapshot returns `"subscription does not permit querying recent SIP data"`, and SIP
bars are delayed ~15 min with the recent window blocked.

**Bug fixed in 1.20.1:** `AlpacaBroker.get_stock_bars` hard-defaulted feed to
`DataFeed.SIP` → on this account it silently returned intraday bars ~15 min stale
(no error, recent bars just missing — measured default-SIP last 5m bar 15 min behind
IEX). That defeats the constitution step-4 momentum loop (confirm 5/15-min structure).

**Fix:** new `config.alpaca_data_feed` setting (default `"iex"`), threaded via
`AlpacaBroker(data_feed=...)` + `resolve_feed()` into bars AND snapshots, at every
construction site (broker_server build_data/execution, api build_data + exec path).
IEX = real-time but IEX-only ~2.5% volume; set `"sip"` ONLY on a paid SIP plan.
Callers can still pass `feed=DataFeed.SIP` explicitly for full-session historical.

Related: snapshot `latestTrade` on IEX is a thin single-venue print that LAGS — use
`latestQuote` mid for live price (itrader run-dir card `snapshot-latesttrade-unreliable`).
itrader got `data_broker=alpaca` added to its `~/.config/aitrader/settings.toml` this
session (was unset → no movers/actives feed). settings.toml is per-user (~/.config),
NOT in the repo. See [[data-execution-broker-split]].
