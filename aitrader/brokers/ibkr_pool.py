"""Pool of IBKRConnections with method-aware routing.

The pool holds N IBKRConnections (each one ib_async IB() on its own worker
thread + asyncio loop) and exposes a small synchronous API:

  pool.run(fn) ........... least-loaded healthy connection, block for result
  pool.run_pinned(key, fn) connection previously pinned to `key`, else fallback
  pool.scatter_run(fn) ... every healthy connection, merged into a list
  pool.pin(key, conn) .... record (key -> connection) for run_pinned
  pool.reconnect_all() ... request reconnect on every connection
  pool.stop() ............ stop every connection

Used internally by IBKRBroker. The pool threads the paper-only fuse flag
(allow_live) down to every connection it owns.
"""

import logging
import threading
import time
from concurrent.futures import Future
from typing import Callable, List, Optional

from aitrader.brokers.ibkr_connection import IBKRConnection

__version__ = "1.0.0"

log = logging.getLogger(__name__)


class IBKRConnectionPool:
    """A pool of IBKRConnections all targeting the same Gateway."""

    def __init__(self, host, port, client_ids, role,
                 connect_stagger_ms=250, connect_timeout=30,
                 idle_pump_seconds=None, watchdog_interval=20,
                 watchdog_probe_timeout=10, watchdog_fail_threshold=2,
                 allow_live=False):
        if not client_ids:
            raise ValueError(f"pool '{role}' needs at least one client_id")
        self.host = host
        self.port = port
        self.client_ids = list(client_ids)
        self.role = role
        self.connect_stagger_ms = connect_stagger_ms
        self.connect_timeout = connect_timeout
        self.idle_pump_seconds = idle_pump_seconds
        self.allow_live = allow_live

        # Independent pool watchdog: an external thread (NOT the per-connection
        # loops) that actively probes every connection and force-reconnects any
        # that fail. The per-connection supervisor handles fast clean drops;
        # this is the backstop for apiReady zombies and half-dead sockets, and
        # works even if a supervisor task has stopped scheduling, because
        # force_reconnect drives the connection's own loop from the outside.
        # Set watchdog_interval<=0 to disable (tests).
        self.watchdog_interval = watchdog_interval
        self.watchdog_probe_timeout = watchdog_probe_timeout
        self.watchdog_fail_threshold = watchdog_fail_threshold
        self.watchdog_running = False
        self.watchdog_thread = None

        conn_kwargs = {}
        if idle_pump_seconds is not None:
            conn_kwargs["idle_pump_seconds"] = idle_pump_seconds

        self.connections: List[IBKRConnection] = [
            IBKRConnection(
                host=host, port=port, client_id=cid, role=role,
                connect_timeout=connect_timeout,
                allow_live=allow_live,
                **conn_kwargs,
            )
            for cid in self.client_ids
        ]
        self.pin_lock = threading.Lock()
        self.pinned: dict = {}  # key -> IBKRConnection
        self.rr_counter = 0
        self.rr_lock = threading.Lock()

    @property
    def name(self):
        return f"pool-{self.role}"

    @property
    def size(self):
        return len(self.connections)

    def start(self):
        """Start all worker threads, staggered to avoid Gateway login throttle."""
        log.info("[%s] starting %d connection(s)", self.name, len(self.connections))
        for i, conn in enumerate(self.connections):
            if i > 0 and self.connect_stagger_ms > 0:
                time.sleep(self.connect_stagger_ms / 1000.0)
            conn.start()
        self.start_watchdog()

    def start_watchdog(self):
        """Launch the independent watchdog thread (idempotent)."""
        if self.watchdog_interval <= 0 or self.watchdog_thread is not None:
            return
        self.watchdog_running = True
        self.watchdog_thread = threading.Thread(
            target=self.watchdog_loop, name=f"{self.name}-watchdog", daemon=True,
        )
        self.watchdog_thread.start()

    def watchdog_loop(self):
        """Probe every connection on an interval; force-reconnect the dead.

        Acts only after watchdog_fail_threshold CONSECUTIVE probe failures so
        a single slow/busy probe doesn't tear down a healthy connection
        mid-order.
        """
        fails = {}
        while self.watchdog_running:
            time.sleep(self.watchdog_interval)
            if not self.watchdog_running:
                break
            for conn in self.connections:
                if not self.watchdog_running:
                    break
                try:
                    ok = conn.health_probe(timeout=self.watchdog_probe_timeout)
                except Exception as exc:
                    log.warning("[%s] watchdog probe error on %s: %s",
                                self.name, conn.name, exc)
                    ok = False
                if ok:
                    fails[conn.name] = 0
                    continue
                fails[conn.name] = fails.get(conn.name, 0) + 1
                conn.healthy = False
                if fails[conn.name] < self.watchdog_fail_threshold:
                    log.warning("[%s] watchdog: %s failed probe (%d/%d)",
                                self.name, conn.name, fails[conn.name],
                                self.watchdog_fail_threshold)
                    continue
                log.error("[%s] watchdog: %s dead — forcing reconnect",
                          self.name, conn.name)
                try:
                    conn.force_reconnect(
                        timeout=self.watchdog_probe_timeout + self.connect_timeout + 5)
                    if conn.health_probe(timeout=self.watchdog_probe_timeout):
                        fails[conn.name] = 0
                        log.info("[%s] watchdog: %s reconnected", self.name, conn.name)
                    else:
                        log.error("[%s] watchdog: %s STILL dead after reconnect",
                                  self.name, conn.name)
                except Exception as exc:
                    log.error("[%s] watchdog: %s reconnect failed: %s",
                              self.name, conn.name, exc)

    def wait_ready(self, timeout=60):
        """Block until every connection is connected (or one fails).

        Returns True if all healthy. Raises the first connection's connect
        error if any fail (including the paper-only fuse PaperOnlyError).
        """
        per_timeout = max(1, timeout)
        for conn in self.connections:
            ok = conn.wait_ready(timeout=per_timeout)
            if not ok:
                return False
        return all(c.healthy for c in self.connections)

    def healthy_connections(self) -> List[IBKRConnection]:
        return [c for c in self.connections if c.healthy]

    def pick(self) -> IBKRConnection:
        """Pick the least-loaded healthy connection; round-robin tiebreak."""
        healthy = self.healthy_connections()
        if not healthy:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                time.sleep(0.1)
                healthy = self.healthy_connections()
                if healthy:
                    break
            if not healthy:
                raise ConnectionError(
                    f"[{self.name}] no healthy connections "
                    f"(of {len(self.connections)})"
                )
        if len(healthy) == 1:
            return healthy[0]
        min_load = min(c.in_flight for c in healthy)
        candidates = [c for c in healthy if c.in_flight == min_load]
        if len(candidates) == 1:
            return candidates[0]
        with self.rr_lock:
            idx = self.rr_counter % len(candidates)
            self.rr_counter += 1
        return candidates[idx]

    def submit(self, fn: Callable) -> Future:
        """Pick a connection, submit fn(ib), return Future."""
        return self.pick().submit(fn)

    def run(self, fn: Callable, timeout: Optional[float] = 60,
            pin_key_extractor: Optional[Callable] = None):
        """Submit fn(ib) on least-loaded healthy connection. Block for result.

        If pin_key_extractor(result) returns a non-None key, the connection
        that served the call is pinned to that key for future run_pinned
        lookups.
        """
        conn = self.pick()
        future = conn.submit(fn)
        result = future.result(timeout=timeout)
        if pin_key_extractor is not None:
            try:
                key = pin_key_extractor(result)
            except Exception as exc:
                log.warning("[%s] pin_key_extractor failed: %s", self.name, exc)
                key = None
            if key is not None:
                self.pin(key, conn)
        return result

    def run_pinned(self, key, fn: Callable, timeout: Optional[float] = 60):
        """Submit fn(ib) on the connection pinned to `key`.

        Falls back to trying each healthy connection in turn if no pin exists
        or the pinned connection is unhealthy.
        """
        conn = self.find_pinned(key)
        if conn is not None and conn.healthy:
            future = conn.submit(fn)
            return future.result(timeout=timeout)
        last_exc = None
        for c in self.healthy_connections():
            try:
                future = c.submit(fn)
                result = future.result(timeout=timeout)
                self.pin(key, c)
                return result
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc
        raise ConnectionError(f"[{self.name}] no connection could serve key={key}")

    def scatter_run(self, fn: Callable, timeout: Optional[float] = 60) -> list:
        """Run fn(ib) on every healthy connection. Returns list of results.

        Per-connection exceptions are logged and swallowed (return value
        omitted). If every connection raises, the last exception is re-raised.

        `timeout` bounds the TOTAL wall-clock of the scatter, not each
        connection independently. All connections are dispatched up front so
        they run concurrently; results are collected against a single shared
        deadline. A stalled connection costs at most ~`timeout` for the whole
        call — never `timeout` × N.
        """
        healthy = self.healthy_connections()
        if not healthy:
            raise ConnectionError(f"[{self.name}] no healthy connections")
        futures = [(c, c.submit(fn)) for c in healthy]
        deadline = None if timeout is None else time.monotonic() + timeout
        results = []
        last_exc = None
        for conn, future in futures:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                results.append(future.result(timeout=remaining))
            except Exception as exc:
                log.warning("[%s] scatter call failed on %s: %s",
                            self.name, conn.name, exc)
                last_exc = exc
        if not results and last_exc is not None:
            raise last_exc
        return results

    def pin(self, key, conn: IBKRConnection):
        with self.pin_lock:
            self.pinned[key] = conn

    def find_pinned(self, key) -> Optional[IBKRConnection]:
        with self.pin_lock:
            return self.pinned.get(key)

    def unpin(self, key):
        with self.pin_lock:
            self.pinned.pop(key, None)

    def reconnect_all(self):
        """Force every connection to drop and reconnect. Used by hard recovery."""
        for conn in self.connections:
            try:
                if conn.ib is not None:
                    conn.ib.disconnect()
            except Exception:
                pass

    def stop(self):
        self.watchdog_running = False
        if self.watchdog_thread is not None:
            self.watchdog_thread.join(timeout=5)
            self.watchdog_thread = None
        for conn in self.connections:
            conn.stop()


def merge_by_id(lists_of_dicts, id_key) -> list:
    """Merge a list-of-lists of dicts, dedupe by `id_key`. Order-preserving."""
    seen = set()
    out = []
    for lst in lists_of_dicts:
        if not lst:
            continue
        for item in lst:
            ident = item.get(id_key) if isinstance(item, dict) else None
            if ident is None:
                out.append(item)
                continue
            if ident in seen:
                continue
            seen.add(ident)
            out.append(item)
    return out
