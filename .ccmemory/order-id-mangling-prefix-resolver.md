---
name: order-id-mangling-prefix-resolver
description: 1.36.4: gemma drops chars from long UUIDs (AMD stop ...c5700→...c700, position unmanageable all night); modify/cancel/wait_for_fill now resolve by un…
metadata:
  type: project
tags: [vllm, gemma, order-id, uuid, tolerance, broker-mcp, 1.36.4]
---

# Order-id mangling → unique-prefix resolver (1.36.4, deployed 2026-07-10 pre-open)

## What happened
Overnight 07-09→10, gemma (atrader) tried to RAISE its AMD stop 541 → 545 to lock
a gain — unprompted self-directed trailing under the minimal constitution, the
behavior the experiment hopes for — and infra failed it. It passed
`b2751323-…-4aeb0d5c700` (11 hex in the last group) for the broker's real
`…-4aeb0d5c5700`: ONE character dropped. `modify_order` AND `cancel_order`
rejected it ("badly formed hexadecimal UUID string"); the wrong id then lived in
its journal tail and was re-used verbatim every cycle (it never re-read the id
fresh from get_orders — the templating force again). Net: the AMD position was
PROTECTED (stop resting broker-side, verified `new` at Alpaca) but UNMANAGEABLE —
no modify, no cancel, and a market exit would bounce on stop-reserved qty.

Same family as [[vllm-gemma-trailing-backtick-lastarg]] and
[[vllm-gemma4-quotefix-patch]]: the local model/parser corrupts long string args.
Diagnosis method: `sudo -H -u atrader python3 -c "from aitrader.api import broker;
…list_all_open_orders()"` → compare the broker's real id to the journal's.

## The fix (tolerance in infra — [[mcp-tools-tolerate-comma-strings]] philosophy)
`broker_server.py resolve_order_id()`, applied in `modify_order`, `cancel_order`,
`wait_for_fill`:
- strip parser junk: backticks/quotes/trailing dots;
- fuzzy-resolve ONLY ids that are UUID-shaped ("-") or the journal's bare
  hex-prefix display form (`b2751323...` — contains a–f, can never be an IBKR
  integer id);
- exact match wins; else UNIQUE first-group-prefix (≥8 chars) match against
  live `list_all_open_orders()`;
- ambiguous/unknown ids pass through untouched (broker reports the real error);
  all-digit ids are NEVER fuzzed (IBKR int id "35" must not resolve to "356").
8-case standalone test exercised incl. the exact AMD string.

## Also observed in the same journal read (for the 07-18 review)
- The 1.36.3 taint repair WORKED: "PASS (Low volume/conviction)" is dead; crypto
  passes now cite conviction, not venue volume.
- NEW EROSION: the step-3 survey table degraded to one prose line ("Checked top
  movers (names)") — no path·count, no %moves. Names drift cycle-to-cycle (so
  pulls look real) but the forced artifact is gone from the journal. Do NOT fix
  mid-week (would be mid-experiment enforcement); review-day item.
- Gemma held while AMD kissed the stop (541.07 vs 541.00) and let the stop do
  its job — correct behavior, stated plainly.
