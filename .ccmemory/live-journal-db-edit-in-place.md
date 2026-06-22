---
name: live-journal-db-edit-in-place
description: NEVER rm+recreate the live journal.db; INSERT in place. Long-lived holders (journal-MCP, aitrader-api) keep the deleted inode and split-brain.
metadata:
  type: feedback
---

When modifying the live journal db (`~/.local/state/aitrader/journal.db`),
**edit in place with INSERT/UPDATE — never `rm` + recreate (incl. `cp` over it
or `VACUUM INTO` after deleting it).**

**Why:** Two long-lived processes hold the db open continuously:
- `aitrader-api` (standalone user service)
- `aitrader-journal-mcp` — a **stdio child of the live `claude` agent session**
  (spawned per session from `~/.claude.json` user-scope MCP), so it canNOT
  reopen the file on its own.

If you unlink the file, those processes keep writing to the now-**deleted
inode** (a ghost). The UI/API show stale data, and the agent's new writes are
silently lost. A plain `cp` is also defeated by a leftover `journal.db-wal`
being replayed on open.

**How to apply:**
- Backfill/import = `INSERT ... WHERE ts NOT IN (...)` against the existing file.
- If you already deleted it: recover the ghost via `cat /proc/<pid>/fd/<n>`
  (db + `-wal` + `-shm`), `VACUUM INTO` a clean copy, merge its unique rows back,
  then restart the holders so they reopen the path. `aitrader-api` =
  `systemctl --user restart aitrader-api`. journal-MCP only reopens on agent
  relaunch (`systemctl --user restart aitrader`; ccloop reconciles from broker +
  journal, safe when market closed).
- aitrader runs as **`--user` systemd services** (`systemctl --user`), not system
  scope. Restarting `aitrader-api` reallocates its portd port (5506→5507…) but
  Caddy routes by name so the UI path is unaffected.

Context: 2026-06-20, restoring the journal after a reinstall wiped it.
Related: [[equity-backfill-on-first-sync]], [[api-service-deploy-path]],
[[runtime-no-headless-p-tmux]], [[portd-dynamic-port-allocation]].</body>
