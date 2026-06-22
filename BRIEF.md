# Autonomous AI Trader — Founding Design Brief

> This is the canonical founding mandate for the project. `CLAUDE.md` is its
> operational distillation; if the two drift, reconcile them. This is a design
> mandate, not an implementation. Do **not** import, port, or imitate any prior
> deterministic trading system (`/src/trader`). Read "Hard Boundary" before
> writing a line.

---

## 1. Mandate

Build a **persistent autonomous AI trader** for a paper account. The AI (you,
running continuously) is the **entire decision-maker**. Everything else is
infrastructure: connectivity, data, a clock, memory. The AI decides what to
look at, what to trade, when, how much, when to exit — by reasoning, not by
calling pre-written logic.

There is **no screener, no scoring engine, no signal generator, no strategy
module, no rules pipeline**. If a decision is being made, the model makes it.
If something is being *fetched, stored, placed, or timed*, infrastructure does
it. That is the only division of labor in this system.

## 2. Hard Boundary — Infrastructure vs. Cognition

This is the load-bearing rule. Violating it rebuilds the thing we are
deliberately not building.

**Infrastructure (allowed as tools/scripts).** Dumb, deterministic, opinion-free
primitives. Each one answers a factual question or performs a mechanical action.
None of them contains a threshold, a ranking, a buy/sell opinion, or anything
that could be called "a strategy."

- **Broker / execution:** connect, account snapshot, list positions, list/get
  orders, place market/limit/stop/stop-limit order, modify order, cancel order,
  list fills/executions. Raw primitives only.
- **Market data:** historical bars for a symbol, current quote/snapshot, the
  list of tradeable symbols for an asset class. A *list* of what exists — never
  a ranked or filtered shortlist.
- **Clock / lifecycle:** is the market open right now, next open/close, half-day
  awareness, and `sleep_until(t)` / `wake_after(seconds)` so the agent can hand
  the wait back to the runtime. Pure time facts plus the sleep mechanism.
- **Memory / state:** read and write the agent's own journal and durable notes;
  read/write the positions-of-record reconciliation store. A notebook, not a
  state machine.
- **Compute sandbox:** an execution environment (Python/bash) so the agent can
  compute *whatever* it wants from raw bars — an indicator, a regression, a
  backtest of its own idea — on the fly. The sandbox is infrastructure; what it
  computes is the agent's choice.
- **Web/search:** for news, filings, macro context. Already native to Claude.
- **(Optional) chart render:** turn bars into an image so the agent can look at
  price action visually. A rendering primitive, not an analysis.

**Cognition (NEVER a tool/script — the AI does this itself by reasoning).**

- Screening or filtering the universe down to candidates.
- Ranking, scoring, or "confidence" numbers.
- Entry/exit signals, indicators-used-as-gates, pattern detectors that emit
  decisions.
- Position sizing formulas, heat budgets, allocation rules baked into code.
- Anything named after "a strategy."

If you find yourself about to write a function that *decides*, stop. That
decision belongs in the agent's reasoning, the prompt, or a skill — not in code.

**Skills vs. tools.** Skills are how-to *guidance* the agent reads and applies
with judgment (e.g., "morning routine," "how I think about an exit"). They are
prose playbooks, not deterministic scripts, and the agent is free to deviate.
Tools are the infrastructure primitives above. Neither encodes a fixed strategy.

## 3. The "Always On" Problem (the one real constraint)

An LLM agent executes in discrete turns. It cannot literally think nonstop.
"Running 100% of the time" is implemented as a **runtime harness** that holds
the agent in a perpetual act-loop and never tears it down during operating
hours. The harness contains **zero trading logic** — it is a runtime, like an
OS scheduler.

Continuity of *cognition* comes from three infrastructure mechanisms:

1. **Session continuity / compaction** — long-lived session, resumed across
   restarts; context compacted as it fills.
2. **Durable journal** — the agent's own notebook (what it's watching, theses,
   why it entered/exited). Read at the top of every cycle. This is the real
   memory; context is just scratch.
3. **Reconciliation against broker truth** — at the top of every cycle re-read
   positions/orders/fills from the broker. The broker is the source of truth for
   *what is*; the journal is the source of truth for *why*. Makes crash-and-
   relaunch completely safe.

**Cadence is a decision, the wait is a mechanism.** The agent ends every cycle
by telling the harness when to wake it: `wake_after(60)` while actively
managing, `sleep_until("09:25 ET")` overnight, `sleep_until(next_open)` on a
closed day. The agent owns *when*; the harness owns *how to sleep*. Nothing in
the harness ever decides whether or what to trade.

## 4. One Cycle

1. **Reconcile** — account/positions/orders/fills from broker; read journal.
2. **Orient** — market, news, P&L, session/time.
3. **Decide** — *all cognition.* Survey the universe (no screener), form theses,
   decide entries/exits/sizing, use sandbox + web. Doing nothing is valid.
4. **Act** — place/modify/cancel via primitives, with a client id / tag.
5. **Journal** — what it did and *why*, and what it's waiting for.
6. **Set next wake** — `wake_after` / `sleep_until`; yield to harness.

## 5. State & Idempotency

- Broker is source of truth for positions/orders. Reconcile every wake.
- Journal/notes hold intent and rationale.
- Every order carries a deterministic client id / tag (no double-submit).
- All times UTC internally, display ET. Real tz library, never hardcoded.

## 6. Guardrails as Fuses, Not Strategy

Any hard limit must be a **fuse** (protects the account from a runaway loop),
never an opinion on a trade. Candidates: kill switch, hard notional ceiling per
order, buying-power ceiling, paper-only enforcement. Dumb absolute bounds, not
risk logic.

## 7. Reuse vs. Clean-Room

Reusable (pure plumbing, no cognition): a broker abstraction of pure primitives;
a market-calendar resolver; DB/journal storage plumbing. Leave behind entirely:
screeners, scoring, entry/exit methods, "strategies," the LLM-reviewer pipeline,
indicator-gates. If in doubt, clean-room it.

## 8. Build Sequence

1. Tool server first, against paper. Verify each primitive in isolation.
2. Harness loop. Perpetual act-loop, session resume/compact, sleep/wake,
   reconcile-on-wake, optional fuses. Drive with a trivial stub agent.
3. The agent's mandate. System prompt / constitution + first skills (guidance,
   not logic).
4. Run paper, observe, refine the prompt/skills — never by adding decision code.

## Appendix A — Infrastructure First Pass

### A.1 Reuses cleanly from old `/src/trader` (infrastructure only)
- The `db_*` query layer (trades / decisions / equity-snapshot via `get_db()`) →
  trimmed journal subset. **Drop the `reviews` table.**
- The `Broker` ABC and driver method bodies (place/get_bars/get_snapshot/
  get_session_close/get_available_types/…) — pure primitives.
- `market_calendar.py` — broker → exchange-calendar-library → fallback resolver.

### A.2 Must NOT come over (cognition/opinion)
- `check_risk_limits` (11-check risk engine). Only a dumb fuse allowed.
- `compute_order_prices` (stop/TP/R:R defaults). Agent computes its own stops.
- Screeners, scoring, strategies, reviewers, indicator-gates.

### A.3 The one real extraction job: broker connection ownership
The old broker drivers assume the engine's Command module owns the IBKR
connection and pumps `wait()`. The old `mcp.py` doesn't connect — it HTTP-
proxies the engine on localhost:7000. The standalone broker MCP must **own its
own connection**: instantiate connection/pool, run the `wait()` pump in its own
thread, handle reconnect. Then every driver method body is reusable as-is. This
is the bulk of the first-pass work — mechanical, not conceptual.

### A.4 First-pass MCP decomposition
1. **broker MCP** (exec + data, standalone connection — the §A.3 job): account,
   positions, orders, place/modify/cancel, fills, bars, snapshot, tradeable-
   universe, plus broker time facts (`get_market_session`, `get_session_close`,
   `get_available_types`). Point at the IBKR paper account.
2. **scheduler MCP** (pure blocking-wait): `wait_until_market_open`,
   `wait_until(iso)`, `wait_until_session_close`, `wait_seconds(n)`,
   `wait_for_fill(order_id, timeout)`. No calendar of its own — reads the
   broker's time facts and blocks until the condition. Issues one tool call; the
   tool doesn't return until the condition is met; the session resumes.
3. **journal MCP** (trimmed `db_*`): durable notebook + positions-of-record for
   reconcile-on-wake.

The compute sandbox (bash/Python) and web search are native to Claude Code.

### A.5 Phase-0 exit criterion
A stub agent, harness-driven, that each wake reconciles account/positions/orders
from the broker MCP, writes a journal entry, and calls the scheduler MCP to
sleep until the next open or N seconds — and survives restart by reconciling from
broker truth. When that loop runs unattended for a full session with no brain,
the infrastructure is done and the agent's mandate goes on top.
