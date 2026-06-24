---
name: alpaca-tif-case-insensitive
description: Alpaca (0.13.1) AND IBKR (1.12.1) had case-sensitive TIF/side w/ silent fallback (uppercase GTC→DAY, BUY→SELL); IBKR TIF fixed, IBKR side still laten…
metadata:
  type: project
tags: [ibkr, alpaca, tif, side, case-sensitivity, silent-fallback, orders]
---

Case-sensitivity + silent-fallback footguns in the broker adapters, all faithful ports of `/src/trader` (NOT regressions). The same two bugs (TIF + side) exist independently in EACH adapter — fixing one adapter does not fix the others.

## Alpaca (`brokers/alpaca.py`) — fixed aitrader 0.13.1

**1. `tif_enum` (seen live 2026-06-18).** Uppercase TIF `"GTC"` failed cryptically; lowercase `"gtc"` placed. Cause: lowercase-keyed dict + `.get(tif, DAY)` → uppercase/unknown silently became DAY. Fix: `str(tif).strip().lower()`, DAY only for empty/None, else `ValueError`.

**2. `side_enum` (MORE dangerous).** `BUY if side == "buy" else SELL` → any non-exact match (`"BUY"`, `"Buy"`) silently placed a **SELL** = wrong direction, no error. Fix: case-insensitive match, `ValueError` on anything else.

## IBKR (`brokers/ibkr.py`) — TIF fixed aitrader 1.12.1; SIDE still latent

The same two bugs were present here (the memory's own "audit other adapters" warning paid off).

**1. TIF — seen live 2026-06-24, FIXED.** itrader asked for a GTC stop; the adapter silently recorded **DAY** (would expire at the close → unprotected overnight into a binary catalyst). Cause: `TIF_MAP.get(tif, "DAY")` against a lowercase-keyed map. Fix: new `normalize_tif()` (lowercase/strip + RAISE on unknown, never silent DAY), applied at all 5 placement sites. The agent had worked around it by retrying lowercase `"gtc"`.

**2. SIDE — STILL LATENT (not yet fixed).** 17 `side == "buy"`/`"sell"` comparisons → uppercase `"BUY"` resolves to the `else` = **SELL (wrong direction)**. Not currently hit because the constitution mandates lowercase side and the agent complies, but it must be hardened (normalize side to lowercase at each public `place_*` method entry). If/when fixed, bump and note here.

## Deploy note
These are package code (`brokers/*.py`), so they need `./install.sh` (rebuild) + a service restart — a RUNNING broker MCP only picks up new adapter code on relay/restart, not from the source edit alone. (Constitution-only changes, by contrast, just copy to the run dir.) `/src/trader/trader/brokers/*.py` still carries all of these latent. Relates to [[data-execution-broker-split]].
