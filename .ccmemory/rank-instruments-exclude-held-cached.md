---
name: rank-instruments-exclude-held-cached
description: 1.49.4: rank_instruments' exclude_held re-fetched broker.get_positions() every call; IBKR's recover_portfolio retry made itrader's calls 3-9s. Cached…
metadata:
  type: project
tags: [broker_server, rank_instruments, ibkr, performance, get_positions, itrader]
---

## Symptom (2026-07-13)

Owner: "for itrader the rank instruments call is taking a VERY long time
eacht ime." Measured from itrader's own session transcripts (matched each
`tool_use` to its `tool_result` by id, diffed timestamps): ~21% of
`rank_instruments` calls took 3-9s against a typical ~0.1s. No correlation
to `asset_type` or CSV size — 1-2KB forex/futures CSVs were slow just as
often as the 1.4MB stock CSV, ruling out CSV parsing/row count as the cause.

## Two independent contributors found

1. **Host contention (owner-resolved, not aitrader's to fix):** clyde was
   running 25+ `qemu` test VMs + `worldserver` + atrader's vLLM workers,
   swap 100%/8GB full. EVERY MCP tool (including `ccmemory`/`journal`, which
   share no code with the broker) showed the same ~17-18s stall ceiling on
   20-45% of calls — a host-level symptom, not tool-specific. Owner cleared
   this before the code fix below.
2. **`rank_instruments`'s `exclude_held` re-fetches broker positions on
   EVERY call (the actual code bug, fixed here):** both `rank_snapshot_csv`
   (single-lens) and `_rank_multi_lens` called `broker().get_positions()`
   fresh every invocation to build the held-symbol exclusion set — not once
   per cycle, once per call. THE LOOP's step 3 makes 2 `rank_instruments`
   calls per open type (floorless + floored), so 4-8 calls/cycle across
   stock/futures/forex, each independently exposed. IBKR's `get_positions()`
   can fall into `recover_portfolio()` (`ibkr.py`) whenever `ib.portfolio()`
   returns momentarily stale/empty (`ib_async` cache-lag quirk) — retries up
   to 5×`await asyncio.sleep(1.0)` once `GrossPositionValue >= $1000`.
   itrader currently holds ~$40k (VLO+XOM), so that gate was live. Alpaca's
   `get_positions()` is a plain REST call, no retry loop — why atrader never
   showed this.

## Fix (1.49.4)

`aitrader/mcp/broker_server.py` 0.10.2 → 0.10.3: added `_held_symbols()`, a
60s-TTL cache used ONLY by `rank_instruments`'s two internal call sites
(`broker_server.py` ~line 871, call sites ~912/~1012). Deliberately scoped
narrow — the public `get_positions` MCP tool (RECONCILE, order-fill
confirmation — see [[stop-verify-must-check-order-status]] and the
constitution's "Broker is source of truth" invariant) was left untouched and
still always calls live, so nothing safety-critical can see stale data. A
minute-stale held-set can only affect whether an already-held name is ALSO
shown as a ranking candidate — never an order, fill, or position record.
`recover_portfolio()`/IBKR sync logic itself was NOT touched — it's correct
for RECONCILE; this only stops paying its cost redundantly from a
candidate-ranking filter that doesn't need millisecond-fresh positions.

Verified via a throwaway script (`/tmp`, not committed — stub broker +
synthetic CSV, testing MY caching control-flow, not fabricating trading
data): 5 rapid calls → 1 broker round-trip (was 5); `exclude_held` still
excludes the correct symbol; cache expires and re-fetches correctly past the
TTL; `exclude_held=False` still bypasses the broker entirely, unchanged.

No test suite exists in this repo (checked — no `tests/` dir anywhere
outside `build/`), consistent with this project's live-verification culture
rather than unit tests; the throwaway script is the only verification and
was not preserved.

Deploy is owner-run (build+install+restart) — prepared in `/src/aitrader`
only, not yet deployed as of this writing. Docs: `docs/broker-mcp.md`
("Universe snapshot for self-survey" section) and `CHANGELOG.md [1.49.4]`.

## Verification still needed

After the owner deploys: re-run the same tool_use/tool_result timestamp-diff
analysis on itrader's next several sessions and confirm `rank_instruments`'s
slow-call rate drops from ~21% toward near-zero (a residual few percent is
expected — the FIRST call after the 60s TTL expires each cycle still pays
whatever `recover_portfolio` costs that one time).
