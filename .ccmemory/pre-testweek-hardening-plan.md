---
name: pre-testweek-hardening-plan
description: Hardening: DONE Fri — auto-pull 1.37.0, last-trade-ts + IBKR phantom-limit + list-wrappers 1.37.1, resolver/HISTORY/branch verified live. OPEN: vLLM…
metadata:
  type: project
tags: [hardening, test-week, checklist, experiment, 1.37.1]
---

# Pre-test-week hardening — status as of Fri 2026-07-10 ~10:20 CDT

Test week Mon 7/13–Fri 7/17; review timing is the owner's call. Owner collapsed the "weekend
list" into DO IT NOW — nearly everything shipped during Friday's dress
rehearsal.

## DONE (verified live where possible)
- ccloop wedge fix: INSTALLED both nodes (markers in site-packages; bin shim
  greps show nothing — that's just the entry-point stub).
- transactions_read on IBKR: ledger populated (19 rows incl. reasons).
- 1.36.4 order-id resolver: VERIFIED IN PRODUCTION (gemma's AMD modify 541→545
  succeeded with its mangled id; 2 more modifies after).
- itrader branch execution: exited NVDA @204.05 at the open per plan; later
  META entry (70 @ 667.32) carried the FIRST HISTORY line (zero-rows form ✓);
  stopped out 662.90 (-$309) and wrote a post-mortem + saved its own lesson
  memory (trailed into noise pre-breakout — its error, its diagnosis).
- Anti-churn: gemma refused AMD and ORCL re-buys after stop-outs, citing churn.
- 1.37.0 AUTO-PULL (owner design): argless get_all_snapshots() chained to
  step 0; get_type_snapshots for targeted refresh; constitution step 0/3(a).
- 1.37.1: last_trade_ts CSV column (stale-open-prints filterable by fact);
  ibkr normalize_order phantom-limit fix (lmtPrice only when TYPE has one);
  ALL 14 list-returning MCP tools wrapped {count, key: [...]}
  ([[mcp-list-results-render-per-element]]).
- Both nodes: 1.37.1 + constitution 19,687 B, fresh sessions 10:15 CDT.
  VERIFY NEXT CYCLES: step-0 argless call adopted; survey tables with numbers;
  wrapped shapes consumed cleanly.
- NFS incident (~08:15–10:00): /src export lost all_squash→root server-side;
  restored by owner. Lesson: a writability probe is not "repair finished" —
  confirm with the owner after an outage before writing. Also: bare `make
  install` ships the newest EXISTING dist wheel — use make world/full.

## OPEN
- vLLM gemma parser char-drop root cause (dropped hex char broke order ids):
  prepare patch NOW, but restarting vLLM = killing atrader's brain — restart at
  market close with owner go. Resolver defends order-ids meanwhile.
- COMMIT the tree (owner's explicit word required) — everything 1.33→1.37.1 is
  uncommitted; today's NFS scare happened with no VCS safety net.
- B (book-level HISTORY on entries) and C (concentration step): owner decisions
  still open; legal until Sunday-night freeze.
- Weekend: crypto-only soak watch (atrader), itrader idle-wake behavior;
  Sunday night: declare final freeze (constitution/text now effectively final).
Related: [[constitution-minimal-experiment]], [[order-id-mangling-prefix-resolver]],
[[crypto-volume-venue-only]], [[snapshots-stale-latesttrade-guard]].
