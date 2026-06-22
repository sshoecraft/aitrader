---
name: install-tilde-leftover-pip-purge
description: 1.1.2: install.sh purges "~"-prefixed pip leftovers (cause of "Ignoring invalid distribution ~eventkit" + false "aeventkit not installed"); tzdata pi…
metadata:
  type: project
---

## Symptom (reported on a tester `./install`)
```
WARNING: Ignoring invalid distribution ~eventkit (...site-packages)   # repeated per pip call
ib-async 2.1.0 requires aeventkit<3.0.0,>=2.1.0, which is not installed.
ib-async 2.1.0 requires tzdata<2026.0,>=2025.2, but you have tzdata 2026.2 ...
```

## Root cause — orphaned "~"-prefixed dist-info backups
`PIP_FLAGS="--user --break-system-packages --force-reinstall"` (install.sh:118) uninstalls→reinstalls
every dep each run. pip renames a dist-info to a backup before deleting it; the backup name takes
**two forms**: `~name` (tilde prepended) AND `~ame` (first char replaced by `~`). If the delete is
interrupted, or a rename churns it — as with the `eventkit`→`aeventkit` fork that ib-async 2.x
depends on — the backup is stranded. pip then spams `Ignoring invalid distribution ~xxx` on every
invocation AND reports a **false** `requires aeventkit, which is not installed` conflict even though
`aeventkit-2.1.0.dist-info` is present and `import eventkit`/`import ib_async` work. `importlib.metadata`
saw aeventkit 2.1.0 the whole time — only pip's scan was confused. On the tester there were two
stranded dirs: `~eventkit-2.1.0.dist-info` and `~ventkit` — note `grep eventkit` MISSES `~ventkit`.

## Fix (1.1.2)
install.sh now purges `"$USER_SITE"/~*` (via `site.getusersitepackages()`) right before the pip
install. Removing these backups is always safe — they are stale copies of an already-valid dist-info.
Deleting them made `pip check` drop both lines instantly.

## tzdata line is cosmetic, intentionally NOT fixed
`ib-async 2.1.0 has requirement tzdata<2026.0` is ib-async's over-tight upper pin on the IANA tz db;
ib_async imports/runs fine against 2026.2. aitrader's `tzdata` dep stays **unpinned** (a trader wants
freshest tz rules) rather than held back for a transitive cap. Pin `tzdata>=2025.2,<2026.0` in
pyproject only if a spotless `pip check` is ever required. Related: [[aitrader-product-packaging-1.0]].
