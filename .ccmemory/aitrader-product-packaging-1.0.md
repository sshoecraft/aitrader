---
name: aitrader-product-packaging-1.0
description: 1.0.0 packaged aitrader as ONE product: ./install.sh (no-prompt template-seed default), ports 7500/7501, snapshot timer, ui/ de-vendored, IBKR gatewa…
metadata:
  type: project
---

aitrader **1.0.0** (2026-06-18) turned the dev checkout into ONE shippable product.
Structural facts not obvious from the tree:

- **`/src/aitrader` is the whole product**: `aitrader/` (Python pkg = 3 MCP servers
  + API backend + brokers + journal), `ui/` (frontend), `systemd/`, `bin/`,
  `prompts/`, `skills/`, `install.sh`. The IBKR **gateway server** is the ONLY thing
  split out — into `/src/aitrader-ibkr-gateway` (per the user's explicit instruction;
  it needs paper/live + credential + consent decisions). aitrader ships only the IBKR
  *client* (`brokers/ibkr*.py`, `[ibkr]` extra, `aitrader-gateway-wait`,
  `ibgateway-ready.service`). Contract: that repo's unit MUST be `ibgateway.service`
  on `ibkr_host:ibkr_port`.
- **`ui/` was de-vendored** (it was a fork of a standalone trader-ui project). Removed
  its parallel skeleton: `ui/Makefile`, `ui/systemd/`, `ui/docs/`, `ui/.ccmemory/`,
  `ui/README.md`, `ui/state.md`, `ui/CLAUDE.md`, + stray `ui/{p,ledger-check.png,
  .playwright-mcp}`. `ui/` is now JUST the SPA (src/, public/, bin/trader_ui, dist/,
  package.json, node_modules, configs). The UI doc now lives at top-level
  `docs/ui.md`. Build: top-level `make ui` or `install.sh` (build from `ui/`, serve
  `~/.local/share/aitrader/ui`). See [[aitrader-ui-build-deploy]].
- **`install.sh` default = NO prompts** (matches the user's stated flow): installs +
  seeds `settings.toml` (defaults broker=alpaca, ports 7500/7501) + a `secrets.toml`
  TEMPLATE, then says "edit those two files, then `systemctl --user enable --now …`".
  It does NOT auto-enable when keys are templated. `--wizard` = interactive prompts +
  auto-enable; `-y --broker X --…keys` = fully non-interactive + auto-enable. The user
  finds prompt-by-default "fucking around" — keep template-seed as the default.
- **Default port block 7500/7501** (was 7099/7100). config.py `api_port`=7500.
- **Snapshot = systemd timer** (`aitrader-snapshot.{service,timer}`), not cron.
- **Makefile is DEV-only** (build/install/ui). Users use `install.sh`. Realigned to
  match (no gateway unit, UI from `ui/`, snapshot timer, broker-scoped pip extra).
- LICENSE holder "Steve Shoecraft" — inferred, confirm.
- Still paper-only (`allow_live=false`, `aitrader/fuses.py`). Real money = one flag,
  not blocked. See [[constitution-stops-and-tool-mechanics]].</body>
