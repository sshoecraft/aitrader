---
name: ccloop-wedges-on-nonwall-api-error
description: FIXED (pending ccenv reinstall): ccloop now relays on a stale non-wall API-error turn via tx.last_api_error + CCLOOP_API_ERROR_GRACE (default 60s). W…
metadata:
  type: project
---

## Incident 2026-06-22 (atrader)

Live agent session-7 wedged **21 min** (19:54→20:15 UTC) after the model API
call timed out mid-turn ("API Error: The operation timed out."). The local model
endpoint couldn't reach Alpaca's backend; instead of recovering, the turn aborted
and the TUI sat idle until the user typed "hello?". Process stayed alive (`Sl+`).

## Root cause (was)

A generic API error fell between ccloop's two keep-alive mechanisms:
1. Context-wall relay matched `isApiErrorMessage` text **exactly `Prompt is too
   long`** → ignored "operation timed out".
2. keepgoing Stop hook fires only on a **Stop** event; an aborted turn emits no
   Stop → never fired.

So no relay, no re-prompt → indefinite wedge.

## Fix (implemented 2026-06-22, in /src/ccenv/ccloop — NEEDS ccenv reinstall + `systemctl restart aitrader` to go live)

- `transcript.py`: new `last_api_error(path)` — returns the error text iff a
  **non-wall** `isApiErrorMessage` turn is the **last real turn** (newer
  assistant/user/tool turn ⇒ None, so a retried-past blip is ignored;
  mode/permission-mode/last-prompt aux records don't count as turns).
- `runner.py` watcher (`run_session_interactive`): third relay trigger — tracks
  how long the SAME error has sat at the tail (wall-clock, not mtime) and relays
  once it persists `api_error_grace` s. Reuses the proven wall relay path;
  `_build_prompt` reads resume.md with NO model call, so recovery works even
  mid-outage (cycles/recovers instead of wedging).
- Knob `CCLOOP_API_ERROR_GRACE` (default 60, 0=off). Docs in README + DESIGN.md.
- Tests added in tests/test_transcript.py (validated inline; pytest not installed
  on this host).

Layer 2 (broker side) already OK: `brokers/alpaca.py connect()` wraps all 3
clients in `enforce_http_timeout` (bounded timeout + GET connect-retry).

Related: [[runtime-ccloop]] [[agent-state-stores-and-clean-relaunch]] [[runtime-no-headless-p-tmux]]
</body>
