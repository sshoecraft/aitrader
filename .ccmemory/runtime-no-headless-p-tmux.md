---
name: runtime-no-headless-p-tmux
description: aitrader must NEVER run headless `claude -p` (metered); the systemd service runs ccloop in tmux for a PTY → interactive TUI → subscription.
metadata:
  type: project
tags: [runtime, billing, ccloop, tmux, systemd, PATH]
---

Anthropic is moving headless `claude -p` / Agent-SDK usage OFF the Claude
subscription onto a metered API credit pool. aitrader runs on a Max subscription,
so it must run the **interactive Claude TUI**, never headless `-p`.

**ccloop 0.5.0+ enforces this** (`/src/ccenv/ccloop`): it never selects headless
`-p` implicitly — that requires BOTH `--headless --accept-api-cost`. With a TTY it
runs the interactive TUI; with NO TTY and no opt-in it **refuses (exit 2)**.
Auto-detect = `sys.stdin.isatty() and sys.stdout.isatty()`.

**The service** `systemd/aitrader.service` (user unit) runs ccloop **inside tmux**
so it gets a real PTY → interactive → subscription:
`ExecStart=/usr/bin/tmux -L aitrader new-session -d -s main .../aitrader`,
`Type=forking`, `ExecStop=tmux -L aitrader kill-server`. Attach: `tmux -L aitrader attach`.

**Two gotchas that make the service crash-loop — both load-bearing (v0.6.1):**
1. **PATH**: systemd's user-manager PATH omits `~/.local/bin`, where ccloop+claude
   live. Without `Environment=PATH=/home/aitrader/.local/bin:...` in the unit, the
   launcher's `execvp("ccloop")` fails ("ccloop not found on PATH") → exit 1 →
   crash-loop. Works from a terminal only because the login shell has ~/.local/bin.
2. **No TTY**: do NOT revert to a bare `Type=simple ExecStart=.../aitrader` — with no
   TTY ccloop 0.5.0 refuses (exit 2). The tmux PTY is required, not cosmetic.

aitrader / aitrader-api / aitrader-ui are all `enable`d user services (lingering on)
so the stack auto-recovers after reboot/power-loss.

**How to apply:** Never add `-p`/`--print`/`--headless` to any claude/ccloop call in
this project. Any always-on path needs a PTY (tmux, or `script -qfec`) AND ~/.local/bin
on PATH. Open ccloop gap: interactive `_confirm_relaunch()` Y/n prompt blocks on an
abnormal (non-relay) exit inside detached tmux — wants auto-relaunch-when-unattended
for full autonomy. Relates to [[runtime-ccloop]] and [[model-choice]].
