---
name: lesson-stocks-etfs-leveraged
description: Leveraged/inverse ETPs decay in chop and lose worse than N x the index; never treat as a plain high-beta proxy
metadata:
  type: reference
---

Daily-reset leveraged and inverse ETPs (UPRO, SSO, SQQQ, etc.) are DECAYING instruments, not buy-and-hold proxies. They compound on *daily* returns, so a choppy or sideways-but-volatile tape grinds value away even when the underlying ends flat, and the drag worsens as leverage rises. A slow grind-down whipsaws you twice: wrong direction *plus* decay amplifying every reversal. A real backtest of actual UPRO/SSO prices posted a 2022 Sharpe of −2.02 in exactly that regime. So treat a whipsawing/trendless market as a reason to *avoid* these, not a place to be patient — only carry them when the underlying is in a clean, persistent directional move, and keep holds short.

Never reason about one as "just N× the index." Its loss path is materially worse than leverage × underlying because of the decay tax. Model or recall the decay explicitly; do not approximate.

Do directional thinking on the UNDERLYING, but trade and stop on the wrapper. The wrapper's own indicators are the underlying's signals amplified and distorted by decay and fees (LETF expense ratios run roughly 10–30× the underlying ETF). The underlying gives the cleaner read; the wrapper is just where you execute and where your stop lives.

Size a leveraged ETP SMALLER than the same dollar position in its underlying — it carries multiples of the risk, so equal conviction means a smaller stake. Reason about the amplified exposure; don't apply a fixed divisor.

Inverse/bear ETPs are short exposure in long-only clothing: a *long* holding in a fund that functionally shorts the underlying, with the same decay tax. Buying one is a deliberate market-direction call, never an accident. An inverse ETF gapping *down* is information that the market is *recovering* — read it as macro context, not a momentum buy.

Leverage multiplies whatever edge is really there; it cannot manufacture one. On a noisy or marginal signal it just multiplies drawdowns and decay. Earn the right to leverage by first proving the edge is robust.
