---
name: ibkr-session-close-modern-format-parse-bug
description: 1.49.6/ibkr.py 1.5.1: session_close_from_gateway mis-parsed IBKR's modern liquidHours date-stamped close, reporting stock open ~4.5h past the real 16…
metadata:
  type: project
tags: [ibkr, session-gate, market-schedule, get_available_types, itrader, live-bug]
---

## Symptom (2026-07-13, live)

Owner watching itrader: "its 4:25pm CT and it still shows equities open."
Pulled itrader's actual `get_available_types` tool_results straight from its
session transcript (not trusting the claim at face value): confirmed live at
**20:54:03 UTC (16:54 ET — 54 minutes past the real 16:00 ET close)** it
returned `{"stock": true, ...}`. itrader's `extended_hours` is never enabled
for this instance — never passed as a kwarg at the `IBKRBroker(...)`
construction site in `broker_server.py` (constructor default `False`) — so
`stock` should have flipped `false` the instant the session left `regular`.
This was not an extended-hours labeling nuance; it was wrong.

## Root cause

`session_close_from_gateway` (`aitrader/brokers/ibkr.py`) reads SPY's
`liquidHours` string from IBKR to compute today's real session close, which
feeds `market_session_now`'s `now < close_utc` check. It had its OWN
bespoke, slice-based parser assuming the LEGACY IBKR format
`YYYYMMDD:HHMM-HHMM` (date stated once). IBKR's actual current format is
`YYYYMMDD:HHMM-YYYYMMDD:HHMM` (a second date stamp on the close side too) —
already documented in this repo (`docs/broker-ibkr.md`) as the format the
SIBLING function `class_windows_from_gateway` (forex/futures) was written
to handle, via a shared `parse_trading_hours` regex-based helper.

Under the modern shape, the buggy parser's `close_part = last_window.split
("-")[1]` lands on `"20260713:1600"` (the CLOSE side's date+colon+time), and
`hh, mm = int(close_part[:2]), int(close_part[2:4])` reads `hh=20, mm=26`
(from the leading "2026" digits) instead of the real `16:00`. Reproduced
exactly in a throwaway test: old parser computed `2026-07-14T00:26:00Z`
(20:26 ET) vs. the correct `2026-07-13T20:00:00Z` (16:00 ET) — a 4h26m
overshoot, matching the live symptom's magnitude precisely.

Why only the stock path had this bug: `class_windows_from_gateway`
(forex/futures) was built using the shared `parse_trading_hours` helper from
the start. `session_close_from_gateway` (stock, via SPY liquidHours) was
older/separate and never migrated to it when the modern-format handling was
added for the other asset classes — same "two paths for the same
underlying string format, only one got the fix" shape worth watching for
elsewhere in this file.

## Why itrader's own trading wasn't directly endangered, but the bug still mattered

itrader's own journal narrative the SAME cycle correctly said "Post-close"
despite receiving `stock: true` from the tool that cycle — the model's own
judgment (knowing 4pm ET closes the session) already discounted the wrong
signal, and IBKR itself would separately reject/queue a plain regular-hours
order outside RTH regardless of what this flag said. But relying on a
smart model to silently route around a broken fact is not a fix, and a
weaker model (atrader/gemma) has no track record of reliably catching this
kind of implicit contradiction (see [[agent-must-be-guided-not-unguided]]
and the various gemma tool-call fragility memories this session already
touched). The constitution's step 2 ("Call `get_available_types`... Don't
assume market hours — use the tool") exists precisely so the model doesn't
have to independently re-derive session boundaries — a broken tool defeats
that design even when a capable model compensates.

## Fix (1.49.6 / ibkr.py 1.5.1)

`session_close_from_gateway` rewritten to call the SAME shared
`parse_trading_hours(det.liquidHours, det.timeZoneId or "US/Eastern")`
helper `class_windows_from_gateway` already uses — one parser for both call
sites instead of two. Finds the window whose local start-date (in the
contract's own reported timezone) matches `target_date`, returns its
`end_utc`. `None` (unmatched date / gateway-confirmed CLOSED) behavior
preserved exactly.

Verified via a throwaway script (`/tmp`, not committed): reproduces the
bug with a synthetic modern-format liquidHours string (not real IBKR
data) — old parser wrong by ~4.5h, new parser correct; legacy
`YYYYMMDD:HHMM-HHMM` format still parses correctly (backward compatible);
a gateway-confirmed `CLOSED` date and a date with no matching entry both
still correctly return `None`. Could NOT exercise the live
`reqContractDetailsAsync` round-trip itself — `ib_async` isn't installed
in this source-tree checkout (it's an optional extra, only pulled in via
`--broker ibkr`, see [[aitrader-ibkr-extra-ib-async]]) — so this verifies
the parsing logic exhaustively but not the live gateway call. Deploy is
owner-run; not yet deployed as of this writing.

## Verification still needed (post-deploy)

Watch itrader's `get_available_types` cross the 16:00 ET close on a live
cycle and confirm `stock` flips to `false` promptly (not ~4.5h later).
Also worth spot-checking `get_market_session()` returns `extended` (not
`regular`) in that same window, and — separately, lower priority — whether
`class_windows_from_gateway` (forex/futures, which never had this bug)
still behaves identically post-fix (it wasn't touched, but worth a glance
since it's the sibling that motivated the fix's shape).
