# aitrader — Persistent Autonomous AI Trader

> This file is the project constitution. It is the operational distillation of
> the Founding Design Brief (`BRIEF.md`). When the two disagree, fix one of them
> — they must not drift. Read `CHANGELOG.md` for build history, `.ccmemory` for
> durable status/decisions/topology, and `docs/` for per-subsystem detail.

## 1. Mandate (one sentence)

A persistent AI agent (Claude, running continuously) is the **entire
decision-maker** for a paper trading account. Everything in this repo is
**infrastructure** — connectivity, data, a clock, memory, a runtime. The agent
decides what to look at, what to trade, when, how much, and when to exit **by
reasoning** — never by calling pre-written decision logic.

## 2. The Hard Boundary (load-bearing — violating it rebuilds what we reject)

**Infrastructure (allowed as tools/scripts).** Dumb, deterministic, opinion-free
primitives. Each answers a factual question or performs a mechanical action.
None contains a threshold, ranking, buy/sell opinion, or "strategy."

- Broker/execution: connect, account, positions, orders, place/modify/cancel,
  fills. Raw primitives only.
- Market data: bars, quote/snapshot, the *list* of tradeable symbols, and
  FACTUAL market-structure rankings the exchange/data vendor publishes — top %
  gainers/losers, most-active-by-volume. Those are DATA (a fact about price and
  volume, like a quote), not an opinion, and the agent still decides what to do
  with them. What stays forbidden is a shortlist ranked or filtered by EDGE or
  QUALITY — a score, a confidence number, an indicator-gate, a buy/sell signal,
  anything that decides what is *good*.
- Clock/lifecycle: is-open, next open/close, half-days, `wait_*` (sleep).
- Memory/journal: read/write the agent's notebook + positions-of-record.
- Compute sandbox: bash/Python so the agent computes *whatever it wants* from
  raw bars. The sandbox is infra; what it computes is the agent's choice.
- Web/search (native to Claude). Optional chart render.

**Cognition (NEVER a tool/script — the agent does this by reasoning):**
screening/filtering the universe BY EDGE OR QUALITY, scoring/confidence numbers,
entry/exit signals, indicator-gates, position-sizing formulas, heat budgets,
anything named after "a strategy." (Ranking by a raw market FACT — % move,
volume — is data, not cognition; that's the movers feed above. The line: rank by
a *fact* = infra; rank by an *opinion of edge* = the agent's job.)

> If you are about to write a function that **decides**, STOP. That decision
> belongs in the agent's reasoning, the constitution prompt, or a skill — not in
> code. If tempted to "just add a quick filter in code," that IS the failure
> mode. Put it in the prompt instead.

**Skills vs tools.** Skills are prose how-to *guidance* the agent reads and
applies with judgment ("morning routine," "how I think about an exit"). Tools
are the infra primitives above. Neither encodes a fixed strategy.

## 3. Locked Decisions (§10 of the brief — answered 2026-06-15)

| Decision | Choice | Consequence |
|---|---|---|
| **Persistence** | Long-lived resumed session | One `claude -p` process stays alive; agent loops internally; harness relaunches with `--resume` + reconcile on crash. Auto-compaction handles context growth. |
| **Asset scope** | Multi-asset (stock/crypto/futures/forex) | Crypto is 24/7 → agent effectively never fully sleeps. Exercises the harness hardest. |
| **Fuses (§7)** | Paper-only enforcement ONLY | NO notional/buying-power caps — the agent owns ALL sizing. The broker adapter refuses non-paper accounts. (No HALT-file kill switch — stop the trader by exiting the session / `systemctl stop aitrader`.) |
| **Broker infra** | Reuse `Broker` ABC + IBKR method bodies; clean-room the connection | The §A.3 job: broker MCP owns its own connection + `wait()` pump + reconnect. |
| **Model** | Single model, NO tiering | User has Claude Max 5x — cost isn't a constraint, so no cheap-poll/escalate routing. Set in `settings.toml: model` (default `opus`); switch to **Fable** (`claude-fable-5`) when available. Don't add tiering. See memory `model-choice`. |
| **Cadence** | Agent-chosen, with two harness fuses | Hard floor (never wake faster than ~5s) + always-wake-at-each-open. |
| **Broker** | IBKR paper account | `secrets.toml: ibkr_port=4002` (paper gateway). |

## 4. Component Model

```
THE AGENT (Claude) — the entire brain: orients, reasons, decides, acts, journals,
                     owns universe selection / entries / exits / sizing / cadence
        ▲ never-stop + relay                      │ tool calls
  RUNTIME = ccloop (ZERO trading logic)    TOOL SERVER (MCP, ZERO trading logic)
  • runs `claude` in the run dir            • broker MCP  (exec+data, owns conn)
  • Stop-hook = never stops (no DONE)       • scheduler MCP (blocking waits = sleep)
  • context full → FRESH session (relay,    • journal MCP  (notebook + records)
    not compaction)                         • sandbox + web = native to Claude
                          │
                  Paper broker (IBKR) + data
```

The runtime is **ccloop** (`/src/ccenv/ccloop`), not a custom harness. It runs
`claude` in the **run dir** (`~/.local/share/aitrader/run/`), which natively
loads `CLAUDE.md` (this constitution) and `.claude/settings.json` (the model).
The 3 MCP servers are registered at **user scope** in `~/.claude.json` (so the
`aitrader` user has them in every session, cwd-independent — not via a run-dir
`.mcp.json`). ccloop's Stop-hook enforces never-stop
against a never-completing criteria; on context-fill it relays to a fresh
session (no lossy compaction). State continuity across relays = the journal +
broker reconcile (ground truth). Sleep/cadence = the scheduler MCP's blocking
waits. Kill switch = `systemctl stop aitrader`.

## 5. One Cycle (repeated forever during operating hours — *how* is the agent's judgment)

1. **Reconcile** — pull account/positions/orders/fills from broker; read journal.
2. **Orient** — market, news, P&L, session/time.
3. **Decide** — *all cognition lives here.* Survey the universe (no screener),
   form/revise theses, decide entries/exits/sizing, use sandbox + web. Doing
   nothing is a valid decision.
4. **Act** — place/modify/cancel via broker primitives with a deterministic
   client id / tag for idempotency.
5. **Journal** — what it did and *why*, and what it's waiting for.
6. **Set next wake** — `wait_*` based on how much attention the situation needs.

## 6. State & Idempotency (invariants)

- **Broker is source of truth** for positions/orders. Reconcile every wake; never
  trust journal over broker.
- **Journal holds intent and rationale** — the things the broker can't tell you.
- **Every order carries a deterministic client id / tag** so a relaunched agent
  recognizes its own in-flight orders and never double-submits.
- **All times UTC internally, display ET.** Use a real tz library — never
  hardcoded offsets (half-days + DST will bite).

## 7. How cognition is driven (ccloop runtime)

The runtime is **ccloop** — `ccloop "<criteria>" "<task>"` run from the run dir
(by `systemctl` for always-on, or the `aitrader` wrapper / raw `ccloop`
interactively). ccloop launches `claude`, and Claude Code natively loads the run
dir's `CLAUDE.md` + `.claude/settings.json` plus the user-scope MCP servers from
`~/.claude.json` — so the constitution, tools, and model attach to every session
including each fresh relay. ccloop's
Stop-hook re-feeds the model whenever it tries to stop (the criteria never
completes), and on context-fill it summarizes → fresh session (not compaction).
Within a session the scheduler MCP's `wait_*` tools **block** until the wake
condition (that's the agent's sleep). We use ccloop because "tell the model not
to stop" via prose is unreliable, and fresh-session relay preserves granularity
that compaction loses. Decisions/rationale: see memory `runtime-ccloop`.

LOCAL-DISK invariant: everything runs from `~/.local` (bin) + the run dir +
`~/.local/share/aitrader` — NEVER from `/src` (NFS; a mount outage must not take
the trader down). `/src` is build-time only. Config: `settings.toml` (no env vars).

## 8. What must NEVER be ported from /src/trader

`check_risk_limits` (11-check risk engine), `compute_order_prices` (stop/TP/R:R
defaults), EDGE/strategy screeners, scoring, strategies, reviewers, indicator-gates. Do not
import or read them "for reference" — they encode the exact inversion we reject.
(A FACTUAL movers feed — top % gainers/losers, most-active by volume — is NOT in
this list: it ranks by a raw market fact, not by edge, and is allowed infra per §2.
A `rank_gainers`-style %-move ranking is fine *as data*; `bandwagon_reviewer` or any
edge-scoring / indicator-gate that decides what is *good* is not.)
Only genuinely-infra plumbing reuses (Broker ABC, IBKR method bodies, market
calendar resolver, db query plumbing trimmed to a journal subset).

## 9. Project Hygiene

- Update the local tree first; any remote mirror syncs *from* local.
- Maintain `CHANGELOG.md` (with rationale). Capture durable status, decisions,
  and topology in `.ccmemory` — there is NO separate state doc.
- Before working on a module, check for its `docs/<module>.md`; after changing
  it, create/update that doc.
- Rev version: patch=fix, minor=feature, major=major change.
- python3 always. Temp files in /tmp, never the project dir. No mock/fake data.
