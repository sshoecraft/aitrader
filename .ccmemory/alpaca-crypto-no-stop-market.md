---
name: alpaca-crypto-no-stop-market
description: 1.28.1: Alpaca has NO crypto stop-market. place_stop_order now auto-routes crypto to stop_limit (sell stop*0.995/buy stop*1.005). Trail crypto via mo…
metadata:
  type: project
tags: [alpaca, crypto, stops, broker, verified, constitution]
---

## The constraint

Alpaca supports NO naked stop-MARKET on crypto — only stop-limit. A plain
`StopOrderRequest` on a crypto symbol is rejected by the venue. (The bracket code
already knew this: `_place_crypto_bracket` / place_bracket_order comment "no naked
crypto stop-market".) Every live crypto stop in the account is `type: stop_limit`;
every stock stop is `type: stop`.

## What bit us (2026-07-04, journal 161)

The agent tried to trail its XRP stop 1.12 → 1.144 and hit a tool error.
`AlpacaBroker.place_stop_order` unconditionally built `StopOrderRequest` → crypto
rejection. And constitution step 9(c) told the agent to "use place_stop_order
(stop-market), NOT a stop-limit" — equity-correct, crypto-broken. Secondary trap:
trailing by PLACING A NEW stop for the full qty also fails — the coins are held by
the resting stop (`qty_available` ~0) → insufficient-quantity rejection.

## Fix (1.28.1)

- `alpaca.py place_stop_order`: `if is_crypto(symbol)` → route to
  `place_stop_limit_order` with limit = `stop*0.995` (sell) / `stop*1.005` (buy),
  same convention as `_place_crypto_bracket`. Caller's `stop_price` untouched;
  order reads `stop_limit` on reconcile. Mechanical venue adaptation, no strategy
  (cf. [[alpaca-tif-case-insensitive]] tif GTC-coercion).
- Constitution 9(c): crypto carve-out — call `place_stop_order` there too (infra
  makes it stop_limit; that's correct, not a bug); MOVE any stop via `modify_order`
  on the EXISTING order, never a second stop.

## How to apply

- Crypto stops CANNOT be stop-market; they gap through unfilled (constitution
  step 11 already warns this — an off-hours crypto book is protected by the agent
  being AWAKE, not the stop). Don't "fix" the stop_limit type — it's the only
  option.
- Deploy: package change → `make build && install`; constitution → `make const`;
  broker MCP respawns from the installed package on agent restart
  ([[api-service-deploy-path]]). Related: [[crypto-hard-lessons-provenance]].
