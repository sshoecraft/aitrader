---
name: agent-state-stores-and-clean-relaunch
description: The aitrader agent persists state in 4 stores; ccloop relaunch seeds from resume.md and re-summarizes the live transcript on graceful exit, so a clea…
metadata:
  type: project
tags: [ccloop, runtime, journal, ccmemory, state, relaunch]
---

To scrub or audit what the running trading agent "knows," there are **four**
distinct persisted stores (the journal is NOT the only one):

1. **Trading journal** — `~/.local/state/aitrader/journal.db` (SQLite, table
   `journal`: id, ts(UTC), kind, symbol, body, tags). Edit/delete rows directly;
   back up first with `sqlite3 … '.backup …'` (WAL-safe). The API `/journal`
   reads this.
2. **Agent ccmemory** — `~/.local/share/aitrader/run/.ccmemory/*.md` (one fact
   per file + `index.db`). `index.db` is a derived cache (see its `.gitignore`) —
   delete it to force a clean rebuild after editing/removing a `.md`. This is the
   AGENT's ccmemory, separate from the dev project's `/src/aitrader/.ccmemory`.
3. **ccloop relay handoff** — `~/.local/share/aitrader/run/.ccloop/runs/<run-id>/resume.md`.
   THIS is what seeds every relaunch: ccloop builds the next session's prompt as
   `preamble + resume.md` (see `/src/ccenv/ccloop` DESIGN.md). `session-N.prompt`
   files are inert debug records of past prompts — only `resume.md` feeds future
   sessions.
4. **Built-in auto-memory** — `~/.claude/projects/-home-aitrader--local-share-aitrader-run/memory/*.md`
   (used as a fallback when the run dir's ccmemory `CCMEMORY_DIR` wasn't wired).

**ccloop relaunch semantics (load-bearing for a clean wipe):** on a *graceful*
session end ccloop **re-summarizes the live transcript → new resume.md**; a
**SIGTERM/Ctrl-C kill PRESERVES** the existing resume.md without re-summarizing
(verified 2026-06-16 — `systemctl --user stop aitrader` preserved it). So to
truly remove something from the agent's future inputs you must:
`systemctl --user stop aitrader` → scrub all 4 stores (incl. resume.md) **while
the process is dead** → `systemctl --user start aitrader`. Just editing files
under a live session is undone by re-summarization, and the live session's
in-context memory can't be scrubbed at all — only a fresh relaunch drops it.

**Principle applied here (2026-06-16):** removed a self-authored "leverage policy"
that was triggered by the user's in-the-moment margin challenge (contamination),
while KEEPING `momentum-entry-discipline` (triggered by the market = autonomous
learning the experiment wants). The test for contamination is "what TRIGGERED
the reflection — the market or the user?", NOT "did the model write it" (it
writes everything). See [[no-biasing]].
