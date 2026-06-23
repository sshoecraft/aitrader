---
name: lesson-execution-and-cost
description: Judge edge NET of realistic cost; high-turnover needs a far bigger edge; a freshly placed order at status:new/filled_qty:0 is NORMAL, still working.
metadata:
  type: reference
---

Judge every edge NET of realistic execution cost, never gross. Backtests flatter by assuming clean fills at the touched price and ignoring slippage, commission floors, and auction costs — real results come in reliably worse, and a live paper run landed BELOW the friction a clean sim assumed. Treat any backtest headline as an optimistic upper bound; be most skeptical of one that only barely clears its hurdle.

Friction scales with how often a thesis forces you to transact, so high-turnover ideas need a far larger edge to survive. A daily round-trip strategy pays the toll every day and it compounds — one decomposed to ~55pp of pure cost-compounding loss on a near-zero gross edge. Multiple genuinely-real statistical signals (overnight tilt, sector rotation, turn-of-month) were uninvestable once realistic auction costs were charged. By contrast a monthly-rebalanced signal barely moved across a wide cost sweep: for low-turnover holdings cost is nearly irrelevant, so if such a strategy looks bad, the SIGNAL is bad, not the cost assumption. "Real in the data" and "worth trading" are separate questions — don't let the first answer the second.

IMPORTANT — a freshly placed order showing status:new with filled_qty:0 is NORMAL and still working, not a failed or broken fill. Alpaca paper fills GRADUALLY against the IEX feed, so a just-placed order (and a resting stop sitting at status:new) is the engine working as intended — wait and re-read fresh broker state rather than treating the non-fill as broken and resubmitting. Re-issuing a duplicate is the asymmetric mistake: a pending state self-heals, an accidental short does not.

Don't open a position without runway to clear its own round-trip cost before you'd be forced out — opening just before a known exit window pays spread for essentially no shot at edge. And if the whole edge lives in a specific fill mechanism (an open/close auction), fill reliability IS part of the edge — verify the broker dependably fills that order type before trusting paper results.
