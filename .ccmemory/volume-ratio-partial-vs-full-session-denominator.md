---
name: volume-ratio-partial-vs-full-session-denominator
description: 2026-07-20: trader AND atrader both cried "extremely low volume" mid-session — data correct in both; rel_vol / 0.3x-gate divide today-so-far by a FUL…
metadata:
  type: project
tags: [volume, rel_vol, snapshot-csv, false-alarm, opex, ibkr-bug]
---

## Partial-session volume ÷ full-session denominator = permanent "low volume" until midday

**2026-07-20 ~12:10 ET.** Owner reported trader (/src/trader) AND atrader (/src/aitrader) both flagging "extremely low volumes" 1.5–2.5h into the session. Two independent codebases, same symptom, so it looked like a shared data outage. It was not a data bug — both compute an apples-to-oranges ratio.

### Verdict: volume data is CORRECT in both systems

atrader survey CSV `prev_volume` (Fri 7/17) vs Yahoo consolidated truth:

| sym | survey CSV | Yahoo | match |
|---|---|---|---|
| SPY | 63,539,939 | 62,569,200 | 101.6% |
| NVDA | 145,165,814 | 144,033,900 | 100.8% |
| AAPL | 63,926,090 | 63,365,300 | 100.9% |
| TSLA | 31,700,697 | 31,317,100 | 101.2% |

`delayed_sip` is working; the silent 403-fallback at `alpaca.py:840-851` did NOT fire. trader's logged numbers likewise match Yahoo (AAL 41.1M logged vs 46.5M Yahoo slightly later; WBD 4.1M/4.24M; ULCC 941K/1.00M) — its bars default `feed = DataFeed.SIP` (alpaca.py:875-876), so full tape.

### The mechanism (identical in both, arrived at independently)

- **atrader** — `broker_server.py:756`: `rel_vol = dvol / prev_v` = today-so-far ÷ prior **FULL** day.
- **trader** — LLM reviewer gate: today-so-far ÷ **20-day full-day average**, hard reject under **0.3x**.

At 21–24% of the 390-min session elapsed, a normal stock reads 0.16–0.34x. Observed: SPY 0.162, NVDA 0.176, AAPL 0.213, TSLA 0.336. Yahoo-verified normal-pace names read the same: AAL 0.29x, WBD 0.20x, ULCC 0.24x. **trader's 0.3x gate therefore rejects nearly the whole universe every morning until ~midday** — a clock artifact, not a liquidity fact.

### Aggravating factor: the denominator day was monthly OPEX

Fri 2026-07-17 was the third Friday = July monthly options expiration, the highest-volume day of the month. SPY 62.6M vs Thu 7/16's 46.4M (+35%). So atrader's `rel_vol` denominator was inflated ~35% above a normal session on top of the partial/full mismatch. Any Monday after monthly OPEX will reproduce this.

Today was genuinely a bit light (SPY 15.5M by 12:09 ET = 33% of a normal 46.4M day at 41% elapsed ≈ 75-80% of normal pace) — light, nowhere near "extreme."

### Fix direction (infra, not cognition)

Normalizing by time-of-day is pure arithmetic on facts — legitimate infra under §2, same justification as `day_range_pct` (1.49.5). Options:
- add `session_elapsed_pct` to the survey CSV so the ratio is interpretable;
- or add a time-of-day-normalized `rel_vol_tod` = today-so-far ÷ prior day's volume **through the same clock time**.

Do NOT "fix" it by moving trader's 0.3x threshold — that just relocates the artifact.

### Separate real bug found en route: IBKR dailyBar volume is garbage

itrader (:5503) `/snapshot/{sym}` returns nonsense volumes — SPY `v`=14,161,412,402,938 (1.4e13), NVDA 3.5e12, AAPL 2.05e13 — and `prevDailyBar.v` = 0.0 always. Unrelated to this report (it reads absurdly HIGH so nobody flagged it), but IBKR-sourced volume is currently unusable. Needs its own fix.

### Trap: the dashboard `/snapshot/{symbol}` endpoint is IEX by design

`api.py:659` → `b.get_snapshot()` uses `alpaca_data_feed` (= "iex"), ~3% of consolidated tape (SPY Fri 2.01M vs 62.6M real = 3.2%). Only the survey path (`broker_server.py:673`) passes `alpaca_survey_feed` = delayed_sip. Reading volume off the dashboard will always look catastrophically low and is NOT evidence of a feed failure.
