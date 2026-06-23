---
name: forex-futures-universe-enumeration
description: Forex/futures showed as untradeable because get_tradeable_assets returned [] — the old screener backfilled the universe; aitrader deleted it. Fixed+V…
metadata:
  type: project
---

# Forex/futures "no feed to survey" — root cause + fix (1.9.0, 2026-06-23)

## Symptom
The live IBKR agent (itrader) treated forex and futures as untradeable: `EUR.USD` quote
errored, `ES` snapshot all-zeros, and "no asset list; no feed to survey" for both classes.

## Investigation (vs `/src/archive/trader`)
The forex/futures **contract, order, and position plumbing in `aitrader/brokers/ibkr.py` is a
faithful, complete port** — verified helper-by-helper: `make_contract`,
`resolve_forex_pair_name`, `FOREX_CASH_MAP` (CAD/JPY inverted → USDCAD/USDJPY),
`is_forex_inverted`, `forex_convert_for_order` (flip side + invert price + qty×rate),
`close_forex_position`, `get_forex_cash_positions`, the `secType=="CASH"` round-trip, and
`resolve_front_month` (5-day roll). It was NOT mis-ported. Do not "fix" that code.

## The actual bug
`get_tradeable_assets(FOREX|FUTURES)` returned `[]` — also a faithful port. In the OLD trader
that emptiness was backfilled by the **screener/buyer** (`trader/buyer.py:get_config_universe`
reading `[screener] forex_universe` / `futures_universe` from settings.toml). aitrader
**correctly deleted the screener as cognition (BRIEF §8) but never replaced the universe
*enumeration*** — which is pure infra ("the list of tradeable symbols", BRIEF §2). So the
agent asked "what can I trade?", got nothing, and concluded "no feed." Lesson: when you strip
a cognition layer, check whether it was also carrying an infra responsibility (here, the raw
universe list) that must be re-homed on the infra side.

## Fix (1.9.0)
- `ibkr.py` (1.1.0→1.2.0): `get_tradeable_assets` enumerates `FOREX_UNIVERSE` (12 major
  IDEALPRO pairs, directions chosen so each round-trips through `normalize_position`) and
  every `FUTURES_SPECS` key — same pattern as `SUPPORTED_CRYPTO`. Complete list, never ranked.
- Delayed-data fallback: `get_snapshot`/`get_snapshots` call `reqMarketDataType(3)` so
  paper/unsubscribed feeds return delayed quotes instead of all-zeros; `get_snapshot` polls
  for the first tick instead of one fixed 1s sleep. (Neither codebase had this — net new.)
- TWS dot notation: `asset_types.normalize_pair_symbol` converts `EUR.USD`→`EUR/USD` only when
  both sides are ISO currencies (so `BRK.B` is safe); wired into `classify_symbol` +
  `make_contract`.

## VERIFIED LIVE (itrader, 2026-06-23, opus 4.8)
After `./install.sh --broker ibkr --no-gateway` + restart (package 1.9.0 / ibkr 1.2.0 /
FOREX_UNIVERSE=12 installed), the agent's first cycle surveyed both classes: forex returned
`EUR/USD` with a real snapshot `1.1382` (after-hours → delayed-data fallback served a quote,
not all-zeros), futures returned `ES/NQ/GC/CL` ("list confirmed live"). Agent quote: "Both
feeds are now live … Forex and futures return real symbols." It then reasoned to a no-trade
(no clean edge fading a hawkish-Fed trend) — correct judgment; the point is it now HAS the
universe + data to decide on. The ib_async connection blocker also cleared on reinstall.

Deploy: rebuild+install the package on the node (MCP runs the INSTALLED package — see
[[api-service-deploy-path]]); itrader is IBKR/opus. Related: [[data-execution-broker-split]],
[[alpaca-paper-fills-gradual-iex]].
