---
name: claude-code-2.1.212-mcp-auto-background-breaks-sleep
description: 2.1.212 auto-backgrounds any MCP call >2min (gate tengu_mcp_auto_background, default 120000ms), defeating scheduler wait_* sleep; fix = CLAUDE_CODE_M…
metadata:
  type: project
tags: [scheduler, mcp, wait, claude-code, 2.1.212, auto-background, sleep, settings-json, ccloop, 1.51.1]
---

# Claude Code 2.1.212 MCP auto-background breaks the scheduler sleep (2026-07-17)

## Symptom
atrader/itrader agents stopped sleeping: `wait_seconds` showed up as a
backgrounded **"MCP task"** (e.g. `MCP task ktga45rj (scheduler/wait_seconds)
completed`) running concurrently while the agent made ~32 other tool calls
during what should be downtime. The agent's own narration rationalized it
("timer still running in the background") — a confabulation. It was busy-looping
through the ccloop keepgoing nudge, burning context and hitting the broker
mid-"sleep".

## Root cause (verified, not inferred)
Claude Code **2.1.212** is the first build that wires MCP-tool auto-backgrounding.
Decompiled gate (from the installed binary):
```
threshold_ms =
  clamp(env CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS, 0, 2147483647)  // if env set; 0 => disabled
  120000                                                        // else if gate tengu_mcp_auto_background ON (default true)
  0                                                             // else
  // also: 0 if type-excluded, or (isNonInteractiveSession && !CLAUDE_AUTO_BACKGROUND_TASKS)
```
Any MCP call running **>2 min** (`$cy=120000`) is moved to a background task
instead of blocking the model's turn. The scheduler `wait_*` tools ARE long
blocking calls — the block IS the agent's sleep (BRIEF §A.4.2). Backgrounded,
they no longer suspend the agent.

Evidence it is genuinely NEW in 2.1.212 (not a remote-gate flip on old code):
- Gate literals `tengu_mcp_auto_background` / `tengu_mcp_tool_auto_backgrounded`
  = **0 occurrences in 2.1.210 and 2.1.211, present only in 2.1.212**. (The env
  var NAME was a dormant placeholder in 210/211 — misleading; the wiring is 212.)
- History cross-check: on 2026-07-11 a 2-hour wait died at exactly **1800s**
  (the idle-abort). Impossible if a 2-min auto-background were active then — it
  would have backgrounded at 2 min. So auto-background was dormant Jul 11, live
  Jul 17. Binary built Jul 16 19:28; Claude Code auto-updates ~daily and keeps a
  rolling versions/ set under `~/.local/share/claude/versions/`.

## Three INDEPENDENT client limits on one MCP call — keep them straight
1. **Idle timeout** (no progress): stdio default 30 min. Defeated by the 60s
   `ctx.report_progress` heartbeat (scheduler 0.4.0 / pkg 1.41.1). KEEP IT.
2. **Auto-background** (NEW 2.1.212): default **2 min** wall-clock. This is what
   broke sleep. Disable with `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS=0`. The heartbeat
   does NOT help here — different limit.
3. **Wall-clock hard limit** (`MCP_TOOL_TIMEOUT` / per-server `timeout`): ~28h
   default. Only bites weekend-length single waits.

Only **interactive** sessions are exposed — the gate exempts
`isNonInteractiveSession` unless `CLAUDE_AUTO_BACKGROUND_TASKS` is set. The trader
runs the interactive TUI (tmux, subscription) by design, so it IS exposed; a
headless `-p` run would not be.

## Why ccloop made it a busy-loop (secondary)
Once backgrounded, control returns to the model → Stop hook fires. ccloop's
background-work gate (`keepgoing.py` `_pending_background_task_count`) only counts
a task whose `.output` is held open by a **live procfs writer** — that is
Bash-shaped. A backgrounded MCP call runs inside the long-lived stdio server, no
per-task writer, so the gate sees 0 → the keepgoing "pick a new angle" nudge fires
→ 32 tool calls. If auto-background is off, this never triggers. (Potential ccenv
hardening: teach that gate to also recognize live MCP tasks. Lives in
/src/ccenv/ccloop, a different repo.)

## Fix (deployed to source; live nodes hand-patched)
Out-of-band in the run-dir `.claude/settings.json` `env` block — the scheduler
server code is UNCHANGED (harness-behavior workaround, not a server bug):
```json
{ "model": "opus", "env": { "CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS": "0" } }
```
- **install.sh (1.51.1)**: idempotent `setdefault` merge of the env key after
  seeding settings.json — self-heals existing installs, preserves explicit values.
- **atrader + itrader**: hand-patched live 2026-07-17 (backup at
  `settings.json.backup`); takes effect on each node's next ccloop relaunch (no
  restart forced — service restarts stay owner-run).
- **Makefile `run-dir` target (`Makefile:102`)**: got the SAME merge (1.51.1) —
  this is the writer `make install`/`world`/`full` actually use (install.sh and
  the Makefile are duplicated, independent seeders). Verified via `make -n
  run-dir`. Edited with explicit owner approval (standing rule: don't touch the
  Makefile unless told).
- **Durability**: this is version-driven, and Claude Code auto-updates — pin the
  env var (done) rather than relying on a version. A future build could also flip
  the `tengu_mcp_auto_background` remote gate independently.

## Verify after any deploy
One `wait_*` >2 min returns `woke_reason: condition_met` IN PLACE, with NO
`MCP task … completed` notification and no keepgoing "pick a new angle" during it.

Related: [[scheduler-wait-1800s-progress-heartbeat]], [[runtime-no-headless-p-tmux]],
[[deploys-are-owner-run]], [[aitrader-deployment-topology]].
