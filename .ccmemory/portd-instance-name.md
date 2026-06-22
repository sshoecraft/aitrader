---
name: portd-instance-name
description: 1.5.0: portd registration name is now per-instance via settings.toml portd_name (default "&lt;unix-user&gt;-aitrader"); was hardcoded aitrader/aitrad…
metadata:
  type: project
---

## What (supersedes the hardcoded names in [[portd-dynamic-port-allocation]])

Through 1.3.0 the portd registration names were **hardcoded**: UI = `aitrader`, API =
`aitrader-api`. On a shared host running >1 stack (the real case: an `alpaca` Unix user and an
`ibkr` Unix user, **one broker per settings.toml**) both registered under the SAME names. portd
is keyed by name, so whichever service started **second** made its `allocate()` clobber the
first's reverse-proxy route → only one dashboard reachable.

## Fix (1.5.0)

New `settings.toml` key **`portd_name`**. UI registers under `<portd_name>` (path
`/<portd_name>/`); API under `<portd_name>-api` (path `/<portd_name>-api/`); the UI's
`--api-base` becomes `/<portd_name>-api`.

- **Default** (key empty/absent): `aitrader/config.py` `portd_name` property derives
  `f"{getpass.getuser()}-aitrader"` → `alpaca-aitrader`, `ibkr-aitrader`. Collision-proof (OS =
  one running user per name), so the two-stack case is fixed with **zero config**. NB: a user
  literally named `aitrader` yields `aitrader-aitrader` (ugly but unique).
- **Override**: explicit value wins, e.g. `portd_name = "bingleboss"` → `/bingleboss/` +
  `/bingleboss-api/`.

## Touched

`aitrader/config.py` (DEFAULTS `portd_name=""` + property + `import getpass`), `aitrader/api.py`
(`PORTD_NAME = f"{s.portd_name}-api"`), `bin/aitrader-ui` (`ui_name=s.portd_name`,
`api_name=f"{s.portd_name}-api"`), both systemd units' `ExecStopPost` (deregister now derives
from `settings().portd_name`). Source change only — deploy needs `./install.sh` + `make ui`
(UI rebuild for the new `--api-base` path) + restart aitrader-api/ui, and each user sets (or
relies on the derived default for) `portd_name` in their own settings.toml.
