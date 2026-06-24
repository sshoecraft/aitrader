"""Time helpers — pure time facts, no decisions.

Invariant (CLAUDE.md §6): all times UTC internally, display ET. Real tz
library (zoneinfo), never hardcoded offsets — half-days and DST will bite.
"""

__version__ = "0.2.0"

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


def utcnow():
    """Current time as a tz-aware UTC datetime."""
    return datetime.now(UTC)


def utcnow_iso():
    """Current UTC time as an ISO-8601 string (seconds resolution, 'Z'-free +00:00)."""
    return utcnow().isoformat()


def to_et(dt):
    """Convert a tz-aware datetime to America/New_York."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(ET)


def et_display(dt):
    """Human ET string, e.g. '2026-06-15 09:30:00 EDT'. The NYSE session clock."""
    return to_et(dt).strftime("%Y-%m-%d %H:%M:%S %Z")


def local_display(dt):
    """Human string in the HOST's local timezone, e.g. '2026-06-15 08:30:00 CDT'.
    Uses the system local zone (astimezone with no argument) so journal prose matches
    the operator's wall clock instead of a hardcoded market timezone — the venue's own
    session clock is a separate concern (et_display / the broker calendar)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def parse_iso(s):
    """Parse an ISO-8601 string to a tz-aware datetime (assume UTC if naive)."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def epoch_to_iso(epoch):
    """Unix epoch seconds → ISO-8601 UTC string, the same +00:00 form as utcnow_iso
    so backfilled rows sort lexically alongside live snapshots (equity_read orders
    by ts as text — see the 0.15.3 ordering fix)."""
    return datetime.fromtimestamp(epoch, UTC).isoformat()
