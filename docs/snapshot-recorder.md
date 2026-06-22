# snapshot-recorder — fixed-cadence equity telemetry (`bin/aitrader-snapshot`)

## What it is

A tiny timer-driven CLI that records one **equity snapshot** to the journal on a
fixed cadence (every 15 min, 24/7). It exists so the dashboard's `day_pl` and the
equity curve have a regular, agent-independent baseline.

It is **pure infrastructure** (CLAUDE.md §2): mechanical recording of account
equity on a clock. No threshold, no ranking, no decision — it biases no trade.
It does not replace the agent's own snapshots; the agent still writes *annotated*
snapshots via the journal MCP (`equity_snapshot_write`) whenever it wants. The
recorder only guarantees the baseline underneath.

## Why it exists

Before this, equity snapshots were written **only** by the agent, when it chose
to. That made them sparse and irregular. Two concrete failures:

1. **`day_pl` read 0 for long stretches.** `api.day_pl` baselines off the first
   equity snapshot of the current **ET** day (see `docs/api.md`). The agent sleeps
   ~11h overnight inside a blocking scheduler `wait_*` call, so after ET midnight
   there was no snapshot for the new day and day P&L showed 0 until the agent woke
   and acted.
2. **Gappy equity curve.** `/portfolio_history` plots the snapshots; sparse points
   make a coarse, hole-y curve.

A fixed 15-min cadence guarantees a fresh snapshot within 15 min of any ET-day
rollover, so day_pl is meaningful soon after midnight and the curve is smooth —
while keeping broker load and history-window churn modest (see Characteristics).

## How it works

```
systemd timer (*:0/15)  →  aitrader-snapshot  →  GET 127.0.0.1:<api_port>/status  →  journal_db.equity_write
```

- **No broker connection of its own.** It reads equity over HTTP from the running
  dashboard API, which owns broker `client_id 80`. So it adds no IBKR client id and
  carries no Error 322/326 risk — the API stays the only extra broker client.
- Connects to **`127.0.0.1`**, not `settings.api_host` (which may be the `0.0.0.0`
  *bind* address).
- Writes `equity`, `cash`, `buying_power` with `ts = utcnow_iso()` and
  `notes="snapshot recorder"`.
- **Never records fake data:** if the API is unreachable, the broker is
  disconnected, or equity is missing/0, it writes nothing and exits non-zero
  (prints a `SKIP:` line). Exit 0 only on a real written snapshot.
- Stdlib only (`urllib`) — no extra dependency.

## Install / operate

- The installer (`./install.sh`, or `make install`) drops the script in
  `~/.local/bin` (via `install -m 755 bin/*`) — LOCAL disk, never `/src` (NFS), per
  the §7 local-disk invariant.
- Scheduling is a **systemd user timer**, not cron (replaced 1.0.0): the installer
  drops `aitrader-snapshot.service` (oneshot) + `aitrader-snapshot.timer`
  (`OnCalendar=*:0/15`, `Persistent=true`) into `~/.config/systemd/user/`. Enable:
  ```
  systemctl --user enable --now aitrader-snapshot.timer
  ```
  One unit pair is correct for every user (`%h` paths). `Persistent=true` runs one
  catch-up after downtime so the curve doesn't gap.
- Output goes to the **journal** (not a logfile): `journalctl --user -u aitrader-snapshot`
  (one line per run: written id + equity, or a `SKIP:` reason).
- Check the schedule: `systemctl --user list-timers | grep aitrader-snapshot`.
- Run by hand to check: `aitrader-snapshot` (prints the same one-line status).

## Characteristics / notes

- Cadence 15 min → ~96 rows/day. `api.day_pl` reads `limit=500` (ample for one ET
  day); `/portfolio_history` reads `limit=5000` (≈52 days of history at this rate).
  If a longer visible history is wanted, raise that limit or downsample.
- **Why 15 min, not 5:** the dominant cost is not disk (~96 tiny rows/day) but the
  live broker round-trip behind each `/status` (≈4 IBKR calls — account/positions/
  orders/types) running 24/7, including overnight when the agent sleeps and equity
  is static (the gateway has thrown Error 322 on account-summary churn before). The
  day_pl baseline needs only one snapshot soon after ET midnight, and intraday curve
  resolution only matters during market hours — so 5-min was overkill. 15-min cuts
  broker load to ~1/4 and stretches the visible history ~3×. A tiered schedule
  (dense during RTH, sparse off-hours) is the option if crisp intraday resolution is
  ever wanted without the overnight waste.
- The recorder is independent of the agent and the API restarting; it only needs
  the API reachable at snapshot time (otherwise it cleanly skips).

## History

- **0.1.0** (project 0.7.0, 2026-06-16) — initial recorder + 5-min crontab entry.
- **(project 1.0.0, 2026-06-18)** — scheduling moved from crontab to a systemd user
  timer (`aitrader-snapshot.{service,timer}`); output now to the journal. Keeps the
  whole stack under `systemctl --user` for the shippable product. Journal note label
  changed `cron recorder` → `snapshot recorder`.
