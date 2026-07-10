---
name: aitrader-deployment-topology
description: aitrader/clyde topology: per-instance model (atrader=local vLLM via clyde; itrader=opus/subscription); systemd stack+readiness gate; ~/.local.
metadata:
  type: project
tags: [deployment, topology, clyde, model, systemd, ccloop]
---

# aitrader deployment topology (clyde) — migrated from the retired state.md

Everything runs from `~/.local` on **clyde** (gateway + brain co-located). `/src`
is NFS, build-time only. This replaces state.md's "Environment" + "Infra topology"
sections (state.md retired 2026-07-09 in 1.34.0 — its changelog role → CHANGELOG.md,
its living-status role → here).

## Model — set PER-INSTANCE by each user's `~/.config/environment.d/ccloop.conf` (NOT drift; §3 and "local model" are BOTH true, for different instances)
- **atrader → local vLLM.** Its ccloop.conf sets `CCLOOP_CLAUDE_BIN=/usr/local/bin/clyde`
  (+ `CCLOOP_EFFORT=max`). `clyde` is a Python wrapper: GETs `/v1/models` from a local
  OpenAI-compatible vLLM server (`http://192.168.1.166:8000`), takes `models[0]`, and
  execs `claude` with `ANTHROPIC_BASE_URL=that host`, `ANTHROPIC_AUTH_TOKEN=local`,
  `ANTHROPIC_MODEL=<served>`, `CLAUDE_CODE_SUBAGENT_MODEL=<same>`, and
  `CLAUDE_CODE_MAX_CONTEXT_TOKENS` from the server's `max_model_len` (needs
  `DISABLE_COMPACT=1`). So atrader's run-dir `{"model":"opus"}` is DEAD. Served model:
  `curl http://192.168.1.166:8000/v1/models`.
- **itrader → opus (Claude subscription).** NO `CCLOOP_CLAUDE_BIN` in its ccloop.conf
  (just `CCLOOP_EFFORT=max` + a commented `#CCLOOP_MODEL=opus`), so ccloop runs plain
  `claude`, which honors its run-dir `.claude/settings.json {"model":"opus"}`.
- **trader / warden:** no ccloop.conf and no aitrader run-dir `.claude/settings.json` —
  NOT aitrader-agent instances in the same sense (legacy/other). Don't assume they run
  the constitution.
- So §3's "single model, opus/Fable" is TRUE for itrader; atrader is the deliberate
  local-model variant. This is effectively a live **opus-vs-vLLM A/B on the same
  constitution** — and the churn that drove 1.34.0 ([[constitution-stripped-to-mechanics]])
  is on the vLLM side (atrader). The forced-artifact memories
  ([[constitution-steps-not-prose]], [[constitution-enforce-via-step-not-column]]) still
  bind atrader because a local model is what it runs.

## Install / config
- `make build && make install` → pkg in `~/.local/lib`, MCP scripts + the `aitrader`
  wrapper in `~/.local/bin`, prompts + run-dir in `~/.local/share/aitrader`. No venv;
  nothing runs from /src.
- Config `~/.config/aitrader/settings.toml` (+ `secrets.toml`). No env vars for app
  config (env.d carries ONLY the clyde/ccloop knobs above).
- Run dir `~/.local/share/aitrader/run/` = `CLAUDE.md` (the constitution, deployed via
  `make const`) + `.claude/settings.json`. The 3 MCP servers are registered user-scope
  in `~/.claude.json`, NOT a run-dir `.mcp.json`.

## Billing-safe runtime
ccloop NEVER uses headless `claude -p` (metered) — the service runs ccloop **inside
tmux** (socket `-L aitrader`) to supply a PTY → interactive TUI → subscription. Attach:
`tmux -L aitrader attach`. Stop: `systemctl --user stop aitrader`. See
[[runtime-no-headless-p-tmux]]. (Note: an instance pointed at a local vLLM via clyde,
like atrader, isn't on the subscription at all — the tmux/PTY path still applies.)

## Service stack (all `--user`, enabled, lingering on)
`ibgateway` (broker=ibkr only, bundled `gateway/` subdir) → `ibgateway-ready` (oneshot
readiness gate `bin/aitrader-gateway-wait`; blocks until the gateway API accepts a login
— exists because `After=ibgateway` only waits for the PROCESS not its ~10-90s login;
connecting early caused an `Error 326` reconnect storm that wedged the dashboard after a
reboot) → `aitrader` (agent, in tmux), `aitrader-api` (dashboard, default :2499, client
id 80/90/100), `aitrader-ui` (default :2500), `aitrader-snapshot.timer` (equity recorder),
`aitrader-report@{daily,weekly,monthly,yearly}.timer` (added 1.33.0). `aitrader.service`
needs `Environment=PATH=~/.local/bin:…` or `execvp("ccloop")` fails → crash-loop.
`aitrader-api.service` runs the INSTALLED `~/.local` pkg, not /src (deploying API changes
needs build+install+restart — see [[api-service-deploy-path]]).

## Instances
Multiple stacks on clyde: home dirs `atrader`, `itrader`, `trader`, `warden` — per-instance
ports/settings.toml; `report_name` defaults to the unix user. `atrader` has passwordless
sudo on clyde (gateway upkeep). IB Gateway (paper) co-located as `ibgateway.service` (IBC
3.23.0 + GW 1044, headless Xvfb, localhost API 4002). `infra` (QNAP VM) decommissioned.
