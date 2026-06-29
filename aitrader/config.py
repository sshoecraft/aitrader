"""Configuration — XDG defaults, overridable via settings.toml. NO env vars.

aitrader is NOT configured through environment variables. Every setting has a
default following the XDG base-directory layout, and ANY of them can be
overridden in the config file:

    ~/.config/aitrader/settings.toml

That config-file path is the one fixed location (it's where the overrides live,
so it can't itself be overridden by them). Secrets (IBKR connection) stay in a
separate ~/.config/aitrader/secrets.toml — config here is non-secret.

Every process (harness + each MCP server) loads this independently at startup,
so they all agree without anything being passed between them. Change a value,
restart the service.

Example settings.toml (all keys optional — shown values are the defaults):

    # data_dir  = "~/.local/share/aitrader"
    # state_dir = "~/.local/state/aitrader"
    wake_floor_seconds = 5          # cadence fuse: shortest wake the scheduler allows
    allow_live         = false      # paper-only fuse; true is REFUSED unless you mean it
    # portd_name       = "alpaca"   # portd route name; default "<unix-user>-aitrader"

The MODEL is NOT here — it's a Claude-session setting in the ccloop run dir's
.claude/settings.json (the runtime is ccloop, see CLAUDE.md).
"""

__version__ = "0.3.0"

import getpass
import os
import tomllib
from functools import lru_cache

HOME = os.path.expanduser("~")

# Fixed: the config directory and the settings file within it. Everything else
# defaults relative to XDG and may be overridden inside settings.toml.
CONFIG_DIR = os.path.join(HOME, ".config", "aitrader")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.toml")

# NOTE: model + the claude binary are NOT configured here — the runtime is
# ccloop, and those are Claude-session concerns (the run dir's
# .claude/settings.json sets the model; ccloop owns the claude binary). This
# file configures only the aitrader runtime the MCP servers read.
DEFAULTS = {
    "data_dir": os.path.join(HOME, ".local", "share", "aitrader"),
    "state_dir": os.path.join(HOME, ".local", "state", "aitrader"),
    "wake_floor_seconds": 5.0,
    "allow_live": False,
    # EXECUTION broker backend: "ibkr" (default), "alpaca", or "myse". Selects
    # where orders/positions/account live. Mirrors /src/trader's `broker` setting.
    "broker": "ibkr",
    # Optional market-DATA broker (separate from execution). None -> the
    # execution broker serves data too. "alpaca" -> route the data_broker_types'
    # bars/snapshots to Alpaca (better pre-market + full-tape coverage). Mirrors
    # /src/trader's broker + data_broker split.
    "data_broker": None,
    # Which asset types' market data the data_broker serves; the rest stay on
    # IBKR. Alpaca only covers stock + crypto (no forex/futures).
    "data_broker_types": ["stock", "crypto"],
    # Alpaca stock data feed: "iex" (real-time, but only IEX's ~2.5% of volume)
    # or "sip" (full consolidated tape, but a free/basic plan delays it ~15 min
    # AND blocks recent SIP entirely). Default IEX so intraday bars/snapshots are
    # REAL-TIME — a 15-min-stale tape is useless for momentum. Set "sip" only on
    # a SIP-entitled (paid) plan, where it gives full-volume real-time data.
    "alpaca_data_feed": "iex",
    # explicit path overrides; "" -> derived from data_dir/state_dir/CONFIG_DIR
    "secrets_path": "",
    "journal_db": "",
    "prompts_dir": "",
    "run_dir": "",
    # ccloop invocation. criteria + task are the two ccloop positional args (text
    # in settings.toml). ccloop_cutoff = relay cutoff in thousands of tokens.
    "criteria": "",
    "task": "",
    "ccloop_cutoff": 500,
    # dashboard API server (UI backend). Default product port block is 2499 (api)
    # + 2500 (ui) — low + memorable, and out of the contended 7000-9000 range that
    # other dev tooling grabs. ui_port is its OWN DEFAULTS key, NOT derived as
    # api_port+1: a hidden +1 coupling is fragile (one stray service on api_port+1
    # silently breaks the UI), so both ports are explicit.
    "api_host": "0.0.0.0",
    "api_port": 2499,
    "ui_port": 2500,
    # portd registration name (Caddy dynamic-port plugin). The UI registers under
    # this name (public path /<portd_name>/) and the API under "<portd_name>-api".
    # MUST be unique per stack on a shared host: portd is keyed by name, so two
    # instances sharing a name make the second's allocate() overwrite the first's
    # route. Empty ("") -> auto-derive "<unix-user>-aitrader" (see portd_name
    # property), which is collision-proof since the OS guarantees one running
    # user per name. Set explicitly for a descriptive path (e.g. "aitrader-alpaca").
    "portd_name": "",
}


def _expand(p):
    return os.path.expanduser(p) if isinstance(p, str) and p else p


class Settings:
    """Loaded settings.toml merged over XDG defaults. Pass an explicit path for
    tests; production uses the fixed SETTINGS_PATH."""

    def __init__(self, path=None):
        self.path = path or SETTINGS_PATH
        self.data = {}
        if os.path.exists(self.path):
            with open(self.path, "rb") as f:
                self.data = tomllib.load(f)

    def _get(self, key):
        val = self.data.get(key)
        return val if val not in (None, "") else DEFAULTS.get(key)

    # ── base dirs ───────────────────────────────────────────────────────
    @property
    def config_dir(self):
        return CONFIG_DIR

    @property
    def data_dir(self):
        return _expand(self._get("data_dir"))

    @property
    def state_dir(self):
        return _expand(self._get("state_dir"))

    @property
    def log_dir(self):
        return os.path.join(self.state_dir, "logs")

    # ── derived file paths (explicit override else derived) ─────────────
    @property
    def secrets_path(self):
        return _expand(self.data.get("secrets_path")) or os.path.join(CONFIG_DIR, "secrets.toml")

    @property
    def journal_db(self):
        return _expand(self.data.get("journal_db")) or os.path.join(self.state_dir, "journal.db")

    @property
    def harness_state(self):
        return os.path.join(self.state_dir, "harness.json")

    @property
    def api_port_file(self):
        # The port the running API actually bound, written by aitrader-api at
        # startup. Out-of-process readers (the snapshot recorder timer) read
        # this instead of api_port so they reach the API regardless of portd
        # dynamic allocation (see portd_name / api.py).
        return os.path.join(self.state_dir, "api_port")

    @property
    def prompts_dir(self):
        return _expand(self.data.get("prompts_dir")) or os.path.join(self.data_dir, "prompts")

    @property
    def run_dir(self):
        # The ccloop run dir: holds CLAUDE.md, .claude/settings.json,
        # criteria.md, task.md. The `aitrader` launcher chdirs here. (MCP
        # servers live at user scope in ~/.claude.json, not in the run dir.)
        return _expand(self.data.get("run_dir")) or os.path.join(self.data_dir, "run")

    # ── scalars ─────────────────────────────────────────────────────────
    @property
    def wake_floor_seconds(self):
        return float(self._get("wake_floor_seconds"))

    @property
    def allow_live(self):
        return bool(self._get("allow_live"))

    @property
    def broker(self):
        # Execution backend: "ibkr" | "alpaca" | "myse".
        return self._get("broker")

    @property
    def data_broker(self):
        # None -> the execution broker serves market data too. "alpaca" -> route
        # data for data_broker_types to Alpaca regardless of the execution broker.
        return self.data.get("data_broker") or DEFAULTS.get("data_broker")

    @property
    def data_broker_types(self):
        # Asset types whose market data the data_broker serves (rest -> IBKR).
        val = self.data.get("data_broker_types")
        return list(val) if val else list(DEFAULTS.get("data_broker_types"))

    @property
    def alpaca_data_feed(self):
        # "iex" (real-time, IEX-only volume) or "sip" (full tape, paid plan).
        return (self.data.get("alpaca_data_feed")
                or DEFAULTS.get("alpaca_data_feed"))

    @property
    def criteria(self):
        # ccloop's first arg — the never-completing success criteria.
        return self.data.get("criteria") or ""

    @property
    def task(self):
        # ccloop's second arg — the initial task / wake instructions.
        return self.data.get("task") or ""

    @property
    def ccloop_cutoff(self):
        # ccloop --cutoff=N (relay cutoff in thousands of tokens).
        return int(self._get("ccloop_cutoff"))

    @property
    def api_host(self):
        return self._get("api_host")

    @property
    def api_port(self):
        return int(self._get("api_port"))

    @property
    def ui_port(self):
        return int(self._get("ui_port"))

    @property
    def portd_name(self):
        """portd registration name for this stack. An explicit settings.toml
        value wins; otherwise derive "<unix-user>-aitrader" so each Unix user's
        instance is unique on a shared host with zero config. portd is keyed by
        name, so two stacks sharing a name make the second's allocate() clobber
        the first's route — username is collision-proof (one running user per
        name). The API registers under "<portd_name>-api" (see api.py / bin)."""
        val = self.data.get("portd_name")
        return val if val else f"{getpass.getuser()}-aitrader"


@lru_cache(maxsize=1)
def settings():
    """The process-wide settings, loaded once from SETTINGS_PATH."""
    return Settings()
