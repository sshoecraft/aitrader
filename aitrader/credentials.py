"""Credential loading for aitrader.

Loads connection config from ~/.config/aitrader/secrets.toml (TOML).
Pure I/O — no decisions.

Expected secrets.toml keys (IBKR paper):
    ibkr_host       = "127.0.0.1"   # IB Gateway / TWS host
    ibkr_port       = 4002          # 4002 = paper gateway, 4001 = live gateway
                                    # 7497 = paper TWS,     7496 = live TWS
    ibkr_client_id  = 1
"""

__version__ = "0.3.0"

import os
import sys
import tomllib

from aitrader.config import settings


def load_secrets(path=None):
    """Load the secrets TOML. Raises FileNotFoundError if absent.

    Path comes from config (settings.toml `secrets_path`, default
    ~/.config/aitrader/secrets.toml). No environment variables.
    """
    if path is None:
        path = settings().secrets_path

    if os.path.exists(path):
        mode = oct(os.stat(path).st_mode)[-3:]
        if mode != "600":
            print(f"WARNING: {path} has permissions {mode}, should be 600", file=sys.stderr)

    with open(path, "rb") as f:
        return tomllib.load(f)


def load_ibkr_credentials(path=None):
    """Return {host, port, client_id} for the IBKR connection.

    Raises ValueError if ibkr_port is missing — there is no default port,
    because picking one silently could connect to the wrong (live) gateway.
    """
    secrets = load_secrets(path)
    host = secrets.get("ibkr_host", "127.0.0.1")
    port = secrets.get("ibkr_port")
    client_id = secrets.get("ibkr_client_id", 1)

    if port is None:
        raise ValueError(
            "ibkr_port not found in secrets.toml. Set ibkr_port "
            "(4002=paper gateway, 7497=paper TWS, 4001/7496=LIVE)."
        )

    return {"host": host, "port": int(port), "client_id": int(client_id)}


def load_alpaca_credentials(path=None):
    """Return (api_key, secret_key) for the Alpaca market-DATA feed.

    Alpaca is the optional data broker (see settings.toml `data_broker`). It
    supplies bars/snapshots for stocks + crypto — NOT execution (that's IBKR).
    Raises ValueError if the keys are absent so a misconfigured data_broker
    fails loudly instead of silently falling back to IBKR's thin paper feed.
    """
    secrets = load_secrets(path)
    api_key = secrets.get("alpaca_api_key")
    secret_key = secrets.get("alpaca_secret_key")

    if not api_key or not secret_key:
        raise ValueError(
            "Alpaca credentials not found in secrets.toml. Set alpaca_api_key "
            "and alpaca_secret_key (or unset data_broker to use IBKR data)."
        )
    return api_key, secret_key


def load_myse_credentials(path=None):
    """Return {host, api_key} for the MYSE execution backend (broker="myse").

    host defaults to http://localhost:7777. Raises ValueError if myse_api_key
    is absent so a misconfigured broker=myse fails loudly.
    """
    secrets = load_secrets(path)
    host = secrets.get("myse_host", "http://localhost:7777")
    api_key = secrets.get("myse_api_key")
    if not api_key:
        raise ValueError(
            "MYSE credentials not found in secrets.toml. Set myse_api_key "
            "(and optionally myse_host)."
        )
    return {"host": str(host), "api_key": str(api_key)}
