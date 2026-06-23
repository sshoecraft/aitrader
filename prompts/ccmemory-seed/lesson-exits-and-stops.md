---
name: lesson-exits-and-stops
description: Anchor exits to thesis-invalidation (structure), not arbitrary distance; verify every stop is live at the broker and reconcile each wake
metadata:
  type: reference
---

Most damage comes from managing the position after entry, not from being wrong on entry. You reason your way to every stop, every exit, every hold-vs-flatten call. There is no numeric gate, no mandatory stop — a fixed stop-loss rule was added here and reverted because a rule you didn't reason to is the failure mode.

**Place the exit where the thesis is proven wrong** — below the structural level (base low, support, pullback low) whose break means the setup failed — not at a round distance from entry. A stop inside the instrument's normal noise gets hit by random wiggle, not by being wrong: a post-mortem of 131 stop-outs ($51K loss, 21.5% win rate) found the stops sat well inside the daily range and ~80% of names recovered within days — closed for a loss right before the recovery. But don't widen to rescue a bad entry: a 5%-stop replay netted ~-$50K, bleeding harder on the ~68% that kept falling than it saved on those that recovered. If the honest invalidation point is too far to risk, the trade is wrong-sized or wrong-timed — decline it or size down. Match room to the instrument and regime (a stop sane on equities sits inside normal FX chop); a tight leash only earns its keep when there's real follow-through. Ratchet stops up, never back down.

**An exit only protects if it is live at the broker and fills.** A computed trail of $51.02 that never reached the broker left the live stop stuck at $49.20 for days and surrendered most of a $4,700 gain (stale order-id, silent cancel/replace failure). Verify the intended stop is the one resting now; prefer broker-side protection that survives your loop being down. A resting stop does not survive a gap — overnight/weekend price can open well past it, so the real risk you carry is the full distance to wherever it reopens.

**An intended exit is not done until the broker confirms the fill.** Reconcile your model against the broker every wake; the broker is ground truth. The worst exposure is one you think is closed but never confirmed. When unsure whether your own close order is still working, prefer the recoverable error — don't re-send a duplicate that can flip a long into an account-sized short (6/08 KLAC, 6/10 SPY zombie stop). Re-attempting a close must be a safe no-op once already done.

**Match the exit to why and how long you're in.** Exit horizon must match entry horizon: a patient trend stop is catastrophic on a single-session trade, and flattening a multi-day breakout intraday throws away the continuation (a +85% breakout collapsed to +10% under same-day exits). Whether to flatten before the close follows the thesis purpose, not a blanket policy — but don't panic-sell an intact thesis into an exogenous shock (selling 6/10's panic would have sold the bottom). Mean-reversion needs a profit-taking exit; a trail that ratchets faster than the move cuts winners small while losers run full.

**Don't over-manage open profit.** Removing a tight give-back ladder moved one SPY study from +5.83% to +39.56% — premature exits churn spread and re-expose to a fresh stop. Let it breathe early, shorten the leash as profit grows and the move stalls (idle capital has opportunity cost). When you scaled in, reckon from blended cost, not first entry — adds lift your true break-even, and an exit below blended cost means your conviction was wrong.

**Exits redistribute outcomes; they cannot create edge.** Every take-profit tested on a negative-edge entry stayed net-negative even as win rate rose to 69%. When bleeding, ask first whether the leak is *what* you trade, not *how* you exit; removing the worst slice of the universe beats any exit tuning.
