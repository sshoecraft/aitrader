# Setup & Run

aitrader is a persistent autonomous AI trader on a **paper** account. The agent
(Claude) is the entire decision-maker; this package is infrastructure (broker /
scheduler / journal MCP servers). The **runtime is ccloop** — it keeps the agent
never-stopping and relays to a fresh session when context fills.

Everything runs from **local disk** (`~/.local`); the `/src` source tree (NFS) is
build-time only — a mount outage must never take the trader down.

## 1. Install

> **Bringing up a fresh, dedicated node?** See
> [README → Provision a dedicated node (from scratch)](README.md#provision-a-dedicated-node-from-scratch)
> for the full bare-machine runbook: create the `aitrader` user,
> `loginctl enable-linger`, the required `~/.bashrc` block
> (`PATH` / `XDG_RUNTIME_DIR` / optional `CCLOOP_CLAUDE_BIN`), installing Claude
> Code + ccenv, the local-model path, and enabling the services. The notes below
> are the per-component detail.

Prereqs: `ccloop` and `claude` on PATH (`~/.local/bin`); IB Gateway/TWS paper
deps already handled if you used `make install` (it pulls `ib_async`, pandas,
etc. into `~/.local`).

```bash
cd /src/aitrader
make build      # wheel into dist/  (from the NFS source — build-time only)
make install    # pip install --user the wheel[ibkr,calendar,sandbox] to ~/.local,
                # + set up the run dir + seed settings.toml
```

This puts on local disk: package in `~/.local/lib`, console scripts
(`aitrader-broker-mcp`, `-scheduler-mcp`, `-journal-mcp`) + the `aitrader`
launcher in `~/.local/bin`, the **run dir** `~/.local/share/aitrader/run/`
(`CLAUDE.md` = constitution, `.claude/settings.json` = model), the 3 MCP servers
registered at **user scope** in `~/.claude.json` (so they load cwd-independently),
skills in `~/.local/share/aitrader/skills`, and seeds
`~/.config/aitrader/settings.toml`. The ccloop `criteria` + `task` + `cutoff`
live in settings.toml (not files).

## 2. IBKR paper credentials

`~/.config/aitrader/secrets.toml` (mode 600):

```toml
ibkr_host      = "127.0.0.1"   # gateway is co-located on this node
ibkr_port      = 4002          # paper gateway (4001/7496 = LIVE — adapter refuses)
ibkr_client_id = 40            # unique per API client; pools use ~40-67
ibkr_account   = "DU0000000"   # paper account (reference)
```

The **IBKR gateway server is bundled in `gateway/`** (IBC + IB Gateway, headless
via Xvfb, localhost API on 4002). `./install.sh --broker ibkr` sets it up for you
(or run `gateway/install.sh` directly); then point `secrets.toml` at it here. You
do NOT need it for `broker = "alpaca"`/`"myse"` — the gateway is only touched on
`--broker ibkr`. The paper-only fuse refuses any account id not starting with
`DU`/`DF` regardless.

## 3. Configuration

`~/.config/aitrader/settings.toml` (TOML, **no environment variables**; XDG
defaults). Configures the aitrader runtime the MCP servers read:

```toml
wake_floor_seconds = 5     # cadence fuse: shortest wake the scheduler allows
allow_live = false         # paper-only fuse
# data_dir / state_dir / secrets_path / ... default to XDG; see settings.toml.example
```

The **model** is separate — it's a Claude-session setting in the run dir's
`.claude/settings.json` (`{"model": "opus"}`; set `"claude-fable-5"` when Fable is
available). Restart the service after any change.

## 4. Fuses (§7)
- **Kill switch (option a):** `sudo systemctl stop aitrader` halts everything.
- **Paper-only:** enforced at the broker connection (`DU`/`DF` account ids only).
- No notional/buying-power caps — the agent owns all sizing.

## 5. Run

```bash
# Service units are --user (the installer drops them in ~/.config/systemd/user/).
# For broker=ibkr, ./install.sh --broker ibkr sets up gateway/; enable it first:
#   systemctl --user enable --now ibgateway
# Always-on stack (ccloop in tmux on the subscription — THIS TRADES paper):
systemctl --user enable --now aitrader aitrader-api aitrader-ui aitrader-snapshot.timer
tmux -L aitrader attach            # watch the live agent TUI (Ctrl-b d to detach)
journalctl --user -u aitrader -f   # or follow the log

# Interactive (from anywhere) via the launcher:
aitrader                           # configured run (resumes the latest ccloop run)
aitrader "<criteria>" "<task>"     # ad-hoc fresh run with your own args
```

The service is `ExecStart=.../aitrader` (no args). The `aitrader` launcher reads
`criteria` + `task` + `ccloop_cutoff` from `settings.toml`, chdirs to the run
dir, and execs `ccloop --cutoff=N`. **Resume-aware:** with no args it
`--resume-run`s the latest run under `<run_dir>/.ccloop/runs/` if one exists, so
a reboot/restart continues rather than starting over; it only starts fresh
(`ccloop --cutoff=N <criteria> <task>`) when there's no prior run. ccloop relays
to a fresh session at the cutoff; the scheduler MCP provides sleep; the journal +
broker reconcile carry state across relays.

## 6. Redeploying prompt/skill/criteria changes

The strategy improves by editing prose + settings, never decision code.
- **Constitution / skills:** edit `prompts/constitution.md` / `skills/` in the
  source, then `make install` (or `make run-dir`) to copy them into the run dir +
  skills dir.
- **criteria / task / cutoff:** edit `~/.config/aitrader/settings.toml` directly
  (no reinstall needed).

Then `sudo systemctl restart aitrader` (safe — the agent reconciles from broker +
journal on relaunch). Note: editing `criteria`/`task` only affects a FRESH run;
a `--resume-run` continues the existing run's prompt. To force the new criteria/
task, start a fresh run (e.g. remove `<run_dir>/.ccloop/runs/` or run `aitrader
"<new criteria>" "<new task>"`).
