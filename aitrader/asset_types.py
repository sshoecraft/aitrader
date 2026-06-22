"""Asset type definitions for the trader package."""

__version__ = "0.10.1"

from enum import Enum


class AssetType(Enum):
    """Supported asset types for trading."""
    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"
    OPTIONS = "options"


# ISO 4217 currency codes for major traded currencies.
# Used to disambiguate forex pairs (EUR/USD) from crypto pairs (BTC/USD)
# when only the symbol string is available (no broker asset_class).
FOREX_BASES = frozenset({
    "EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY",
    "SEK", "NOK", "DKK", "HKD", "SGD", "MXN", "ZAR", "TRY",
    "PLN", "CZK", "HUF", "ILS", "CNH",
})


def normalize_crypto_symbol(symbol):
    """Normalize crypto symbols to canonical slash format.

    BTCUSD → BTC/USD, DOGEUSD → DOGE/USD, PAXGUSD → PAXG/USD.
    Forex symbols (EURUSD), stock tickers, and already-slashed symbols
    are returned unchanged.
    """
    if "/" in symbol:
        return symbol
    s = symbol.upper()
    if not (s.endswith("USD") and len(s) >= 6):
        return symbol
    base = s[:-3]
    if base in FOREX_BASES:
        return symbol  # forex, not crypto
    return base + "/USD"


def classify_symbol(symbol, asset_class=None):
    """Return the AssetType for a symbol.

    Uses asset_class from broker data when available (both Alpaca and IBKR
    provide this). Falls back to symbol heuristics.

    IBKR secType values: STK, CRYPTO, CASH (forex), FUT (futures).
    Alpaca asset_class values: us_equity, crypto.
    """
    # Broker-provided asset_class takes priority for definitive types
    if asset_class in ("crypto",):
        return AssetType.CRYPTO
    if asset_class in ("forex", "CASH"):
        return AssetType.FOREX
    if asset_class in ("futures", "FUT"):
        return AssetType.FUTURES
    if asset_class in ("options", "OPT"):
        return AssetType.OPTIONS

    # For us_equity: trust it unless symbol looks like a pair (X/Y)
    # Alpaca may return us_equity for some crypto pairs in certain contexts
    if asset_class in ("us_equity",):
        if "/" in symbol:
            parts = symbol.split("/")
            if len(parts) == 2 and parts[0] in FOREX_BASES:
                return AssetType.FOREX
            return AssetType.CRYPTO
        return AssetType.STOCK

    # Fallback: symbol-based heuristics
    if "/" in symbol:
        parts = symbol.split("/")
        if len(parts) == 2 and parts[0] in FOREX_BASES:
            return AssetType.FOREX
        return AssetType.CRYPTO

    return AssetType.STOCK
