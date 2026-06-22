---
name: aitrader-ibkr-extra-ib-async
description: aitrader's ib_async is an optional 'ibkr' extra only installed via --broker ibkr; flipping settings.toml broker=ibkr later does NOT pull it
metadata:
  type: project
---

aitrader (the IBKR *client*, repo `/src/aitrader`) declares `ib_async` as an **optional** dependency, not a base one:

```toml
[project.optional-dependencies]
ibkr = ["ib_async>=2.0.0"]
```

aitrader's `install.sh` only adds that extra when invoked with `--broker ibkr` (install.sh: `[ "$BROKER" = "ibkr" ] && EXTRAS="$EXTRAS,ibkr"`, then `pip install ${WHL}[${EXTRAS}]`).

**Footgun:** if aitrader was installed with the default broker (alpaca) and you later switch by editing `~/.config/aitrader/settings.toml` to `broker = "ibkr"`, `ib_async` is NOT retroactively installed. The IBKR adapter then fails at runtime: "IBKR adapter requires ib_async which isn't installed" — blocks the whole cycle.

**Env facts:** aitrader runs from `/usr/bin/python3` with user site-packages — entry point `~/.local/bin/aitrader` (shebang `#!/usr/bin/python3`), installed via `pip install --user --break-system-packages` (Ubuntu 24.04 / PEP 668 externally-managed). aitrader itself lives in `~/.local/lib/python3.12/site-packages/aitrader/` (installed wheel, not editable from /src).

**Fix applied (2026-06-20):** `python3 -m pip install --user --break-system-packages "ib_async>=2.0.0"` → got ib_async 2.1.0 + aeventkit + nest_asyncio. Side effect: downgraded `tzdata` 2026.2 → 2025.3 (ib_async pins `tzdata<2026.0`); harmless tz data. Verified: `import ib_async` and `import aitrader.brokers.ibkr` both clean, and a real ib_async handshake to 127.0.0.1:4002 returned paper account DU0000000 (server v178).

Alternative durable fix: re-run aitrader's `./install.sh --broker ibkr`. Relates to [[install-sh-gateway-ibc-layout]] (the gateway side).
