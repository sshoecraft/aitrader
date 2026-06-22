---
name: dashboard-default-ports-2499-2500
description: 1.2.0: default dashboard ports 7500/7501 → 2499/2500; ui_port is now its own config DEFAULTS key + Settings.ui_port property (no longer api_port+1)
metadata:
  type: project
---

## What changed (1.2.0)
Default dashboard ports moved **7500/7501 → 2499 (api) / 2500 (ui)**, and **`ui_port`
is now a first-class setting** — its own key in `config.py` `DEFAULTS` (`2500`) with a
real `Settings.ui_port` property. It is **no longer derived as `api_port + 1`**.

## Why
- 7500 is a round number in the contended 7000–9000 band other dev tooling grabs;
  "round + default" maximizes collision odds. 2499/2500 is low, memorable, quiet. UI
  gets the round/memorable 2500 (what a human types in a browser), API gets 2499.
- Both clear of privileged (<1024) and ephemeral (49152+) ranges. Checked: neither is
  on the Chrome/Firefox `ERR_UNSAFE_PORT` block list (nearby **2049/NFS IS blocked**,
  6000/X11 is too — 2499/2500 are not), so the UI loads in a browser.
- The hidden `ui = api+1` coupling was fragile: a stray service on `api_port+1`
  silently broke the UI. Now both ports are explicit.

## Motivation (the incident)
A real port-collision poisoned the journal: on clyde, the production aitrader (IBKR)
and a leftover **tester** instance (Alpaca, a leftover tester) BOTH defaulted
to `0.0.0.0:7500`. When the prod API restarted during an install, the tester grabbed
the port; `bin/aitrader-snapshot` (which blindly trusts whatever answers
`127.0.0.1:7500`) then recorded the tester's Alpaca equity into the prod IBKR journal.
Moving prod to 2499/2500 sidesteps the default-collision. Still-open hardening: the
recorder/API should verify the `/status` account matches the configured execution
account before recording (never trust a port you didn't bind). See [[no-biasing]] only
loosely; root issue is identity-trust, not bias.

## Files touched
`aitrader/config.py` (DEFAULTS + `ui_port` property), `bin/aitrader-ui` (reads
`s.ui_port`, no `+1`), `ui/src/api.ts` (dev fallback 2499), `install.sh`
(API_PORT=2499/UI_PORT=2500; `ui_port` line only written when non-empty),
`settings.toml.example`, `README.md`, `docs/ui.md`, `aitrader/api.py` docstrings,
both systemd unit comments, `state.md`, `CHANGELOG.md`.

## Migration
Existing installs unaffected (they have explicit ports in settings.toml, or keep what
they set). Only a fresh install with no ports specified picks up 2499/2500. Two stacks
on one host must STILL set distinct pairs — a better default lowers collision odds, it
does not prevent two same-defaulted instances from colliding. Related:
[[aitrader-product-packaging-1.0]].
