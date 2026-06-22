---
name: api-service-deploy-path
description: aitrader-api.service runs the INSTALLED ~/.local package, not /src; deploying API code changes needs make build+install+restart aitrader-api.
metadata:
  type: project
---

`aitrader-api.service` (FastAPI :7099) and `aitrader-ui.service` (:7100) run as
`systemctl --user` units. The API ExecStart is `~/.local/bin/aitrader-api`, which
imports the **installed** package at `~/.local/lib/python3.12/site-packages/aitrader/`
— NOT `/src/aitrader`. So editing files under `/src/aitrader` and restarting the
service does nothing; the running process still reports the old `__version__`.

To deploy an API/broker code change: `make build && make install` (builds a wheel,
force-reinstalls to `~/.local`), then `systemctl --user restart aitrader-api`. The
Makefile `restart`/`full` targets only touch `aitrader.service` (the agent), not the
API — restart `aitrader-api` explicitly.

Restarting `aitrader-api` is safe and independent of the trading agent: it's a
separate IBKR client (id 80; agent uses base 40, pools 40-71), so it only blips the
dashboard, never the agent's session or positions.

Note: a bare `python3 -c "import aitrader"` from `/src/aitrader` resolves to the
`/src` tree (cwd on sys.path) and can show a *different* version than the running
service — don't trust it to tell you what's deployed. See [[runtime-no-headless-p-tmux]].
