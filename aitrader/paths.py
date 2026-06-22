"""Resolved filesystem paths — all derived from config (XDG defaults, overridable
in settings.toml). NO environment variables.

This is a thin convenience layer over aitrader.config so callers can keep doing
`from aitrader import paths; paths.STATE_DIR`. Values are resolved once at import
from the settings file; change settings.toml and restart to apply.
"""

__version__ = "0.2.1"

import os

from aitrader.config import settings, CONFIG_DIR as _CONFIG_DIR, SETTINGS_PATH as _SETTINGS_PATH

_s = settings()

CONFIG_DIR = _CONFIG_DIR
SETTINGS_PATH = _SETTINGS_PATH
DATA_DIR = _s.data_dir
STATE_DIR = _s.state_dir
LOG_DIR = _s.log_dir

SECRETS_PATH = _s.secrets_path
JOURNAL_DB = _s.journal_db

# Harness runtime state (last session id) for resume-on-restart.
HARNESS_STATE = _s.harness_state

# Installed prose (the agent's mandate) — on LOCAL disk, never the NFS source.
PROMPTS_DIR = _s.prompts_dir


def ensure_dirs():
    """Create the config/data/state dirs if missing. Idempotent."""
    for d in (CONFIG_DIR, DATA_DIR, STATE_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)
