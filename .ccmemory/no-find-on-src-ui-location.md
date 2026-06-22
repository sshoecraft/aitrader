---
name: no-find-on-src-ui-location
description: NEVER run `find` (or recursive scans) over /src — it's NFS, huge/slow. The aitrader dashboard UI source lives at /src/aitrader/ui/, not /src/trader-u…
metadata:
  type: feedback
---

**Never run `find` over `/src`** (or any broad recursive scan rooted there). `/src`
is NFS (see [[src-nfs-all-squash-root]]) — it's huge and slow, and scanning it is
a waste. Scope filesystem searches to the specific project dir or a known
subpath, or use a path you already know. If you don't know where something is,
ask or check the obvious project-relative location first.

**The aitrader dashboard UI source is `/src/aitrader/ui/`** (project-relative
`./ui/`). It is NOT `/src/trader-ui` (that's a different, shared project I wrongly
assumed). When reconciling what the dashboard *displays* (labels, derived fields
like "Total P&L") against what `api.py` serves, read `./ui/` here.

**Why:** the user explicitly corrected both — got an interrupt for `find … /src …`.
**How to apply:** for UI questions on aitrader, grep under `/src/aitrader/ui/src`;
never `find /src`.</body>
