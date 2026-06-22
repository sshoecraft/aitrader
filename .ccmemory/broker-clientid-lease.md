---
name: broker-clientid-lease
description: broker client-id via flock lease: agent PINS 40 (detected by cwd=run dir), interactive leases 110+, API=80; connect-failure releases the lease (no le…
metadata:
  type: project
tags: [broker, ibkr, clientid, flock, mcp, connection]
---

## Why this exists

Every `aitrader-broker-mcp` reads the same fixed `ibkr_client_id=40` from secrets
(the user-scope MCP registration passes NO args/env). So a SECOND broker MCP (an
interactive/ad-hoc session next to the running agent) collided on **IBKR error
326** → "pools failed to become ready." The IBKR API has **no way to enumerate
connected client-ids** — only 326 on a colliding connect — so the server can't
"ask the gateway" for a free one. We coordinate locally instead.

## Mechanism (`aitrader/brokers/clientid_lease.py`, v0.2.0; broker_server 0.10.1)

`broker()` calls `acquire_client_id()` → `(base, fd)`, then `IBKRBroker(client_id
=base)`. On connect success it calls `hold(fd)` (keep the flock for the process
life); on failure `release(fd)` (so a failed connect does NOT leak the base).
flock files live in `STATE_DIR/ibkr-clientids/<base>.lock`.

**Roles (deterministic, no env/arg):**
- **Agent pins 40** (`AGENT_CLIENT_ID`). Detected by `cwd == settings().run_dir`
  — the agent's broker MCP runs in the run dir; interactive sessions run in
  /src/aitrader etc. A stable id is REQUIRED: IBKR ties order cancel/modify
  rights to the placing clientId, so the agent must keep 40 across relays to
  manage its own resting stops.
- **Interactive/ad-hoc lease 110/140/170…** (`INTERACTIVE_BASES`, spaced 30 so
  each owns orders=base/status=base+10/data=base+20..27). They never take 40.
- **API = 80** (hardcoded in api.py, does NOT lease; 80-100 reserved, absent
  from the pools).

**Why flock:** kernel releases the lock the instant the holder dies (exit/crash/
kill -9), so a lease can't go stale — no PID checks, no reclaim, no PID-reuse
race. flock is per-host + local-disk (constitution LOCAL-DISK invariant) ✓.

## Gotchas / history

- A pre-lease agent (old code) holds gateway-40 WITHOUT an flock, so a new-code
  broker would lease 40 and still collide — the agent must run ≥0.10.0 for the
  lease to be consistent. After an agent restart it cwd-pins 40.
- Stale `<base>.lock` files persist after a holder dies (only the flock matters,
  not file existence) — reclaimed automatically.
- 32-connection gateway ceiling: each full broker (data:8)=10 conns; agent(10)+
  API(3)+1 interactive(10)=23. Room for ~1 interactive broker at a time.
- Rejected first attempt: auto-bump by colliding against the gateway and catching
  326 — slow/log-spammy; `ibkr.py` was reverted to original. See
  [[agent-state-stores-and-clean-relaunch]].
- Edge case: an interactive Claude launched FROM the run dir would be mis-detected
  as the agent and try 40 (falls through to lease if 40 busy). Unlikely.
