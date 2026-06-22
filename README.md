# aitrader

> ## ⚠️ DISCLAIMER — READ FIRST
> **aitrader is licensed for personal, non-commercial use only** (PolyForm
> Noncommercial 1.0.0 — see [`LICENSE`](LICENSE)). It is **NOT intended to be
> run against a live brokerage account** — it ships paper-only by design. The
> author bears **NO responsibility for any financial loss or damage** of any
> kind arising from its use. **You use it entirely at your own risk.**

**A persistent autonomous AI trader.** A Claude agent runs continuously and is the
*entire* decision-maker for a trading account — it decides what to look at, what to
trade, when, how much, and when to exit, **by reasoning**. Everything in this repo
is infrastructure: broker connectivity, market data, a clock, a journal, a runtime,
and a dashboard. None of it contains a strategy, a screener, a threshold, or a
buy/sell opinion. (See [`BRIEF.md`](BRIEF.md) and [`CLAUDE.md`](CLAUDE.md) for the
design and the hard infrastructure/cognition boundary.)

Ships **paper-first**. Runs against **Alpaca** or **MYSE** out of the box with no
extra moving parts; IBKR is supported too — its gateway server is bundled in
[`gateway/`](gateway/) and set up for you when you install with `--broker ibkr`.
Real-money trading is possible but deliberately gated behind a fuse — see
[Safety](#safety).

---

## What you get

| Component | What it is |
|---|---|
| **The agent** | Claude, run by `ccloop` in a tmux PTY (your Claude subscription, never metered API), never-stopping, relaying to a fresh session when context fills. |
| **3 MCP servers** | `broker` (execution + market data), `scheduler` (clock + blocking waits = the agent's sleep), `journal` (notebook + positions-of-record). Pure infra. |
| **Dashboard** | A FastAPI backend (`aitrader-api`) + React UI (`trader_ui`) showing account, positions, equity curve, and the agent's own rationale. |
| **Snapshot timer** | A systemd timer recording a baseline equity snapshot every 15 min. |

State survives restarts because the **broker is the source of truth** (reconciled
every wake) and the **journal holds intent**; nothing critical lives only in
context.

## Requirements

- Linux with `systemd --user` (enable lingering: `loginctl enable-linger $USER`)
- Python ≥ 3.12, `pip`, `tmux`
- `claude` and `ccloop` on your `PATH` (`~/.local/bin`)
- A broker account: **Alpaca** (paper keys) or **MYSE**, or **IBKR** (the gateway
  in [`gateway/`](gateway/) is set up automatically by `--broker ibkr`)
- Node/npm only if you build the UI from a git clone (release tarballs ship the
  prebuilt UI)

## Provision a dedicated node (from scratch)

aitrader is designed to run as its **own unmodified Linux user** under
`systemd --user` (one trader per user → one broker account per user). On a bare
machine the full bring-up is:

```bash
# 1. Create the dedicated user and let its --user services run without a login
sudo useradd -m -s /usr/bin/bash aitrader
sudo loginctl enable-linger aitrader            # services start at boot, survive logout

# 2. Become that user for everything below
sudo -iu aitrader
```

As the `aitrader` user, put these lines at the **very TOP of `~/.bashrc`, ABOVE
the interactive-shell guard** (the `case $- in *i*)` / `[ -z "$PS1" ] && return`
block). They must run for *non-interactive* SSH commands too, or `systemctl
--user` and `ccloop` won't find their runtime dir or binaries:

```bash
export PATH="$HOME/.local/bin:$PATH"
# LOCAL MODEL ONLY — uncomment to point ccloop's interactive runs at a local
# OpenAI-compatible server via extras/local_claude (see "Local model" below).
# Leave commented when using the Claude subscription / Anthropic API.
#export CCLOOP_CLAUDE_BIN=/usr/local/bin/local_claude
export XDG_RUNTIME_DIR=/run/user/$(id -u)         # makes `systemctl --user` work over SSH
```

Then, still as `aitrader`:

```bash
# 3. Install Claude Code (the agent runtime)
#    https://docs.claude.com/en/docs/claude-code — and authenticate it once
#    (`claude` → /login) on your Max/subscription.

# 4. Install ccenv (provides ccloop, the never-stopping runtime)
git clone https://github.com/sshoecraft/ccenv && cd ccenv && ./install.sh && cd ..

# 5. Install aitrader itself
git clone <this repo> aitrader && cd aitrader
./install                                         # alpaca by default…
# …or, for IBKR as the backend broker, set up the bundled gateway too:
./install --broker ibkr

# 6. Fill in config + secrets, then enable the stack
$EDITOR ~/.config/aitrader/settings.toml          # broker + ports
$EDITOR ~/.config/aitrader/secrets.toml           # broker keys (mode 0600)
systemctl --user daemon-reload
systemctl --user enable --now aitrader aitrader-api aitrader-ui aitrader-snapshot.timer
```

**IBKR backend (`--broker ibkr`).** The installer also sets up the bundled
gateway (`gateway/` — IB Gateway under IBC, headless), then stops for the two
decisions only you can make — your IBKR login and paper-vs-live. Fill in
`~/ibc/config.ini`, point `secrets.toml` at the gateway (`ibkr_port = 4002` =
paper), enable it **before** the trader, then start the rest:

```bash
systemctl --user enable --now ibgateway          # bring the gateway up first
systemctl --user enable --now aitrader aitrader-api aitrader-ui aitrader-snapshot.timer
```

See [`gateway/README.md`](gateway/README.md). For non-IBKR brokers
(`alpaca`/`myse`) there is no gateway — skip this block.

### Local model

To run the agent against a **local OpenAI-compatible model** instead of the
Claude subscription/API, the launcher is [`extras/local_claude`](extras/) — it
fetches the served model + its real context window and points Claude Code at it.
Install it and wire it in at **both** levels:

```bash
# Interactive runs (tmux TUI) read ~/.bashrc — uncomment the CCLOOP_CLAUDE_BIN
# line shown above, after copying the launcher onto PATH:
sudo install -m 0755 extras/local_claude /usr/local/bin/local_claude

# Non-interactive runs (the systemd --user service) do NOT read ~/.bashrc, so
# also set it via environment.d, then reload so the manager picks it up:
mkdir -p ~/.config/environment.d
echo 'CCLOOP_CLAUDE_BIN=/usr/local/bin/local_claude' > ~/.config/environment.d/ccloop.conf
systemctl --user daemon-reload
```

> **Search MCP required for local models.** Claude Code's built-in
> `WebSearch`/`WebFetch` only work against Anthropic's backend — they are dead
> when pointed at a local model. If the agent runs local, register a separate
> search-provider MCP (e.g. Brave Search or SearXNG) so it keeps web access.

### Optional: auto port registration

If you run [caddy-portd](https://github.com/sshoecraft/caddy-portd) on the host,
the API/UI register themselves for a dynamically-allocated port (the api/ui units
request one from portd at `:2019`) and Caddy reverse-proxies them by name — no
fixed `2499`/`2500` to manage. Without portd the defaults in `settings.toml`
apply.

## Install

The default install asks **no questions** — it installs everything and seeds two
config files for you to edit:

```bash
cd aitrader
./install.sh
$EDITOR ~/.config/aitrader/settings.toml   # broker + ports (defaults 2499/2500 are fine)
$EDITOR ~/.config/aitrader/secrets.toml     # your broker keys
systemctl --user enable --now aitrader aitrader-api aitrader-ui aitrader-snapshot.timer
tmux -L aitrader attach                      # watch the live agent (Ctrl-b d to detach)
```

That's the whole flow. The installer is self-contained (no `make` needed): it
builds + `pip install --user`s the package, deploys the UI, seeds the run dir +
constitution, registers the MCP servers at user scope, and installs the systemd
user units — all under `~/.local`/`~/.config` (the source tree is build-time only).

Prefer to be walked through it, or fully automate it?

```bash
./install.sh --wizard                                      # prompts for broker/ports/keys, then auto-enables
./install.sh -y --broker alpaca --alpaca-key K --alpaca-secret S   # fully non-interactive
```

Dashboard: `http://127.0.0.1:2500` · API: `http://127.0.0.1:2499/status`.

**Using IBKR?** Install with `--broker ibkr` and the installer also sets up the
bundled gateway (`gateway/` — IB Gateway under IBC, headless): it downloads the
gateway, installs its `ibgateway.service`, and seeds `~/ibc/config.ini`. It then
stops for the two decisions only you can make — your IBKR login and paper-vs-live
— so you fill in `~/ibc/config.ini`, `systemctl --user enable --now ibgateway`,
then enable the aitrader services. Pass `--no-gateway` to manage the gateway
yourself. See [`gateway/README.md`](gateway/README.md).

### Brokers

| `broker =` | Needs | Notes |
|---|---|---|
| `alpaca` | `alpaca_api_key`, `alpaca_secret_key` | Stocks + crypto. Simplest; no gateway. **Default.** |
| `myse`   | `myse_host`, `myse_api_key` | REST exchange client. Optional `data_broker = "alpaca"` for market data. |
| `ibkr`   | the bundled [`gateway/`](gateway/) + `ibkr_host`/`ibkr_port` | Multi-asset. `--broker ibkr` sets up the gateway (IB Gateway/IBC/Xvfb) for you; you still make the paper/live + credential decisions it stops for. |

## Configure

Everything is file-based (no environment variables):

- `~/.config/aitrader/settings.toml` — broker, ports, cadence, ccloop criteria/task.
- `~/.config/aitrader/secrets.toml` — broker credentials (mode 0600).
- `<run_dir>/.claude/settings.json` — the Claude model (`{"model": "opus"}`; switch
  to `claude-fable-5` when available).

Restart after changes: `systemctl --user restart aitrader aitrader-api`.

## Safety

aitrader has exactly one deterministic "no": a **paper-only fuse**
(`aitrader/fuses.py`). The broker adapter refuses any non-paper account unless you
set `allow_live = true` in `settings.toml`. For IBKR, the gateway's paper/live mode
is a *second, independent* switch — both must agree before a real-money order is
possible. There are deliberately **no notional or position-size caps in code**: the
agent owns all sizing by reasoning. Going to real money is your conscious decision;
see `BRIEF.md`/`CLAUDE.md` on the fuse model before you flip it.

Stop the trader at any time: `systemctl --user stop aitrader`.

## Operate

```bash
systemctl --user status aitrader
journalctl --user -u aitrader -f                  # agent log
journalctl --user -u aitrader-snapshot -f         # equity recorder
systemctl --user list-timers | grep aitrader      # snapshot schedule
```

## Uninstall

```bash
./uninstall.sh            # remove the install, keep journal + config
./uninstall.sh --purge    # also delete journal.db, settings, secrets (confirmed)
```

## Layout

```
install.sh / uninstall.sh   the product front door
aitrader/                   the package (config, api, brokers, mcp servers, journal)
ui/                         dashboard SPA + its static server (ui/bin/trader_ui)
systemd/                    --user units (agent, api, ui, snapshot timer, readiness gate)
bin/                        launchers + CLIs (snapshot recorder, gateway readiness probe)
gateway/                    the bundled IBKR gateway server (IB Gateway/IBC) — only used by broker=ibkr
prompts/ skills/            the agent's constitution + prose how-to guidance
docs/                       per-subsystem documentation
CLAUDE.md / BRIEF.md        the project constitution + founding design brief
```

The IBKR gateway server lives in [`gateway/`](gateway/) and is set up by
`./install.sh --broker ibkr` (or run `gateway/install.sh` directly).
