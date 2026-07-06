---
name: stop-verify-must-check-order-status
description: 1.32.3: a pending_cancel/canceled order is NOT a stop; step 9 MATCH/VERIFY were status-blind → MSFT naked 4 days reported "protected". Now a status-a…
metadata:
  type: project
tags: [constitution, stops, protect, alpaca, pending_cancel]
---

# Stop verification must check ORDER STATUS, not just (symbol,side,qty)

## The failure (found 2026-07-06)
MSFT sat NAKED ~4 days while the agent reported it protected every single cycle:
`STOPS: MSFT: 386.00 (ID: f41f7112... pending cancel)`. It bled entry 389.89 → 384 (−$400), straight through the 386 the "stop" was set at, which never fired.

## Root cause — two stacked failures
1. **Mechanical (Alpaca):** the 07-02 386 stop was cancelled and the cancel JAMMED in `pending_cancel` (the 42210000 bug — can't cancel via API). While `pending_cancel` it **reserved all 76 shares** → `qty_available=0` → any replacement stop is rejected for insufficient qty. Boxed in.
2. **Cognitive (the real bug):** step 9(b) MATCH tested only `(symbol, side, qty)` and 9(d) VERIFY only "shows an order id" — both **status-blind**. The dying `pending_cancel` order matched, so the agent counted it as its stop and NEVER placed a replacement (no `insufficient` rejection in the journal — it never even tried). Being prose, it collapsed to a one-line "STOPS:" summary instead of a rigorous per-position check.

The order later resolved to `canceled` (freeing the shares), so when found MSFT was truly naked AND placeable.

## Fix (1.32.3, deployed)
- **9(b) MATCH → a FORCED TABLE** (the proven [[constitution-trail-forced-table-9e]] pattern), one row per position, cells read off `get_orders`, with a STATUS column + WORKING? YES/NO. Protection counts ONLY if status ∈ {new, accepted, held, resting partially_filled}. **pending_cancel / pending_replace / canceled / replaced / rejected / expired / filled = NOT protection → treat as NONE, place fresh.** Names the real MSFT case in-text.
- **9(c)** blocked-shares edge: if a replacement is rejected because a stale pending_cancel reserves the shares (`qty_available` < position qty) → write `NAKED — BLOCKED by stuck order <id>`, retry every cycle, never report protected.
- **9(d) VERIFY** requires seeing a WORKING stop's id; naked/blocked stated plainly.
- Manually placed the missing stop: `sl_msft_20260706_1` @ 380.50 (under 07-06 session low 381.33), order `a054da8d`, status `new`.

## Lesson
"Has an order id" ≠ "is protected." Any stop check must read the order's STATUS and treat a non-working status as NO protection. General doctrine reconfirmed: prose/summary checks get a hollow pass; only a forced table with tool-read cells binds the local model. See [[constitution-enforce-via-step-not-column]], [[constitution-steps-not-prose]], [[alpaca-crypto-no-stop-market]] (Alpaca stop quirks).
