---
name: aitrader-ui-build-deploy
description: aitrader UI source=/src/aitrader/ui; serves ~/.local/share/aitrader/ui (renamed from trader/ in 1.0.0). Build via install.sh or make ui.
metadata:
  type: project
---

Deploying a CSS/TSX change to the aitrader dashboard UI (updated for **1.0.0**):

- **Source:** `/src/aitrader/ui` (React+TS+Vite). NOT `/src/trader-ui`. See
  [[no-find-on-src-ui-location]].
- **Served from:** `~/.local/share/aitrader/ui` (RENAMED in 1.0.0 from the legacy
  `~/.local/share/trader/ui`). `aitrader-ui.service` → `~/.local/bin/aitrader-ui`
  → `~/.local/bin/trader_ui` (stdlib http.server SPA server, `INSTALL_DIR` now the
  aitrader dir). Ports come from settings.toml at runtime via a `/config.js` route
  (api_port default **7500**, ui_port=api_port+1=**7501**; was 7099/7100). PORT
  changes need no rebuild; asset/CSS changes DO.
- **Build + deploy:** the installer (`/src/aitrader/install.sh`) copies prebuilt
  `ui/dist` → the serve dir and installs `ui/bin/trader_ui`. To rebuild assets:
  `cd /src/aitrader/ui && . ~/.nvm/nvm.sh && npm run build -- --outDir ~/.local/share/aitrader/ui --emptyOutDir`
  then `systemctl --user restart aitrader-ui` (hard-refresh; assets are
  content-hashed). Or `make ui` from the repo root (now fixed — builds from `ui/`).
- **FIXED in 1.0.0 (were the old gotchas):** the main Makefile `ui` target now
  builds from `UI_SRC := ui` into `~/.local/share/aitrader/ui` (no longer the stale
  `/src/trader-ui` that would clobber with the wrong source). `ui/CLAUDE.md` was
  rewritten for aitrader (no longer the stale trader-ui copy with :7000).
- **NOTE:** the live clyde box still serves the old `~/.local/share/trader/ui` on
  7099/7100 until it's redeployed with the 1.0.0 installer. Relates to
  [[aitrader-services]], [[aitrader-product-packaging-1.0]].</body>
