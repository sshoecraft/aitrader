---
name: modify-order-crypto-rounding-churn
description: 1.30.0: modify_order rounded crypto stops to 2dp (1.165→1.17) in BOTH brokers → hair-trigger full-position wick-out + panic re-buy. Fixed both. IBKR…
metadata:
  type: project
tags: [crypto, stops, alpaca, ibkr, modify_order, rounding, verified, go-live]
---

## The incident (2026-07-04, live Alpaca paper)

Agent trailed its XRP stop: `modify_order(stop_price=1.165)` (no symbol). Result
stop = **1.17**, 0.3% under a 1.1732 market → instant wick-out of ~25k XRP. Agent
misread the stop-out as a tool bug ("modify_order acted as a market sell — I
accidentally liquidated my position") and re-bought 25k @ ~1.178 (HIGHER), then
stopped out AGAIN at 1.165. Day P&L +$387 → ~−$1,100 on churn+fees.

## Root causes (all confirmed)

1. **Rounding — Alpaca:** `modify_order` rounded with `symbol or ""`. Agent omits
   symbol on trails → `round_price(1.165, "")` treats crypto as STOCK (2dp) →
   **1.17** (proven in-repl; `round_price(1.165,"XRP/USD")==1.165`).
2. **Rounding — IBKR (SAME bug):** `modify_order` had no crypto branch → crypto
   fell into `else: round(x,2)`. Latent (IBKR crypto = Paxos, live-only /
   untradeable on paper) but would bite at go-live. `round_price`/`pround` are
   ALPACA-ONLY; IBKR rounds inline per-branch — NO shared path, so crypto
   correctness must be fixed in EACH broker separately.
3. **Cushion:** even correct 1.165 (0.7% under) triggered stop-out #2 — crypto
   range makes a last-candle-low stop a hair-trigger. This is judgment, not code.

## Fixes (1.30.0)

- `alpaca.py modify_order`: look up the order's symbol when omitted → crypto 8dp.
- `ibkr.py modify_order`: crypto branch passes prices RAW (matches its own
  `place_stop_limit_order`), not round(x,2).
- `ibkr.py place_stop_order`: crypto sends a stop-MARKET — **UNVERIFIED on Paxos**
  (Alpaca has none → routes to stop-limit). GO-LIVE checklist: verify on a live
  IBKR crypto account; if rejected, route to stop-limit like Alpaca.
- constitution 9(e): crypto stops need far more room (swing low several bars back,
  never last candle). Related: [[alpaca-crypto-no-stop-market]], [[crypto-hard-lessons-provenance]].

## State

Agent HALTED (`systemctl --user stop aitrader`) during the fix. Code+constitution
deployed via make build+install (install redeploys the constitution via run-dir;
does NOT restart). Restart = `systemctl --user start aitrader`.
