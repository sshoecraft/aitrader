---
name: alpaca-paper-fills-gradual-iex
description: Alpaca paper fills GRADUALLY vs IEX feed — filled_qty=0 / status 'new' right after placing is NOT a broken engine; resting GTC stops also show 'new'.
metadata:
  type: project
---

A session (2026-06-22) wrongly concluded "Alpaca's paper matching engine is
broken — orders stuck in 'new', stops inert, no downside protection." All three
claims were false. Corrected diagnosis:

**1. Paper fills are GRADUAL against the IEX feed, not instant.** A marketable
XLE sell limit (xle_gtc_test_1, 121 @ $53, market ~$53.67) read `filled_qty: 0 /
status: new` seconds after placement, then progressed 0 → 59 → 120 → **121
filled @ $53.63** over ~3 minutes. Checking fill state immediately after placing
(or right at 09:30 open) shows 0 and looks "stuck." It isn't — give it minutes.
Free paper accounts match against IEX prints only (thin tape), so fills trickle.

**2. `status: "new"` is the CORRECT resting state for an un-triggered GTC stop.**
NVDA stop @189.49 (price 213), TSM @458 (472), VTI stop_limit @362 (371), LLY
@1043 (1103) all sit "new" = armed and waiting for the stop price to be touched.
NOT inert. Downside protection IS in place. Don't misread "new" as "failed."

**3. `qty_available: 0` on every position is EXPECTED** when each position has a
full-size resting protective stop — the shares are reserved by that order. To
place an additional/replacement sell you must cancel the stop first to free the
shares. Oversized sells (e.g. 121-share test sells against a position already
drawn down to 62) get held, not filled — that confounded the "stuck" tests too.

**4. Crypto is NOT impossible.** The MCP place_* tools default `tif="day"`
(broker_server.py ~L297+); Alpaca crypto rejects day, needs gtc/ioc. But the
agent's real crypto orders passed `tif="gtc"` and filled fine (BTC/ETH buys
filled; crypto stops rest as gtc). Footgun worth fixing: auto-coerce day→gtc for
crypto in brokers/alpaca.py. Related: [[alpaca-tif-case-insensitive]].

**Operational caution:** "test" orders here are REAL paper orders. The XLE test
fully liquidated the 121-share XLE position. Don't place throwaway marketable
orders against live positions to "test the engine."

Relates to [[data-execution-broker-split]], [[alpaca-vs-ibkr-bars-start]].
