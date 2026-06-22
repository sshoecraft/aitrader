"""Single ib_async IB() connection wrapped in a dedicated worker thread.

CLEAN-ROOM connection ownership (BRIEF §A.3). The old driver assumed the
engine's Command module owned the IBKR connection and pumped wait(). Here the
connection OWNS ITS OWN connection: each IBKRConnection owns one IB() instance
and one persistent asyncio event loop. The worker thread IS the loop thread —
it creates the loop, connects ib_async (sync, loop not yet running), then
enters loop.run_forever() and stays there for the life of the connection. The
ib_async socket reader posts callbacks to that loop and they fire immediately
(this IS the wait()/sleep() pump, now owned here, running in its own daemon
thread). A 5s supervisor task confirms isConnected() and reconnects on drop.

submit(fn) schedules fn(ib) on the loop via loop.call_soon_threadsafe. fn may
be a sync callable returning a value, or it may return a coroutine — in which
case the coroutine is awaited on the loop and its result bridged back to the
caller's concurrent.futures.Future.

PAPER-ONLY FUSE (BRIEF §7): after the API handshake reports managed accounts,
the connection verifies every managed account id is a paper account (IBKR
paper account ids start with 'DU'; live with 'U'). If any account is not paper
it refuses — raises RuntimeError and disconnects. Overridable only by an
explicit allow_live=True, which defaults to False.

ib_async stays as the TWS wire protocol; what we own here is the
connection-management layer (threading, loop ownership, queue dispatch,
reconnect supervision, and the paper fuse).
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import Future
from typing import Callable, Optional

try:
    from ib_async import IB
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    IB = None

__version__ = "1.0.0"

log = logging.getLogger(__name__)

SHUTDOWN = object()


class PaperOnlyError(RuntimeError):
    """Raised when the connected account is not a paper account and
    allow_live was not explicitly set. This is the §7 paper-only fuse."""


def is_paper_account(account_id):
    """True if an IBKR account id is a paper account.

    IBKR paper account ids start with 'DU' (or 'DF' for paper advisor
    families); live individual accounts start with 'U'. Empty / unknown
    ids are treated as NOT paper — the fuse fails closed.
    """
    if not account_id:
        return False
    return account_id.upper().startswith(("DU", "DF"))


class IBKRConnection:
    """One ib_async IB() instance on its own worker thread + asyncio loop."""

    def __init__(self, host, port, client_id, role="data",
                 connect_timeout=30, idle_pump_seconds=None,
                 supervisor_interval_seconds=5.0, allow_live=False):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.role = role
        self.connect_timeout = connect_timeout
        # idle_pump_seconds retained as a constructor kwarg for API
        # compatibility with pool callers. It has NO effect — there is no
        # polling pump; the persistent loop delivers callbacks instantly.
        self.idle_pump_seconds = idle_pump_seconds
        self.supervisor_interval_seconds = supervisor_interval_seconds
        # PAPER-ONLY FUSE: refuse non-paper accounts unless explicitly allowed.
        self.allow_live = allow_live

        self.ib: Optional["IB"] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.ready = threading.Event()
        self.connect_error: Optional[Exception] = None

        self.in_flight_lock = threading.Lock()
        self.in_flight_count = 0
        self.healthy = False
        # Guards against the per-connection supervisor and the pool watchdog
        # both driving do_reconnect_async at the same time. Set/cleared only
        # on the loop thread, so a plain bool checked-then-set before the first
        # await is race-free.
        self.reconnecting = False

        # Observability — periodic supervisor logs these every 60s.
        self.dispatch_count = 0
        self.reconnect_count = 0
        self.last_obs_log = time.monotonic()

    @property
    def name(self):
        return f"ibkr-{self.role}-c{self.client_id}"

    @property
    def in_flight(self):
        with self.in_flight_lock:
            return self.in_flight_count

    def start(self):
        """Start the worker thread (returns immediately; use wait_ready)."""
        if self.thread is not None:
            return
        self.running = True
        self.thread = threading.Thread(
            target=self.thread_main, name=self.name, daemon=True,
        )
        self.thread.start()

    def wait_ready(self, timeout=60):
        """Block until first connect completes (success or failure).

        Returns True if connected, False on timeout.
        Raises the connect exception if connect failed (including the
        paper-only fuse PaperOnlyError).
        """
        ok = self.ready.wait(timeout=timeout)
        if not ok:
            return False
        if self.connect_error is not None:
            raise self.connect_error
        return True

    def submit(self, fn: Callable) -> Future:
        """Schedule fn(ib) on this connection's loop thread. Returns a Future.

        fn(ib) may return a value (sync) or a coroutine (async). The Future
        completes when:
          - sync fn returns → set_result with that value
          - async fn returns coroutine → coroutine awaited on the loop, its
            result/exception propagated to the Future
          - fn raises before returning → set_exception

        Increments in_flight at submit time so the pool's least-loaded
        balancer sees the load immediately.
        """
        future: Future = Future()
        if not self.running or self.loop is None or self.loop.is_closed():
            future.set_exception(ConnectionError(f"{self.name}: not running"))
            return future

        with self.in_flight_lock:
            self.in_flight_count += 1

        def runner():
            # Runs on the loop thread.
            try:
                result = fn(self.ib)
            except Exception as exc:
                self.complete_inflight()
                self.note_call_exception(exc)
                future.set_exception(exc)
                return
            if asyncio.iscoroutine(result):
                task = self.loop.create_task(result)

                def on_done(t):
                    self.complete_inflight()
                    try:
                        if t.cancelled():
                            future.cancel()
                        elif t.exception() is not None:
                            self.note_call_exception(t.exception())
                            future.set_exception(t.exception())
                        else:
                            future.set_result(t.result())
                    except Exception as exc:
                        log.error("[%s] result bridge failed: %s", self.name, exc)

                task.add_done_callback(on_done)
            else:
                self.complete_inflight()
                future.set_result(result)

        try:
            self.loop.call_soon_threadsafe(runner)
        except RuntimeError as exc:
            self.complete_inflight()
            future.set_exception(exc)
        return future

    def complete_inflight(self):
        with self.in_flight_lock:
            self.in_flight_count = max(0, self.in_flight_count - 1)
        self.dispatch_count += 1

    def note_call_exception(self, exc):
        """Ground-truth health signal from a real dispatched call.

        ib_async raises ConnectionError("Not connected") from getReqId()/send()
        BEFORE anything goes on the wire when the API handshake state is bad.
        That state can persist while the supervisor's alive() check still reads
        healthy. A failed call is the only never-blind signal: on a
        ConnectionError, take this connection out of rotation and force the
        proven reconnect path. NO order is resubmitted — the error fired
        pre-transmission. Runs on the loop thread, so guarded_reconnect can be
        scheduled directly.

        A PaperOnlyError is fatal, not a health blip — never reconnect on it.
        """
        if isinstance(exc, PaperOnlyError):
            return
        if not isinstance(exc, ConnectionError):
            return
        if self.reconnecting:
            return
        log.warning("[%s] dispatched call failed (%s) — marking unhealthy, reconnecting",
                    self.name, exc or repr(exc))
        self.healthy = False
        try:
            self.loop.create_task(self.guarded_reconnect())
        except Exception as sched_exc:
            log.error("[%s] could not schedule self-heal reconnect: %s",
                      self.name, sched_exc)

    def thread_main(self):
        """Worker thread main: own a loop, connect, run_forever.

        This thread IS the ib_async callback pump. Once run_forever() is
        active, the socket reader delivers ib_async events on this loop with
        no polling — the connection owns its own wait() pump (BRIEF §A.3).
        """
        if not HAS_IB_INSYNC:
            self.connect_error = ImportError("ib_async is required for IBKR broker")
            self.ready.set()
            return

        # Create and install this thread's asyncio loop. ib_async will use
        # asyncio.get_event_loop() and pick this one up automatically.
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Initial connect — sync, drives the loop briefly via util.run. The
        # loop is NOT running yet (run_forever hasn't been called), so the
        # sync connect path works. The paper fuse runs inside do_connect; if
        # it trips, PaperOnlyError propagates and we do NOT retry — a live
        # account will never become paper by retrying.
        delay = 5
        max_delay = 30
        attempt = 0
        while self.running:
            attempt += 1
            try:
                self.do_connect()
                self.healthy = True
                self.connect_error = None
                break
            except PaperOnlyError as exc:
                # Fatal — fuse tripped. Stop trying; surface to wait_ready.
                self.connect_error = exc
                self.running = False
                log.error("[%s] PAPER-ONLY FUSE TRIPPED: %s", self.name, exc)
                break
            except Exception as exc:
                self.connect_error = exc
                msg = repr(exc) if not str(exc) else str(exc)
                log.warning(
                    "[%s] initial connect attempt %d failed: %s — retrying in %ds",
                    self.name, attempt, msg, delay,
                )
                for _ in range(delay):
                    if not self.running:
                        break
                    time.sleep(1)
                delay = min(delay * 2, max_delay)
            if not self.running:
                break

        if not self.running:
            self.ready.set()
            self.cleanup_loop()
            return

        log.info("[%s] connected after %d attempt(s)", self.name, attempt)
        self.ready.set()

        # Schedule the supervisor coroutine — monitors connection health,
        # reconnects on drop, emits observability log every 60s. Runs forever
        # on this loop until self.running flips to False.
        supervisor_task = self.loop.create_task(self.supervisor())

        try:
            self.loop.run_forever()
        finally:
            supervisor_task.cancel()
            try:
                self.loop.run_until_complete(supervisor_task)
            except (asyncio.CancelledError, Exception):
                pass
            self.shutdown_ib()
            self.cleanup_loop()
            log.info("[%s] stopped", self.name)

    def assert_paper(self):
        """PAPER-ONLY FUSE (§7). Raise PaperOnlyError if any managed account
        on this connection is not a paper account, unless allow_live is set.

        Called on the loop thread immediately after a connect/reconnect, once
        ib_async has populated managedAccounts from the API handshake.
        """
        if self.allow_live:
            log.warning("[%s] allow_live=True — paper-only fuse DISABLED", self.name)
            return
        accounts = []
        try:
            raw = self.ib.managedAccounts()
            accounts = [a for a in raw if a]
        except Exception as exc:
            raise PaperOnlyError(
                f"{self.name}: cannot read managed accounts to verify paper "
                f"status ({exc}); refusing to proceed"
            )
        if not accounts:
            raise PaperOnlyError(
                f"{self.name}: no managed accounts reported after connect; "
                f"cannot verify paper status, refusing to proceed"
            )
        live = [a for a in accounts if not is_paper_account(a)]
        if live:
            raise PaperOnlyError(
                f"{self.name}: connected account(s) {live} are NOT paper "
                f"accounts (paper ids start with 'DU'). Refusing to trade a "
                f"live account. Pass allow_live=True to override."
            )
        log.info("[%s] paper-only fuse OK: accounts=%s", self.name, accounts)

    def alive(self):
        """True only when the connection can actually service requests.

        ib.isConnected() checks ONLY the socket-level connState. Order
        placement calls client.getReqId(), which raises
        ConnectionError("Not connected") when client.isReady() (the
        managedAccounts handshake flag) is False. A connection can sit in
        connState=CONNECTED with apiReady=False — a zombie that passes
        isConnected() but rejects every order. Health MUST gate on both.
        """
        ib = self.ib
        if ib is None:
            return False
        try:
            return bool(ib.isConnected() and ib.client.isReady())
        except Exception:
            return False

    def health_probe(self, timeout=10):
        """Active liveness probe, callable from any thread.

        Round-trips reqCurrentTime over the wire so a half-dead socket — where
        both flags still read True but the link is gone — is caught by the
        timeout. Returns True only if the full API path responds.
        """
        if not self.alive():
            return False
        future = self.submit(lambda ib: ib.reqCurrentTimeAsync())
        try:
            future.result(timeout=timeout)
            return True
        except Exception:
            return False

    async def guarded_reconnect(self):
        """Reconnect once, refusing to overlap a reconnect already running.

        Both the per-connection supervisor and the pool watchdog reach here;
        the guard keeps them from tearing down each other's fresh IB().
        Runs on the loop thread. Re-asserts the paper fuse after reconnect.
        """
        if self.reconnecting:
            return
        self.reconnecting = True
        try:
            await self.do_reconnect_async()
            self.assert_paper()
            self.healthy = True
            self.reconnect_count += 1
        finally:
            self.reconnecting = False

    def force_reconnect(self, timeout=45):
        """Drive a reconnect from another thread (the pool watchdog).

        Submits guarded_reconnect onto this connection's own loop and blocks
        for the result.
        """
        if self.loop is None or self.loop.is_closed():
            raise ConnectionError(f"{self.name}: loop not available")
        future = asyncio.run_coroutine_threadsafe(
            self.guarded_reconnect(), self.loop,
        )
        return future.result(timeout=timeout)

    async def supervisor(self):
        """Watch connection health, reconnect on drop, emit periodic obs."""
        while self.running:
            try:
                if not self.alive():
                    self.healthy = False
                    connected = self.ib is not None and self.ib.isConnected()
                    log.warning(
                        "[%s] unhealthy (connected=%s api_ready=%s) — reconnecting",
                        self.name, connected,
                        connected and self.ib.client.isReady(),
                    )
                    try:
                        await self.guarded_reconnect()
                        log.info("[%s] reconnected", self.name)
                    except PaperOnlyError as exc:
                        # Fuse tripped on reconnect — stop the connection.
                        log.error("[%s] PAPER-ONLY FUSE TRIPPED on reconnect: %s",
                                  self.name, exc)
                        self.connect_error = exc
                        self.running = False
                        self.loop.call_soon(self.loop.stop)
                        break
                    except Exception as exc:
                        log.warning("[%s] reconnect attempt failed: %s",
                                    self.name, exc)

                now = time.monotonic()
                if now - self.last_obs_log >= 60.0:
                    log.debug(
                        "[%s] dispatched=%d reconnects=%d in_flight=%d healthy=%s",
                        self.name, self.dispatch_count, self.reconnect_count,
                        self.in_flight, self.healthy,
                    )
                    self.dispatch_count = 0
                    self.reconnect_count = 0
                    self.last_obs_log = now

                await asyncio.sleep(self.supervisor_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("[%s] supervisor error: %s", self.name, exc)
                await asyncio.sleep(self.supervisor_interval_seconds)

    def do_connect(self):
        """Open a fresh IB() connection. Caller's thread must be the worker.

        Sync — uses ib_async's connect which internally runs the loop briefly
        via util.run. Safe only when loop.run_forever() has NOT been called
        yet (initial connect on thread startup). Asserts the paper-only fuse
        before returning a usable connection.
        """
        if not HAS_IB_INSYNC:
            raise ImportError("ib_async is required for IBKR broker")
        if self.ib is not None:
            try:
                self.ib.disconnect()
            except Exception:
                pass
            self.ib = None
        self.ib = IB()
        self.ib.RequestTimeout = 30
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id,
                            timeout=self.connect_timeout)
            # §7 fuse — verify paper account before this connection is usable.
            self.assert_paper()
        except Exception:
            try:
                self.ib.disconnect()
            except Exception:
                pass
            self.ib = None
            raise

    async def do_reconnect_async(self):
        """Async reconnect — runs as part of the supervisor coroutine.

        Uses ib.connectAsync because loop.run_forever() is active by now, so
        the sync ib.connect() path (which calls run_until_complete) would
        raise. Always builds a fresh IB() instance and releases the prior one
        on BOTH success and failure paths to avoid leaking a file descriptor
        per failed retry.
        """
        if self.ib is not None:
            try:
                self.ib.disconnect()
            except Exception:
                pass
            self.ib = None
        self.ib = IB()
        self.ib.RequestTimeout = 30
        try:
            await self.ib.connectAsync(
                self.host, self.port, clientId=self.client_id,
                timeout=self.connect_timeout,
            )
        except Exception:
            try:
                self.ib.disconnect()
            except Exception:
                pass
            self.ib = None
            raise

    def shutdown_ib(self):
        if self.ib is not None:
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
            except Exception:
                pass

    def cleanup_loop(self):
        if self.loop is None or self.loop.is_closed():
            return
        try:
            pending = [t for t in asyncio.all_tasks(self.loop) if not t.done()]
            for t in pending:
                t.cancel()
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except Exception:
            pass
        try:
            self.loop.close()
        except Exception:
            pass

    def stop(self):
        """Signal the worker to shut down and wait briefly for join."""
        if not self.running:
            return
        self.running = False
        if self.loop is not None and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                pass
        if self.thread is not None:
            self.thread.join(timeout=10)
