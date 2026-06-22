---
name: portd-dynamic-port-allocation
description: 1.3.0: aitrader-api/ui get their port from Caddy portd (:2019 /allocate, names aitrader-api & aitrader) when it's running, else settings.toml default…
metadata:
  type: project
---

## What
1.3.0 makes the dashboard portd-aware. On start, `aitrader-api` and `aitrader-ui` ask the
local Caddy **portd** plugin for their listen port; if portd isn't running they fall back to
the configured defaults (2499/2500 — see [[dashboard-default-ports-2499-2500]]). The SPA works
BOTH on the raw port (no portd) AND through Caddy path-routing `https://host/aitrader/` (portd).

## How
- `aitrader/portd.py`: `allocate(name)`, `deregister(name)`, `resolve_port(name, default)`.
  Admin API `http://127.0.0.1:2019/portd/*`. Hard **~1s timeout, never raises**. `allocate()`
  doubles as the probe → `allocate(name) or default`. portd absent = connect refused instantly
  (~0.05s measured), so startup never hangs. Verified live on clyde (allocate→5500 in 0.05s;
  unreachable→None in 0.05s→default).
- `aitrader/api.py:main()`: `port = portd.allocate("aitrader-api") or s.api_port`; binds it.
- `bin/aitrader-ui`: `ui_port = allocate("aitrader") or s.ui_port`. If `allocate("aitrader-api")`
  succeeds (portd up) it passes `--api-base /aitrader-api` to trader_ui; else `--api-port <default>`.
- Deregister on stop = `ExecStopPost=-/usr/bin/python3 -c "from aitrader import portd; portd.deregister('<name>')"`
  on both systemd units (non-fatal, ~1s) so stopped services don't leave stale routes.

## SPA path-routing (the non-obvious part — required, not optional)
Caddy strips the `/aitrader` prefix before forwarding, so the BACKEND gets unprefixed paths
(no FastAPI root_path needed for the endpoints to work). But the BROWSER must request with the
prefix, so absolute asset paths (`/assets/...`, `/config.js`) 404 under `/aitrader/`. Fixes:
- `ui/vite.config.ts` `base: './'` → built `index.html` uses `./assets/...` (works at root AND
  under a prefix). Safe ONLY because the dashboard has **no client-side router** (no deep routes).
- `ui/index.html`: `<script src="config.js">` (relative, was `/config.js`).
- `ui/bin/trader_ui`: new `--api-base` → injects `window.__API_BASE__`; SPA `ui/src/api.ts` uses
  `window.__API_BASE__ ?? http://host:port`. Under portd the base is the path `/aitrader-api`, so
  `fetch("/aitrader-api/status")` → Caddy → API. **Requires a UI rebuild** (`make ui`).

## portd facts
Endpoints: `/portd/allocate` (assigns a port from the Caddyfile `port_range`, registers
`/<name>/` reverse-proxy route, idempotent by name), `/portd/deregister`, `/portd/services`,
`/portd/register` (caller-supplied port). We use **allocate**, mirroring `/src/dispatcher`.
Source: `/src/caddy-portd` (Go Caddy plugin; live on clyde, range starts ~5500).

## Status
Source change only (not installed). Deploy: `./install.sh` + `make ui` + restart aitrader-api/ui.
Files: `aitrader/portd.py` (new), `aitrader/api.py`, `bin/aitrader-ui`, `ui/bin/trader_ui`,
`ui/src/api.ts`, `ui/src/globals.d.ts`, `ui/index.html`, `ui/vite.config.ts`, both systemd units.
