"""Cross-process IBKR client-id lease.

The gateway assigns each API connection a unique clientId and offers NO way to
enumerate which are in use — the only signal is error 326 on a colliding
connect. Several aitrader broker processes share one gateway (the agent's MCP,
any interactive MCP), so each must claim a distinct clientId *base*.

Coordination is via advisory file locks (flock): each candidate base has a lock
file under STATE_DIR/ibkr-clientids/; a process flock()s the first it can and
HOLDS THE FD OPEN for its whole life. The kernel releases the lock the instant
the holder dies — clean exit, crash, kill -9 — so a lease can never go stale:
no PID bookkeeping, no reclaim sweep, no PID-reuse race.

Roles:
  * The AGENT pins a stable id (40). Its broker MCP runs with cwd = the run dir
    (interactive sessions don't), so we detect it that way. A stable id matters:
    IBKR ties cancel/modify rights to the clientId that placed an order, so the
    agent must keep the same id across relays to manage its own resting orders.
  * Interactive / ad-hoc brokers lease from INTERACTIVE_BASES (110+) and never
    touch 40.
  * The dashboard API hardcodes 80 (api.py) and does not lease — 80-100 is its
    reserved slot, absent from the pools below.

Bases are spaced 30 so each owns a full pool slot (orders=base, status=base+10,
data=base+20..+27 for data:8). flock is per-host (all clients share this node)
and unreliable on NFS, but STATE_DIR is local disk (constitution LOCAL-DISK
invariant) — both hold.
"""

__version__ = "0.2.0"

import fcntl
import logging
import os

from aitrader.config import settings

log = logging.getLogger(__name__)

# Stable id reserved for the agent (matches secrets.toml ibkr_client_id).
AGENT_CLIENT_ID = 40
# Lease pool for everyone else. Spaced 30; clears the agent (40-67) and the
# API's reserved 80-100.
INTERACTIVE_BASES = [110, 140, 170, 200, 230, 260, 290]

# Leases held for the life of THIS process. Never closed explicitly on success —
# process exit releases them (that is the staleness-proof mechanism).
_held_fds = []


def lease_dir():
    return os.path.join(settings().state_dir, "ibkr-clientids")


def _try_lock(base):
    """Return an flock-held fd for `base`, or None if a live process holds it."""
    d = lease_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{base}.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)  # held by a live process
        return None
    try:  # stamp pid for human observability only (NOT correctness — flock is)
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
    except OSError:
        pass
    return fd


def _is_agent():
    """The agent's broker MCP runs with cwd = the run dir; interactive sessions
    do not. Used only to reserve the stable AGENT_CLIENT_ID for the agent."""
    try:
        return os.path.realpath(os.getcwd()) == os.path.realpath(settings().run_dir)
    except Exception:
        return False


def acquire_client_id():
    """Claim a client-id base; return (base, fd).

    The fd IS the lease. On a successful connect the caller must `hold(fd)` (keep
    it open for the process life); if the connect fails the caller must
    `release(fd)` so the base is not leaked. The agent (run dir) tries its stable
    id 40 first; everyone else — and the agent if 40 is somehow busy — leases the
    first free base from 110+.
    """
    candidates = ([AGENT_CLIENT_ID] if _is_agent() else []) + INTERACTIVE_BASES
    for base in candidates:
        fd = _try_lock(base)
        if fd is not None:
            log.info("[clientid-lease] claimed base %d%s", base,
                     " (agent)" if base == AGENT_CLIENT_ID else "")
            return base, fd
    raise RuntimeError(
        f"[clientid-lease] no free IBKR client-id base — tried {candidates}")


def hold(fd):
    """Retain a lease for the process lifetime — call after a successful connect."""
    _held_fds.append(fd)


def release(fd):
    """Release a lease — call if the connect fails, so the base is not leaked."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass
