---
name: equity-snapshot-recorder-cron
description: Equity snapshots: bin/aitrader-snapshot reads /status over HTTP and writes a journal snapshot; as of 2026-06-18 `make install` installs the */15 cron…
metadata:
  type: project
---

As of 2026-06-16 (v0.7.0), equity snapshots (the source of `/status` `day_pl` and
the `/portfolio_history` curve) are written on a fixed cadence by
`bin/aitrader-snapshot`, NOT only by the agent.

- The recorder reads equity over HTTP from the running dashboard API
  (`GET 127.0.0.1:<api_port>/status`) and writes one journal equity snapshot. It
  opens NO broker connection of its own (the API owns the broker connection), so no
  extra IBKR client id / Error 322/326 risk. Stdlib-only; refuses to record when
  the API is unreachable / broker disconnected / equity 0 (no fake data). Because
  it goes through the API, it is broker-agnostic — it worked on the Alpaca node
  node the moment the API itself connected (see [[api-multibroker-and-version-drift]]).
- **`make install` now installs the crontab entry** (2026-06-18). The `install-cron`
  target (folded into `install`, also runnable standalone) appends, ONLY IF no
  `aitrader-snapshot` line already exists, this idempotent entry for the running
  user (paths from `$(LOCAL_BIN)`/`$(STATE_DIR)`, so per-user — gtrader vs aitrader):
  `*/15 * * * * ~/.local/bin/aitrader-snapshot >> ~/.local/state/aitrader/logs/snapshot.log 2>&1`
  Re-running install keeps the existing entry (grep guard). It also `mkdir -p`s the
  logs dir. NOTE: cadence is **`*/15`** (matches the deployed aitrader@clyde
  crontab), not the `*/5` an older note claimed.
- **Why it exists:** snapshots used to be agent-only (journal MCP
  `equity_snapshot_write`) → sparse; `day_pl` baselines off the first snapshot of
  the current ET day (see `docs/api.md`), so after ET midnight and through the
  agent's overnight blocking-scheduler sleep, day_pl read 0 and the curve was
  gappy. Fixed cadence guarantees a fresh ET-day baseline quickly.
- Boundary-safe (CLAUDE.md §2): mechanical telemetry, biases no trade — see
  [[no-biasing]]. The agent still writes its own annotated snapshots too.
- The cron is also documented in `docs/snapshot-recorder.md` and CHANGELOG [0.7.0].
- Unrelated but learned earlier: a multi-hour tmux spinner on the agent
  ("Razzmatazzing… 2h29m") is NORMAL — the agent asleep inside a blocking
  scheduler `wait_*` call (CLAUDE.md §7), not a hang. Real tmux socket is
  `-L aitrader` (session `main`); the agent runs via `aitrader.service`.</body>
