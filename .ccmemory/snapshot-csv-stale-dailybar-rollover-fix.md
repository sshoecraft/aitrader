---
name: snapshot-csv-stale-dailybar-rollover-fix
description: 1.48.1: snapshot_type_to_csv paired live latestTrade with a dailyBar that hadn't rolled to today (near-miss fabricated breakout); fixed via bar_is_to…
metadata:
  type: project
tags: [snapshots, get_all_snapshots, broker_server, data-quality, stale-bar, 1.48.1, alpaca]
---

# Stale dailyBar paired with a live price — fix 1.48.1 (2026-07-13)

## Symptom (near-miss, caught by the agent before an order)
An `itrader` session almost sized/ordered a fabricated "tanker breakout"
2 minutes after the open. The fabrication AGREED with a real fundamental
(VLCC rates ~doubled) so it read as confirmation, not noise. Only caught
because `prev_close` in the survey CSV didn't match Friday's close from a
separate `get_bars` call.

## Root cause
Alpaca's snapshot `dailyBar` rolls to the new session on a symbol's FIRST
*consolidated* print of that session, not at the bell. A CSV written ~2 min
post-open catches most of the universe still on the PRIOR session's
`dailyBar`/`prevDailyBar` while `latestTrade` is already live (including
extended-hours prints). `snapshot_type_to_csv` paired live price against the
stale bar unconditionally:
- `prev_close` (`prevDailyBar.c`) landed ONE SESSION TOO FAR BACK (e.g. FRO
  CSV 36.56 = Thursday; correct Friday close was 38.11).
- `day_open/high/low/volume` carried the prior session's full-day range
  mislabeled as today's.
- On the observed snapshot (12,914 rows): `price > day_high` 6.2%,
  `price < day_low` 9.6%, `range_pos` outside `[0,1]` 14.3% (INSW's live
  pre-market 89.9999 vs Friday's high 88.54 → range_pos 1.28).
- `rank_instruments(fresh_only=True)` did NOT filter these out —
  `last_trade_ts` is the TRADE's date (genuinely "today" for a pre-market
  print), not the BAR's date. Checking the wrong field.
- Same family as [[snapshots-stale-latesttrade-guard]] (1.36.1, the OTHER
  direction: trade older than bar) but this is bar-not-yet-rolled while the
  trade IS fresh — the existing guard's condition (`lt_t[:10] < db_t[:10]`)
  does not fire here since the trade is newer, not older.

## Fix (`broker_server.py` 0.9.0 → 0.9.1, `snapshot_type_to_csv` row builder)
Compare the bar's own timestamp to today's date once per call
(`today_str = utcnow_iso()[:10]`), then per row:
```python
bar_is_today = bool(db_t) and db_t[:10] == today_str
if bar_is_today:
    day_o, day_h, day_l, dvol = db.get("o"), db.get("h"), db.get("l"), db.get("v")
    prev_c = pdb.get("c")
else:
    day_o = day_h = day_l = dvol = None      # today's range genuinely unknown
    prev_c = db.get("c")                     # db IS the correct previous close
```
Every derived field (`day_notional`, `rel_vol`, `pct_intraday`, `gap_pct`,
`range_pos`) already blanks itself once `dvol`/`day_o`/`day_h`/`day_l` are
`None` (existing truthy/`is not None` guards) — one branch fixes every
downstream column. `price > day_high` / `range_pos` outside `[0,1]` become
STRUCTURALLY IMPOSSIBLE: the bounding fields are blank whenever they aren't
genuinely today's. `last_trade_ts` needed no change — it already tracked
the PRICE's own provenance correctly; only the OTHER columns lacked that
discipline. `rank_instruments`'s `fresh_only` also needed no change: a
stale-bar row's ranked column is now either correct (`pct_1d`, `price`) or
blank, and blank already self-excludes via the existing `no_data` path —
fixing the source made the downstream compensating check unnecessary.

Docstring updated: untraded/not-yet-rolled names now read `pct_1d`=flat 0%
(price frozen at the still-valid prior close) with blank range columns,
not a stale prior-day move under a misleading "day_high"/"day_low" label.

## Cross-broker check (did NOT touch IBKR/MYSE code, verified reasoning only)
- **MYSE**: `dailyBar`/`prevDailyBar` are genuine last-2-daily-bars (same
  shape as Alpaca) — same latent bug, same fix applies, already covered by
  the shared row-builder.
- **IBKR**: `dailyBar.t` is really "last ticker update" (`ticker.time`), not
  a bar date, and IBKR already sets `prevDailyBar.c == dailyBar.c` (same
  `close` var reused for both) — so `prev_c` is IDENTICAL in both branches
  for IBKR rows regardless of `bar_is_today`; the only behavior change there
  is a no-tick-yet row showing blank instead of a confident `0.0` (strict
  improvement, not a regression).

## Verification
1. **Stubbed repro** (`broker()`/`settings()` monkeypatched, no live
   connection): reproduced the exact FRO/INSW numbers from the writeup.
   Fixed code: FRO/INSW `prev_close` correctly lands on Friday's close (not
   Thursday's), `day_high`/`range_pos` blank instead of impossible values;
   an already-rolled control row is untouched.
2. **Live** (real Alpaca, itrader's own paper creds via
   `build_data_broker()` directly — data-only, IBKR/execution never
   touched; output written to a scratch dir, never itrader's real
   `state_dir`/`snapshots_stock.csv`, so the live agent's universe file was
   never at risk of being overwritten/truncated): FRO/INSW/NVDA/MU/AAPL/SPY
   all came back with `day_low <= price <= day_high` holding for every row.
   Run was 33 min post-open so all 6 (liquid) names had already rolled —
   did not catch the exact race window live today (it's a 1-2 min-post-open
   phenomenon that had already passed), so this run validates the
   already-rolled path end-to-end against real data/shapes rather than the
   stale-bar branch itself; the stale-bar branch is confirmed via (1) and
   via reading the IBKR/MYSE snapshot code above.

## Deploy
Source-only edit in `/src/aitrader` — needs owner-run package build +
install + broker MCP restart to reach the live `itrader`/`atrader`
processes (see [[deploys-are-owner-run]], [[api-service-deploy-path]]).

## Process note
Verifying against real Alpaca required itrader's/atrader's actual
credentials, which live under `~/.config/aitrader/secrets.toml` on each
account (per `credentials.py`'s own docstring) — NOT under `/src` (build-
time only, per the LOCAL-DISK invariant). Owner explicitly directed
`sudo -u itrader`/`sudo -u atrader` for this; the verification script ran
AS itrader (`sudo -n -u itrader python3 ...`) so credential material was
loaded in-process by that user's own `aitrader.credentials` loader and was
never read or displayed by the assisting session directly.
