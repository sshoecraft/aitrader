---
name: scheduler-wait-1800s-progress-heartbeat
description: 1.41.1: Claude Code aborts MCP calls silent 1800s — every wait >30min died; agent self-clamped to 1790s "leashes". Fix = 60s report_progress heartbea…
metadata:
  type: project
tags: [scheduler, mcp, wait, timeout, 1800s, heartbeat, 1.41.1, claude-code]
---

# Claude Code 1800s idle watchdog kills long scheduler waits → 0.4.0 heartbeat port (2026-07-11)

## The finding (live transcript, atrader session 34d61a17, Sat 7/11)
Seven aborts in one session: `MCP server "scheduler" tool "wait_seconds" sent no
response or progress for 1800s; aborting.` Concretely off the wire:
- 16:43Z `wait_seconds(7200)` → killed at exactly 1800s (17:13Z).
- 17:13Z `wait_until(+90min)` → killed at exactly 1800s (17:43Z).
- The model then SELF-CLAMPED: `wait_seconds(1799)` → condition_met; `1800` →
  completed once at 1800.0009s then aborted the next time (exact-1800 races the
  watchdog — coin flip); settled on `1790` repeatedly. Its journal wrote
  "maintaining 30-minute leash" as if it were judgment — it was the harness
  ceiling. The constitution's earned ~2h weekend leash was structurally
  unreachable, and each abort fed the model an error turn mid-loop (noise that
  compounds gemma's templating drift).

## Root cause + fix
The Claude Code client (≥2.1.x) aborts any MCP tool call with no response AND no
progress notification for 1800s. Our waits slept silently (1s asyncio chunks, no
pings). The predecessor repo diagnosed this identically (its session_state.md §8)
and fixed it in its scheduler 0.4.0 — but the fix NEVER CROSSED THE REBUILD; the
current repo's scheduler was 0.3.0, byte-identical except for the missing fix.
1.41.1 ports it verbatim: `_sleep_until` emits `ctx.report_progress` every
`PROGRESS_PING_SECONDS` (60s); `ctx: Context` FastMCP-injected into all four wait
tools (model-visible schemas unchanged); a report_progress raise is swallowed so
a missing progressToken can never break the wait. Compile-verified; pre-port copy
at `aitrader/mcp/scheduler_server.py.backup`.

## Deploy + verify (OWNER-run — [[deploys-are-owner-run]])
- Needs a PACKAGE deploy: `make world`/`make full` + restart aitrader. `make
  const` does NOT ship MCP code.
- Verify: one >30-minute wait returning `woke_reason: condition_met` in the
  transcript; journal cadence free to exceed 30min again.
- Alternative belt-and-suspenders the abort message itself suggests: a per-server
  `"timeout"` (ms) on the scheduler entry in `~/.claude.json` — not needed once
  the heartbeat is live.
- When grading journal cadence at any review, remember: pre-fix
  "30-minute leash" language and erratic wake intervals were watchdog artifacts,
  not agent choices.
- **1.42.3 retirement:** the agents' own cap lessons
  (`wait-seconds-1800s-abort` on itrader, alias `wait-seconds-idle-timeout`)
  are now listed in `prompts/ccmemory-seed/RETIRED` and purged from every
  node's run-dir store by BOTH `./install.sh` and `make const` — a stale copy
  anywhere re-imposes the dead ~1700s ceiling (itrader was observed doing
  exactly that on 7/11; owner hand-deleted its copy, manifest guards the rest).
  Related: [[constitution-minimal-experiment]],
  [[runtime-ccloop]], [[aitrader-deployment-topology]].
