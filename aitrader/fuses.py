"""Fuses — the ONLY deterministic 'no' in the system (BRIEF §7, CLAUDE.md §3).

A fuse protects the account/broker from a runaway loop the way a breaker
protects wiring. It NEVER expresses a view on a trade. ONE fuse only:

  1. Paper-only enforcement — the broker adapter refuses a non-paper account
     unless explicitly told allow_live=True.

The old HALT-file kill switch was removed: the operator stops the trader by
exiting the session (escape → exit) or `systemctl stop aitrader`, not via a
sentinel file the harness polls.

There are deliberately NO notional / buying-power ceilings: the agent owns ALL
sizing (locked decision §10). Do not add risk logic here.
"""

__version__ = "0.2.0"


# ── paper-only enforcement ─────────────────────────────────────────────────

class LiveAccountRefused(RuntimeError):
    """Raised when the broker adapter is pointed at a non-paper account and
    allow_live was not explicitly set."""


def is_paper_account_id(account_id):
    """IBKR paper account ids start with 'DU' (individual) or 'DF' (paper FA);
    live start with 'U'/'F'. Returns True only for a recognized paper id. Kept
    in sync with the broker connection's own assert_paper() check."""
    if not account_id:
        return False
    return str(account_id).upper().startswith(("DU", "DF"))


def assert_paper_account(account_id, allow_live=False):
    """Raise LiveAccountRefused unless the account is paper (or allow_live).

    Called by the broker connection immediately after login, BEFORE any order
    can be placed. This is the paper-only fuse."""
    if allow_live:
        return
    if not is_paper_account_id(account_id):
        raise LiveAccountRefused(
            f"Refusing to operate on non-paper account {account_id!r}. "
            f"aitrader is paper-only; pass allow_live=True to override (DON'T)."
        )
