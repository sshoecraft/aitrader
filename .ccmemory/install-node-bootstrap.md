---
name: install-node-bootstrap
description: install.sh ensure_node() auto-downloads pinned Node 22.21.1 to ~/.cache/aitrader when no npm; make ui now reuses that cache too (1.7.4).
metadata:
  type: project
---

## Node is a build-time-only dep the installer now satisfies itself

`ui/dist` is **git-ignored** (see `ui/.gitignore`) → never shipped. The dashboard
UI must be built with node/npm (vite+tsc). Before 1.7.2 a node-less box (anyone
who just cloned the repo) silently got no dashboard: `install.sh` skipped it and
`make ui` died sourcing `$HOME/.nvm/nvm.sh`.

As of **1.7.2**, `install.sh` has `ensure_node()` (+ a `fetch()` curl/wget helper,
mirroring `gateway/install.sh`): if `npm` isn't on PATH it downloads a **pinned**
official Node (`NODE_VERSION`, 22.21.1) for the detected OS/arch (linux|darwin ×
x64|arm64) into `${XDG_CACHE_HOME:-~/.cache}/aitrader/node-v<ver>-<os>-<arch>/`,
prepends its `bin` to PATH for the build only, reuses it next time. Node is NEVER
needed at runtime (agent/MCP/API are pure python); it's purely to build the UI.
Falls back to prebuilt-`dist`/skip on no-network or unsupported platform.

Implications:
- **`make ui` no longer hard-assumes nvm** (fixed 1.7.4, with explicit user
  permission to edit the Makefile). The recipe now resolves npm in order:
  system `npm` on PATH → `$HOME/.nvm/nvm.sh` if present → the install.sh cache
  `${XDG_CACHE_HOME:-~/.cache}/aitrader/node-v$(NODE_VERSION)-linux-x64/bin`,
  else errors telling you to run `./install.sh` once to bootstrap node. `make ui`
  builds + redeploys to `~/.local/share/aitrader/ui` + `systemctl --user restart
  aitrader-ui` ONLY (never touches `aitrader.service`). A `NODE_VERSION := 22.21.1`
  var was added to the Makefile — **keep it in sync with install.sh's NODE_VERSION**.
- Node-free UI redeploy also works via `./install.sh --build-ui` (auto-gets node).
- To bump the bundled Node, change `NODE_VERSION` in BOTH `install.sh` and the `Makefile`.
- The stale-`dist` rebuild trigger (source newer than `ui/dist/index.html`) +
  `--build-ui` both route through `ensure_node`.

Related: [[aitrader-ui-build-deploy]] [[install-sh-gateway-ibc-layout]]
[[aitrader-product-packaging-1.0]] [[no-find-on-src-ui-location]]
