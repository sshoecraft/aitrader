---
name: install-sh-gateway-ibc-layout
description: gateway/install.sh auto-downloads IB Gateway + IBC; non-obvious flat-vs-nested layout, build detection, and IBC's bundled config.ini gotcha
metadata:
  type: project
---

The gateway installer (now `gateway/install.sh`, merged into the aitrader repo from the former standalone `aitrader-ibkr-gateway` repo on 2026-06-20 (aitrader 1.6.0); aitrader's own `./install.sh --broker ibkr` descends into it) was changed (2026-06-20) from "checks that you provided IB Gateway + IBC" to **downloading and installing both** automatically. Idempotent: each step detects and skips if present. Flags `--no-deps`, `--no-app`.

Key facts that took real digging (don't re-derive):

- **IB Gateway standalone installer installs FLAT** into its `-dir` (app `ibgateway` launcher, `jars/`, `.install4j/`, `data`, `ibgateway.vmoptions`, `uninstall` all directly in `-dir`). It does NOT create the classic `~/Jts/ibgateway/<build>/` tree.
- **IBC requires the NESTED layout**: `scripts/ibcstart.sh` builds `gateway_program_path=${TWS_PATH}/ibgateway/${TWS_MAJOR_VRSN}` and needs `<that>/jars`. So install.sh installs into a staging dir, reads the build, then renames staging → `~/Jts/ibgateway/<build>/`.
- **Build number source**: `jars/jts4launch-<build>.jar` (e.g. `jts4launch-1045.jar` → build `1045`, Gateway 10.45). This becomes IBC's `TWS_MAJOR_VRSN`.
- **install4j unattended flags**: `-q` (unattended, no X needed) `-dir <path>`.
- **IBC's release zip ships its OWN `config.ini`** — a generic default with `TradingMode=live`, `AcceptIncomingConnectionAction=manual`, empty `OverrideTwsApiPort`. ALL WRONG for aitrader (and defaults to LIVE!). install.sh deletes it on extract so the seed step installs `ibc/config.ini.example` (paper, 4002, accept) instead. Never clobbers a user-edited config.
- IBC `gatewaystart.sh` editable vars (lines ~21-28) are sed-pinned: `TWS_MAJOR_VRSN`, `TWS_PATH`, `IBC_PATH`, `IBC_INI`, `LOG_PATH`.
- **No `unzip` on this box** — IBC zip is extracted with `python3 -m zipfile -e`.
- Sources: IB Gateway `https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh` (~320MB); IBC latest via GitHub API `repos/IbcAlpha/IBC/releases/latest`.

Remaining manual user steps after install: fill `IbLoginId`/`IbPassword`/`TradingMode` in `~/ibc/config.ini`, optionally set `TrustedIPs=127.0.0.1` in `~/Jts/.../jts.ini`, then `systemctl --user enable --now ibgateway`.
