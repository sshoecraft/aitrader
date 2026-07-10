---
name: survey-feed-delayed-sip
description: 1.37.3: survey CSVs now pull feed=delayed_sip — FREE full consolidated tape 15-min delayed (NVDA 74M vs IEX 2.9M ≈ 4%); live quotes stay real-time IE…
metadata:
  type: project
tags: [alpaca, data-feed, delayed-sip, survey, iex, 1.37.3]
---

# Survey feed = delayed_sip (1.37.3) — the free fix for the IEX keyhole

## The problem (owner escalated: "THIS IS A MASSIVE FAILURE")
Free Alpaca plan = real-time IEX only ≈ 2-4% of consolidated volume. Verified
live: NVDA 2.9M (IEX) vs 70.9M (consolidated, Yahoo). Effects on the survey:
volume floors lied (16 "liquid" names at a 1M IEX floor), "traded today" =
printed-on-IEX (6,989 of 12,737 mid-session), stale opening prints, mega-cap
bias in the movers menu → contributed to the NVDA monoculture. The docstring's
`day_volume > 1_000_000` example was calibrated for consolidated tape — with
delayed_sip it is now correct again.

## The discovery
The SAME free plan includes the FULL consolidated tape 15-min delayed:
`feed=delayed_sip` (alpaca-py DataFeed.DELAYED_SIP, SDK ≥ ~0.43). Verified
against the live account: latest-trade 15:13 vs 15:28 real-time; snapshot
dailyBar NVDA 72.1M / NOK 28.6M / VOD 12.4M. Real-time consolidated (sip)
remains 403 (the $99/mo Algo Trader Plus tier — the no-compromise upgrade if
the 15-min lag ever costs entries).

## The design (breadth stale, actions fresh)
- `alpaca_survey_feed` setting (default delayed_sip) used ONLY by
  snapshot_type_to_csv for STOCK pulls — the whole-tape survey CSVs.
- Single-symbol get_snapshot/get_bars/entries/stops stay REAL-TIME on
  alpaca_data_feed=iex. This matches agent practice: survey the file, verify
  live before acting (opus literally journals "verified live").
- resolve_feed(name=None) maps iex|sip|delayed_sip; get_stock_snapshots(feed=)
  silently falls back to the configured feed on 403/subscription errors
  (verified live: blocked sip → IEX, no exception). IBKR/MYSE get_snapshots
  accept-and-ignore `feed`.
- Crypto unaffected (Alpaca's own venue — see [[crypto-volume-venue-only]]).
- SDK also exposes feeds 'overnight' (Blue Ocean) and 'boats' — future option
  for overnight-session marks. Related: [[alpaca-data-feed-iex-default]],
  [[snapshots-stale-latesttrade-guard]].
