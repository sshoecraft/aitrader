---
name: ibkr-long-only-guard-removed
description: 1.46.0: verify_position_for_sell (aitrader's own code, inherited from /src/trader) silently blocked ALL short-side stock/futures orders on IBKR; remo…
metadata:
  type: project
tags: [ibkr, shorting, long-only, bugfix, 1.46.0, hard-boundary]
---

## The finding
itrader's own session log stated it directly: *"shorting is blocked
GLOBALLY on this adapter... This account is long-only... Every 'short side'
candidate in my survey language has been unactionable this whole time."*
Owner asked to confirm whether this was IBKR (broker/account-level) or
aitrader's own code.

**It was aitrader's own code — not IBKR, not an account permission.**
`aitrader/brokers/ibkr.py::verify_position_for_sell()` was called from
`place_market_order`/`place_limit_order`/`place_stop_limit_order`/
`place_stop_order` whenever `side == "sell"`:

```python
if held_qty <= 0:
    raise ValueError(f"Cannot sell {qty} {symbol}: no open long position "
                      f"(held={held_qty}). Would create accidental short.")
```

Proof it's not universal: `aitrader/brokers/alpaca.py` has ZERO equivalent
check — `docs/broker-data-feed.md` already documented "No long-only
enforcement" for Alpaca as a known asymmetry, nobody had connected it to a
live trading limitation until this incident. `docs/broker-ibkr.md` confirms
`ibkr.py` is "a clean-room port of the IBKR broker driver from `/src/trader`"
— this guard was carried over verbatim and has been present since aitrader's
VERY FIRST commit (`391e472`), never revisited.

## Why this matters architecturally
This is the same failure class as the OFFENSE/DEFENSE/PATIENCE posture
machinery found earlier (see `constitution-minimal-experiment`) and the
`/src/trader` risk-engine logic CLAUDE.md §8 explicitly says must never be
ported (`check_risk_limits`, `compute_order_prices`). A blanket "you may
never open a short" rule is exactly the kind of directional/risk POLICY
baked into infra that this project's Locked Decisions table rejects: *"NO
notional/buying-power caps — the agent owns ALL sizing"* (§3). The
constitution has ALWAYS assumed shorting is available — `"longs AND the
short side"`, `"hedge, or short"`, `direction=down` on `rank_instruments` is
explicitly framed as tradeable — the agent was never told this door was
welded shut. It just silently failed, every time, for as long as this
account has run on IBKR.

## The undocumented half-workaround
A `side="sell_short"` value existed in the code — but only bypassed the
guard in 3 of 4 order methods (`place_stop_limit_order`/`place_stop_order`/
`place_market_order` never even checked for it, so passing it there would
have skipped `verify_position_for_sell` AND gone through as a real SELL);
`place_limit_order` was the ONLY method that referenced it at all, and only
to explicitly BLOCK it for crypto (`"Short selling crypto is not supported
on IBKR"`). Crucially: **the constitution and every MCP tool docstring only
ever documented `side` as `buy`/`sell`** — `sell_short` was never part of
the sanctioned interface, so the agent had no way to discover or use it.
`place_bracket_order` never had the guard at all (a 5th inconsistency).

## Fix (1.46.0, `ibkr.py` 1.4.3 → 1.5.0)
Deleted `verify_position_for_sell()` entirely and all 4 call sites, plus the
crypto `sell_short` special case. A short IBKR genuinely can't fill (e.g.
crypto — Paxos/ZeroHash has no margin/short mechanism, a REAL venue
constraint, not a policy) now surfaces as IBKR's own rejection at order
time, same as it always has on Alpaca. `held_qty()`, `recover_portfolio()`,
`get_forex_cash_positions()` are unaffected — still used elsewhere (position
reconciliation), only the sell-side pre-flight block was removed.

Docs updated: `docs/broker-ibkr.md` (new subsection under the driver's
market-data section), `docs/broker-data-feed.md` (asymmetry note updated —
no longer an asymmetry). No constitution change needed — it already assumed
shorting works.

Related: `constitution-minimal-experiment` (same failure pattern —
inherited-but-unexamined restriction contradicting the "agent owns
everything" design), `futures-zeros-and-mcp-bypass` (same session, same
audit method: read the agent's own transcript directly).
