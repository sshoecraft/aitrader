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

## State stores & clean wipe

To scrub or audit what the running agent "knows," there are **four** distinct
persisted stores — the journal is not the only one:

1. **Trading journal** — `~/.local/state/aitrader/journal.db` (SQLite). Edit/
   delete rows in place (never `rm`+recreate — see docs/journal-mcp.md's
   operational-hazards note); the API `/journal` reads this.
2. **Agent ccmemory** — `~/.local/share/aitrader/run/.ccmemory/*.md` (one fact
   per file + a derived `index.db` cache — delete the cache to force a clean
   rebuild after editing/removing a `.md`). This is the AGENT's ccmemory,
   separate from the dev project's `/src/aitrader/.ccmemory`.
3. **ccloop relay handoff** — `~/.local/share/aitrader/run/.ccloop/runs/<run-id>/resume.md`.
   This is what seeds every relaunch: ccloop builds the next session's prompt
   as `preamble + resume.md`. `session-N.prompt` files are inert debug records
   of past prompts — only `resume.md` feeds future sessions.
4. **Built-in auto-memory** — `~/.claude/projects/-home-aitrader--local-share-aitrader-run/memory/*.md`,
   used as a fallback only when the run dir's ccmemory isn't wired.

**Load-bearing fact for a clean wipe.** On a *graceful* session end ccloop
**re-summarizes the live transcript into a new `resume.md`**; a **SIGTERM/kill
PRESERVES** the existing `resume.md` without re-summarizing. So to truly remove
something from the agent's future inputs: `systemctl --user stop aitrader` →
scrub all four stores (including `resume.md`) **while the process is dead** →
`systemctl --user start aitrader`. Editing files under a *live* session gets
undone by the next graceful re-summarization, and the live session's in-context
memory can't be scrubbed at all — only a fresh relaunch drops it.

## Deploying a change

The running services import the **INSTALLED** `~/.local` package, not `/src` —
editing `/src/aitrader` and restarting a service does nothing until a build+
install lands the change. What to run depends on what changed:

- **Constitution-only change** (`prompts/constitution.md`): `make const` (or
  `./install.sh`) rewrites the run-dir `CLAUDE.md` and the data-dir copy. An
  already-running session keeps its loaded prompt until the next fresh session
  (ccloop relay on context-fill) or a service restart.
- **Package/code change** (broker/journal/API/MCP server code): `make build &&
  make install` (builds a wheel, force-reinstalls to `~/.local`), **then
  restart the affected service(s)** — a build+install alone does not restart
  anything.

The broker and journal MCPs are **stdio children of the agent process**, so
they only pick up a new install on an **agent restart**
(`systemctl --user restart aitrader`) — safe when the market is closed; ccloop
reconciles from broker + journal on relaunch either way. The dashboard API is
its **own** systemd service (`aitrader-api`, a separate IBKR client — id 80 —
independent of the agent's client-id pool) and needs its own explicit restart
(`systemctl --user restart aitrader-api`); the Makefile's `restart`/`full`
targets only touch `aitrader.service`, not `aitrader-api`.

## Status (2026-06-15, v0.3.0)
Built and installed. MCP servers handshake from the installed `~/.local` scripts.
**Not yet proven end-to-end under ccloop** — a bounded ccloop smoke (DONE-able
criteria) to confirm ccloop loads the run-dir files and drives a cycle is the
next verification, before first light. ccloop config knobs are documented in
`/src/ccenv/ccloop/README.md`.
