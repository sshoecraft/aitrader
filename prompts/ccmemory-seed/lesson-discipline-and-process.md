---
name: lesson-discipline-and-process
description: Reconcile against the broker every wake; distrust apparent edge; an ack is not a fill; doing nothing is valid; live results override backtests.
metadata:
  type: reference
---

The broker is ground truth for positions and orders — never your journal, last-known state, or memory. Reconcile against it every wake, especially after any gap where you weren't watching: a position may have stopped, filled, or closed while you were away. When the broker shows something your notes can't explain, find the fill that caused it before acting. Individual broker responses still lie: a connection can read "healthy" yet reject every order, a position feed can return empty/stale, a cancel can ack "success" while the order stays armed. An intended exit is OPEN until the broker confirms it filled — the most dangerous exposure is the one you think is closed and stopped watching. (A flatten that never fired held positions overnight unnoticed; "cancelled" stops that stayed live built an account-sized overnight short.) Treat any documented bug or constraint as a hypothesis to re-verify live, not settled fact — a stale false belief poisons every later decision. Make retries safe: re-check ground truth so a retry neither double-acts nor assumes success.

Watch exits on their own clock; never gate them behind entry attention. When fully invested, "nothing to buy, no cash" can blind you to what you should be closing — exactly when an intended exit gets skipped.

Distrust any apparent edge by default. Most of what looks like edge is survivorship bias, levered beta, transaction cost, or small-sample noise. A survivor-only universe manufactured a fake 1.34 Sharpe / 47% CAGR and inverted the low-vol premium. More return at equal-or-worse Sharpe is levered beta, not skill. A single composite score/confidence number correlated ~zero (sometimes negatively) with realized P&L — form your own thesis from what the tape and context show, never defer to a packaged number or a long checklist.

Out-of-sample is the only honest test: a 0.944-AUC in-sample classifier gave -12.6% forward alpha. One good window is a hypothesis, not durability. Small samples are noise (one DOGE trade flipped 10 of 19 metrics). When live and backtest disagree on the same instrument, LIVE WINS — backtest alpha that contradicts fills is an artifact (crypto topped backtests yet lost ~$8.9k live). Match horizon, instrument, and account to the decision; a tactic good in stocks can invert in forex.

Win rate isn't the goal — expectancy is; protect winners-run-larger asymmetry. Segregate P&L from broken execution before learning from it. Doing nothing is a valid decision; cash is a legitimate position — but an empty book empty because the thesis fails is a signal to rethink, not health.
