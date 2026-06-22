---
name: heat-observability
description: /status heat (per-position + per-class aggregate) is display-only observability for the shared UI, NOT a budget/gate — keep it on infra side.
metadata:
  type: project
tags: [api, heat, boundary, status]
---

## What

`aitrader/api.py` `/status` returns heat (added v0.9.0): a top-level `heat`
aggregate (`total_heat`/`stock_heat`/`crypto_heat`/`forex_heat`/`futures_heat`/
`position_count`) plus a real per-position `heat`, all as fractions of equity.
Computed in `enrich_positions_with_heat(positions, equity)`.

Formula (risk-at-stop ÷ equity), per position:
- **no live protective stop** → at-risk = `|market_value|` (full downside; IBKR
  `marketValue` already embeds the futures multiplier, so it's true notional for
  every asset class → no stop = max heat).
- **live stop** → at-risk = `|market_value| × max(0, dist_to_stop)/current`,
  floored at 0 (a stop locked in profit is not downside risk).

Stops come from `enrich_positions_with_protective_orders`; class buckets from
`asset_types.classify_symbol(...).value`.

## Why this is NOT a constitution violation (CLAUDE.md §2 "heat budgets" / §8 risk engine)

The §2 prohibition is on heat *budgets* — a gate/cap that constrains a decision —
and on porting the rejected risk engine (§8). This is neither:
- **Display-only.** It's read by the trader-ui HeatPanel (human dashboard). The
  agent NEVER reads :7099 — it acts through MCP tools. So it cannot bias cognition.
- **Mechanical, not opinion.** Same class as the existing `to_stp` distance and
  sector enrichment — factual arithmetic over broker truth, no threshold/score.
- The agent still owns ALL sizing and risk. Nothing here limits it.

Why the API and not the UI: the UI is **shared** with the trader engine
(:7000/:7001), which populates the same panel from its risk engine. Each engine
satisfies the contract in its own `/status`; engine-specific UI branching was
rejected. Decided with the user 2026-06-16.

## How to apply

- Do NOT turn this into a gate/cap or feed it to the agent — that would cross the
  boundary. If extending, keep it observability-only.
- Do NOT "remove it as a violation" — it was a deliberate, user-approved call.
- Related: [[no-biasing]], [[api-service-deploy-path]] (deploy = make build+install
  +restart aitrader-api; /src edits are not live).
