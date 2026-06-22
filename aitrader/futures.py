"""Futures contract specifications — multipliers, tick sizes, margins.

Single source of truth for all futures-related constants. No broker-specific
logic, no cognition — just data and pure utility functions (tick rounding,
multiplier/margin lookups). Used by the IBKR driver to build and round
futures orders.
"""

__version__ = "0.1.0"


# Contract specifications: exchange, multiplier, currency
SPECS = {
    # E-mini index futures (CME)
    "ES": {"exchange": "CME", "multiplier": 50, "currency": "USD"},
    "NQ": {"exchange": "CME", "multiplier": 20, "currency": "USD"},
    "YM": {"exchange": "CBOT", "multiplier": 5, "currency": "USD"},
    "RTY": {"exchange": "CME", "multiplier": 50, "currency": "USD"},
    # Micro index futures (CME)
    "MES": {"exchange": "CME", "multiplier": 5, "currency": "USD"},
    "MNQ": {"exchange": "CME", "multiplier": 2, "currency": "USD"},
    "MYM": {"exchange": "CBOT", "multiplier": 0.5, "currency": "USD"},
    "M2K": {"exchange": "CME", "multiplier": 5, "currency": "USD"},
    # Metals (COMEX)
    "GC": {"exchange": "COMEX", "multiplier": 100, "currency": "USD"},
    "SI": {"exchange": "COMEX", "multiplier": 5000, "currency": "USD"},
    "MGC": {"exchange": "COMEX", "multiplier": 10, "currency": "USD"},
    "SIL": {"exchange": "COMEX", "multiplier": 1000, "currency": "USD"},
    # Energy (NYMEX)
    "CL": {"exchange": "NYMEX", "multiplier": 1000, "currency": "USD"},
    "NG": {"exchange": "NYMEX", "multiplier": 10000, "currency": "USD"},
    "MCL": {"exchange": "NYMEX", "multiplier": 100, "currency": "USD"},
    # Copper (COMEX)
    "HG": {"exchange": "COMEX", "multiplier": 25000, "currency": "USD"},
    "MHG": {"exchange": "COMEX", "multiplier": 2500, "currency": "USD"},
    # Platinum group (NYMEX)
    "PA": {"exchange": "NYMEX", "multiplier": 100, "currency": "USD"},
    "PL": {"exchange": "NYMEX", "multiplier": 50, "currency": "USD"},
}


# Minimum tick sizes per contract
TICK_SIZES = {
    # E-mini index
    "ES": 0.25,
    "NQ": 0.25,
    "YM": 1.0,
    "RTY": 0.10,
    # Micro index
    "MES": 0.25,
    "MNQ": 0.25,
    "MYM": 1.0,
    "M2K": 0.10,
    # Metals
    "GC": 0.10,
    "SI": 0.005,
    "MGC": 0.10,
    "SIL": 0.005,
    # Energy
    "CL": 0.01,
    "NG": 0.001,
    "MCL": 0.01,
    # Copper
    "HG": 0.0005,
    "MHG": 0.001,
    # Platinum group
    "PA": 0.10,
    "PL": 0.10,
}


# Approximate initial margin per contract (USD)
MARGIN_ESTIMATES = {
    # Micro index
    "MES": 1500,
    "MNQ": 1800,
    "MYM": 900,
    "M2K": 750,
    # E-mini index
    "ES": 15000,
    "NQ": 18000,
    "YM": 9000,
    "RTY": 7500,
    # Metals
    "GC": 11000,
    "SI": 9500,
    "MGC": 1100,
    "SIL": 950,
    # Energy
    "CL": 6500,
    "NG": 2500,
    "MCL": 650,
    # Copper
    "HG": 4000,
    "MHG": 400,
    # Platinum group
    "PA": 3000,
    "PL": 2500,
}


def round_to_tick(price, symbol):
    """Round a price to the nearest valid tick size for a futures symbol.

    Falls back to round(price, 2) for unknown symbols.
    """
    tick = TICK_SIZES.get(symbol)
    if tick is None:
        return round(float(price), 2)
    price = float(price)
    return round(round(price / tick) * tick, 10)


def get_multiplier(symbol):
    """Return the contract multiplier for a futures symbol, or 1 for unknown."""
    spec = SPECS.get(symbol)
    if spec is None:
        return 1
    return spec["multiplier"]


def get_tick_size(symbol):
    """Return the tick size for a futures symbol, or 0.01 for unknown."""
    return TICK_SIZES.get(symbol, 0.01)


def get_margin_estimate(symbol):
    """Return the estimated initial margin for a futures symbol, or None."""
    return MARGIN_ESTIMATES.get(symbol)
