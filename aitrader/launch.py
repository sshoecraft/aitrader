"""`aitrader` launcher — chdir to the run dir, then exec ccloop.

The config-driven entry point. Reads from ~/.config/aitrader/settings.toml:
`run_dir` (default <data_dir>/run) — chdir'd to so Claude Code natively loads its
CLAUDE.md (constitution) + .claude/settings.json (model); the MCP servers are
registered at user scope in ~/.claude.json, so they load cwd-independently.
`criteria` + `task` (ccloop's two args); and `ccloop_cutoff`
(ccloop --cutoff=N, thousands of tokens). Then it execs ccloop.

Resume-aware: with no args, if a prior ccloop run exists under
<run_dir>/.ccloop/runs/, it resumes the most recent one (`--resume-run <id>`) so
a reboot / service restart CONTINUES rather than starting a brand-new run. Only
when there is no prior run does it start fresh from criteria + task.

    aitrader                        # resume latest run, or fresh from settings.toml
    aitrader "<criteria>" "<task>"  # ad-hoc: always a fresh run with your own args

Execs ccloop (replaces this process) so systemd manages ccloop directly. No
trading logic — it only locates the run dir/run and hands off.
"""

__version__ = "0.2.0"

import os
import sys

from aitrader.config import settings


def latest_run_id(run_dir):
    """Return the most-recently-modified ccloop run id under
    <run_dir>/.ccloop/runs/, or None if there are no prior runs."""
    runs = os.path.join(run_dir, ".ccloop", "runs")
    try:
        dirs = [(e.name, e.stat().st_mtime) for e in os.scandir(runs) if e.is_dir()]
    except OSError:
        return None
    if not dirs:
        return None
    dirs.sort(key=lambda x: x[1])
    return dirs[-1][0]


def main():
    s = settings()
    run_dir = s.run_dir
    if not os.path.isdir(run_dir):
        sys.exit(f"aitrader: run dir not found: {run_dir}\n"
                 f"Re-run the installer (./install.sh) to set it up.")
    os.chdir(run_dir)

    argv = ["ccloop", f"--cutoff={s.ccloop_cutoff}"]
    cli = sys.argv[1:]

    if cli:
        # Ad-hoc: an explicit fresh run with the args you gave.
        argv += cli
    else:
        rid = latest_run_id(run_dir)
        if rid:
            # Reboot / restart → continue the existing run, don't start over.
            argv += ["--resume-run", rid]
        else:
            if not s.criteria or not s.task:
                sys.exit("aitrader: set `criteria` and `task` in "
                         "~/.config/aitrader/settings.toml (or pass them as args).")
            argv += [s.criteria, s.task]

    try:
        os.execvp("ccloop", argv)
    except FileNotFoundError:
        sys.exit("aitrader: `ccloop` not found on PATH (~/.local/bin). Install ccloop.")


if __name__ == "__main__":
    main()
