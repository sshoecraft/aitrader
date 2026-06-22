---
name: alpaca-tif-case-insensitive
description: Alpaca tif_enum AND side_enum were case-sensitive w/ silent fallback (uppercase TIF→DAY error; uppercase BUY→SELL wrong-direction). Fixed aitrader 0.…
metadata:
  type: project
---

Two case-sensitivity + silent-fallback footguns in `brokers/alpaca.py`, both
faithful ports of `/src/trader` (NOT regressions). Fixed in aitrader **0.13.1**.

**1. `tif_enum` — seen live 2026-06-18.** An Alpaca crypto order (BTC/USD) with
uppercase TIF `"GTC"` failed with cryptic broker "invalid crypto time_in_force";
lowercase `"gtc"` placed fine. Cause: dict keyed lowercase-only +
`.get(tif, TimeInForce.DAY)` → uppercase/unknown silently became DAY, which
Alpaca rejects for crypto. Fix: `str(tif).strip().lower()`, DAY only for
empty/None, else `ValueError` naming bad value + valid set.

**2. `side_enum` — found while fixing #1, MORE dangerous.** Was
`OrderSide.BUY if side == "buy" else OrderSide.SELL` → any non-exact match
(`"BUY"`, `"Buy"`) silently fell to the `else` and placed a **SELL** = wrong
trade direction, no error. Fix: case-insensitive match on buy/sell, `ValueError`
on anything else.

Both verified against real alpaca-py (GTC/gtc; buy/BUY/Sell/long). Built +
installed to `~/.local` (0.13.1). A RUNNING broker MCP only picks these up on
session relay / service restart — install alone doesn't touch the live process.

**Future ports:** `/src/trader/trader/brokers/alpaca.py` still has BOTH latent
bugs (same `.get(tif, DAY)` and same `side==... else SELL`). Audit any other
enum coercions ported from /src/trader for the same case/silent-fallback pattern.

Relates to [[data-execution-broker-split]].
