"""portd integration — dynamic port allocation via the local Caddy `portd` admin API.

If portd is running on this host, a dashboard service asks it for a port by name
(`allocate`) and portd reverse-proxies `/<name>/` to it. If portd is NOT running,
the caller falls back to its configured default port. Pure infra — no trading logic.

Design constraints (see CLAUDE.md, and the operator's brief):
- The probe MUST be quick and MUST NEVER hang service start. We use a hard 1s
  timeout; a missing portd refuses the TCP connect instantly, so the common
  "portd not installed" path returns in milliseconds, never the timeout.
- Every function is best-effort: it never raises. On any failure the caller gets
  None (allocate) / the default (resolve_port), i.e. plain non-portd behavior.
"""
import json
import urllib.error
import urllib.request

# Caddy's admin API (the portd plugin lives under /portd/*). Localhost only.
PORTD_ADMIN = "http://127.0.0.1:2019"
# Quick — a portd probe must not stall a systemd service start.
TIMEOUT = 1.0


def _request(method, path, payload=None, timeout=TIMEOUT):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        PORTD_ADMIN + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return json.loads(body) if body else {}


def allocate(name, timeout=TIMEOUT):
    """Ask portd for a port for `name` and register its `/<name>/` route.

    Idempotent: if `name` is already registered, returns its existing port. The
    call doubles as the "is portd up?" probe — returns None (fast) when portd is
    absent, so callers can `allocate(name) or default`. Never raises.
    """
    try:
        resp = _request("POST", "/portd/allocate", {"name": name}, timeout=timeout)
        port = resp.get("port")
        return int(port) if port else None
    except Exception:
        return None


def deregister(name, timeout=TIMEOUT):
    """Remove `name`'s portd registration + route. Best-effort; never raises."""
    try:
        _request("DELETE", "/portd/deregister", {"name": name}, timeout=timeout)
        return True
    except Exception:
        return False


def resolve_port(name, default, timeout=TIMEOUT):
    """The port this service should bind: portd-allocated if portd is up, else
    `default`. One call — `allocate`'s own timeout is the probe."""
    return allocate(name, timeout=timeout) or default
