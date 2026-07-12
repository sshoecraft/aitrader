---
name: market-schedule-broker-scoping
description: 1.44.1 fix: get_market_schedule showed forex/futures on Alpaca (no such classes exist there); now filtered by settings().broker.
metadata:
  type: project
tags: [scheduler-mcp, market-calendar, alpaca, ibkr, broker, bugfix]
---

## The bug
`get_available_types()` (broker MCP, broker truth) correctly reports Alpaca as
`{stock, crypto}` only — `Alpaca.get_available_types()`'s own docstring says
"Alpaca has no forex/futures," and the keys are simply absent.

But `get_market_schedule` (scheduler MCP) calls
`market_calendar.week_schedule()`, which is a PURE, broker-agnostic calendar
function — it unconditionally builds `stock`/`futures`/`forex`/`crypto`
sessions for every caller, no matter what broker is configured. Correct for
IBKR (trades all five: stock/crypto/forex/futures/options). Wrong for
Alpaca/myse: those instances saw `open_now`/`next_open`/session-span facts
for forex and futures as if they were real schedule facts, when the account
can never trade those classes at all — not "closed right now," categorically
unavailable. Reported by the owner on atrader (Alpaca).

## The fix (1.44.1, `aitrader/mcp/scheduler_server.py` 0.4.0 → 0.4.1)
`get_market_schedule` now filters `week_schedule()`'s `classes` dict through
a static `BROKER_ASSET_TYPES` map before returning, and adds a `broker` field
to the response:

```python
BROKER_ASSET_TYPES = {
    "ibkr": {"stock", "crypto", "forex", "futures", "options"},
    "alpaca": {"stock", "crypto"},
    "myse": {"stock"},
}
```

Deliberately NOT fixed by making `market_calendar.week_schedule()` broker-aware
— that module has zero broker connection by design (a second process can't
share IBKR's socket, and the scheduler MCP is explicitly ZERO-trading-logic).
The map is a static capability FACT mirroring each `Broker.get_available_types()`
key set, not a live broker call or a judgment — filtering happens one layer up
in the scheduler MCP, which already reads `settings()` for `wake_floor_seconds`.
An unrecognized `broker` value degrades to the unfiltered (pre-fix) behavior
rather than hiding everything, so a future broker addition doesn't silently
show nothing.

Verified with a standalone script (Settings(path=<temp toml>), no live broker
needed): raw `week_schedule()` → `{crypto, forex, futures, options, stock}`;
filtered for alpaca → `{crypto, stock}`; ibkr → all 5; myse → `{stock}`.

## Keep in sync
If a `Broker` subclass's `get_available_types()` key set ever changes (e.g.
Alpaca adds an asset class), update `BROKER_ASSET_TYPES` in
`scheduler_server.py` to match — nothing enforces the two stay aligned, they're
independently maintained (broker code and scheduler MCP are different files
with a different owner-of-truth reason not to unify: the scheduler must not
hold a live broker connection).

Docs updated: `docs/scheduler-mcp.md` (design decision 5, was 5→6 renumbered),
`docs/market-calendar.md` (Consumers section + a note that week_schedule
itself stays broker-agnostic on purpose). Deploy is package install/restart
(Python source, not the constitution — `make const` alone won't ship this).
