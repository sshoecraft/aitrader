---
name: gateway-merged-into-subdir
description: 1.6.0: former standalone aitrader-ibkr-gateway repo merged INTO aitrader as gateway/ subdir; ./install.sh --broker ibkr descends into gateway/install…
metadata:
  type: project
tags: [gateway, ibkr, install, packaging, architecture]
---

As of aitrader **1.6.0 (2026-06-20)** the IBKR gateway server is **no longer a separate repo**. The old `/src/aitrader-ibkr-gateway` was moved wholesale into `/src/aitrader/gateway/` (README.md, install.sh, docs/, ibc/, systemd/ibgateway.service, .gitignore) and the old repo dir was removed.

**Why merged (the deciding reason):** the release model is **lockstep** — aitrader is only released after being tested against a *specific* gateway version, and the gateway must never update out from under aitrader. A sibling repo with an independent lifecycle fought that; one tree pins them together by construction. Earlier "keep it separate" arguments were dropped as moot: the IB Gateway (~320MB) + IBC binaries are **downloaded at install time, never shipped in the tree**, and independent lifecycle was a *liability* here, not a benefit. (Considered git submodule for the same lockstep + standalone existence, but the gateway does not need to stand alone, so a plain subdir is simpler — no submodule pointer ceremony.)

**Wiring:** `./install.sh --broker ibkr` now runs a "Set up IBKR gateway" step that descends into `gateway/install.sh` (`( cd "$SRC_DIR/gateway" && ./install.sh )`). New flag `--no-gateway` opts out. The gateway installer is self-contained + idempotent and stops at its own credentials / paper-vs-live gate, so the conscious human consent step is preserved. **Alpaca/MYSE installs never touch `gateway/`** — the dependency-isolation property is intact (no X/font deps, no binaries pulled).

**Docs updated:** README.md (intro, requirements, brokers table, IBKR install note, layout), SETUP.md, docs/broker-mcp.md, gateway/README.md (reframed separate-repo → bundled subdir; `cd` paths fixed to `/src/aitrader/gateway`). The gateway's two ccmemory notes were folded into this repo's store ([[install-sh-gateway-ibc-layout]], [[aitrader-ibkr-extra-ib-async]]).

**Left undone on purpose:** the `Makefile` still has 3 stale comment/echo references to `aitrader-ibkr-gateway` (lines ~33, 66, 101) — NOT edited, per the standing hard rule "do not edit the Makefile unless explicitly told." Flagged to the user for a follow-up green-light.
