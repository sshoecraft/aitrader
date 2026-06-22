# Runtime — ccloop

The aitrader runtime is **ccloop** (`/src/ccenv/ccloop`), not a custom harness.
(An earlier hand-rolled `aitrader/harness/loop.py` was deleted at v0.3.0.) **Zero
trading logic** — ccloop is a relay loop; all cognition is the agent's.

## Why ccloop
- **Never-stop is enforced, not requested.** ccloop's `Stop` hook re-feeds the
  model whenever it tries to end its turn, against a success criteria that never
  completes. Prompt prose ("never stop") is unreliable; a hook is not.
- **Fresh session on context-fill, not compaction.** When the context window
  fills, ccloop summarizes the transcript and hands off to a fresh session.
  Compaction loses granularity; relay preserves it.

## How it's wired (all native Claude Code — survives every relay)
ccloop runs `claude` in the **run dir** `~/.local/share/aitrader/run/`. Claude
Code auto-loads, every session including each relay:
- `CLAUDE.md` — the constitution (source: `prompts/constitution.md`)
- `.claude/settings.json` — the model (`{"model": "opus"}`)
- broker/scheduler/journal MCP servers — registered at **user scope** in
  `~/.claude.json` (→ `~/.local/bin/aitrader-*-mcp`), so they attach in every
  session regardless of cwd. `make run-dir` merges them in; there is no run-dir
  `.mcp.json`.

ccloop's two args (`criteria` + `task`) and `ccloop_cutoff` (--cutoff) come from
**settings.toml** (not files). The `aitrader` launcher (`aitrader/launch.py`)
reads them, chdirs to the run dir, and execs ccloop.

## Responsibilities split
| Concern | Owner |
|---|---|
| Never-stop, context relay, crash relay | ccloop |
| Sleep / cadence between cycles | scheduler MCP (blocking `wait_*` inside a session) |
| State continuity across relays | journal + broker reconcile (ground truth); ccloop summary is a bonus |
| Model | run-dir `.claude/settings.json` |
| Kill switch | `sudo systemctl stop aitrader` (option a) |

## Invoke (all via the `aitrader` launcher)
- Service (always-on, headless): `systemd/aitrader.service` is
  `ExecStart=.../aitrader` (no args). `sudo systemctl enable --now aitrader`;
  logs `journalctl -u aitrader -f`.
- Interactive: `aitrader` (configured run, resumes latest), or
  `aitrader "<criteria>" "<task>"` (ad-hoc fresh run).
- **Resume:** with no args the launcher scans `<run_dir>/.ccloop/runs/` and
  `--resume-run <latest>` if a prior run exists — so a reboot/restart continues
  the same run instead of starting over. Fresh only when there is no prior run.

## Status (2026-06-15, v0.3.0)
Built and installed. MCP servers handshake from the installed `~/.local` scripts.
**Not yet proven end-to-end under ccloop** — a bounded ccloop smoke (DONE-able
criteria) to confirm ccloop loads the run-dir files and drives a cycle is the
next verification, before first light. ccloop config knobs are documented in
`/src/ccenv/ccloop/README.md`.
