---
name: survey-prev-session-liquidity-columns
description: 1.50.0: delayed_sip's dailyBar rolls ~15min INTO the session → 12,968/12,968 stock rows blank on volume pre-market; agent invented "sub-penny=uninves…
metadata:
  type: project
tags: [survey, liquidity, delayed_sip, broker-mcp, snapshot]
---

## The trap (re-derived twice already — don't do it a third time)

The survey feed is `delayed_sip` (1.37.3). Its snapshot `dailyBar` **only rolls to today ~15 MINUTES INTO
the session** — it's a 15-min delayed tape, so before that it serves the PRIOR session's bar. Therefore
`bar_is_today` in `snapshot_type_to_csv` is False for the ENTIRE universe through every pre-market survey,
and the 1.48.1 guard (correctly) blanks `day_volume`, `day_notional`, `rel_vol`, `day_open/high/low` and
every derived range field.

**Measured 2026-07-16: 12,968 of 12,968 stock rows had blank day_volume.** Still only 47.5% of a 400-name
sample had rolled 17min after the open. Feed proof at 13:44 UTC: NVDA dailyBar `delayed_sip`=2026-07-15
(v=125,734,825, a FULL prior day) vs `iex`=2026-07-16 (v=239,012, partial). It rolled at 13:46.

## Why it mattered — the agent's "sub-penny = uninvestable" was a SYMPTOM

With every liquidity column blank pre-market, `pct_1d` is the only usable lens exactly when the agent forms
its morning watchlist. Raw %-move ranking surfaces sub-penny names, with no fact to judge tradeability by —
so the agent filled the hole with the only column left: price (journal id 464 GATE-rejected EOSER +86.6% as
"sub-penny, uninvestable"). **Price is not liquidity, and the proxy is backwards in BOTH directions:**
EOSER $0.0425 traded **$2.2M** the prior session; XOCT **$39.71** traded **$36.8k**; EVLVW (+438%) $0.007
traded **$3.9k**. It rejects the liquid name and passes the illiquid ones.

Lesson that generalizes: when the agent invents a crude proxy rule, look for the FACT it's missing before
"fixing" the reasoning. Its heuristics are downstream of its data.

## Fix (1.50.0)
`prev_volume` / `prev_notional` columns = the completed prior session's units + dollars traded
(`prev_close × prev_volume`; stock/crypto only — futures need the multiplier, forex has no venue volume).
Read off whichever bar IS the previous session's, mirroring how `prev_close` already chooses: `prevDailyBar`
once rolled, else `dailyBar`. Never blank pre-market — that session is over. Pure DATA per CLAUDE.md §2.
They're valid `by`/`lenses` automatically (`by` validates against the CSV's columns) and ride in every mover
(a mover carries the whole row).

## Don't
- **Don't "fix" this by buying a feed.** Pre-market there is no today-bar on ANY feed at any price — the
  session hasn't started. `delayed_sip` is doing its job (NVDA 4.8M vs IEX 283k ≈ 6% keyhole) — keep 1.37.3.
  Also: `sip` SILENTLY returns IEX data on this account (identical numbers) — verify, never assume.
- **Don't make `min_volume` fall back to prev_volume.** It floors on TODAY's volume, so pre-market
  `excluded.min_volume == universe` — that's the floor, not a dead tape. Left as-is deliberately: the agent
  journals the floors it used, and a floor whose basis shifts with the clock makes that record ambiguous.
- **Don't use the IEX feed to judge liquidity.** It's a ~1-6% keyhole. Reading EOSER off iex gives "$235
  traded today / 139-share last trade"; the consolidated truth is $1.84M and a 50,000-share print. This
  error was made live in-session. Always pass `feed='delayed_sip'` for volume questions.

## Testing without touching production
Shim `bs.settings` to a temp `state_dir` + patch `b.get_tradeable_assets` to a few symbols + set
`bs.broker = lambda: bs.build_data_broker()` (Alpaca-only). `broker()` builds the IBKR EXECUTION broker —
it burns a clientid lease and can fail/disturb the live trader ([[broker-clientid-lease]]). Related:
[[snapshot-csv-stale-dailybar-rollover-fix]], [[survey-feed-delayed-sip]], [[snapshot-day-range-pct-column]],
[[deploys-are-owner-run]].
