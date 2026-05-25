"""
News Sentiment Lexicon — keyword dictionaries for deterministic news impact scoring.

Positive / negative / urgency keywords mapped to weights.
Symbol synonyms for cross-referencing news against trading symbols.
"""

from __future__ import annotations


POSITIVE_KEYWORDS: dict[str, float] = {
    "surge": 0.8,
    "rally": 0.8,
    "breakthrough": 0.9,
    "boom": 0.85,
    "bullish": 0.9,
    "soar": 0.85,
    "rocket": 0.85,
    "moon": 0.7,
    "adoption": 0.6,
    "partnership": 0.7,
    "upgrade": 0.6,
    "approval": 0.75,
    "launch": 0.6,
    "growth": 0.7,
    "profit": 0.75,
    "gain": 0.65,
    "rise": 0.6,
    "strong": 0.55,
    "recovery": 0.6,
    " ATH": 0.8,
    "all-time high": 0.85,
    "outperform": 0.7,
    "buyback": 0.65,
    "dividend": 0.5,
}

NEGATIVE_KEYWORDS: dict[str, float] = {
    "crash": 1.0,
    "hack": 0.9,
    "lawsuit": 0.7,
    "ban": 0.9,
    "bearish": 0.85,
    "collapse": 0.95,
    "plunge": 0.85,
    "dump": 0.8,
    "scam": 0.9,
    "fraud": 0.9,
    "investigation": 0.7,
    "penalty": 0.65,
    "fine": 0.6,
    "recession": 0.85,
    "inflation": 0.6,
    "default": 0.8,
    "liquidation": 0.85,
    "margin call": 0.8,
    "freeze": 0.7,
    "suspend": 0.75,
    "withdrawal": 0.55,
    "delay": 0.5,
    "miss": 0.5,
    "loss": 0.65,
    "fall": 0.55,
    "weak": 0.55,
    "sell-off": 0.8,
    "panic": 0.85,
    "fear": 0.7,
    "uncertainty": 0.6,
    "volatility": 0.5,
    "regulatory": 0.6,
    "sec": 0.65,
    "cbdc": 0.4,
    "war": 0.8,
    "conflict": 0.7,
    "attack": 0.75,
    "exploit": 0.8,
    "vulnerability": 0.65,
    "breach": 0.75,
}

URGENCY_KEYWORDS: list[str] = [
    "breaking",
    "urgent",
    "alert",
    "just in",
    "exclusive",
    "immediate",
    "flash",
    "emergency",
    "live update",
    "developing",
    "now",
    "critical",
]

SYMBOL_SYNONYMS: dict[str, list[str]] = {
    "BTCUSDT": ["bitcoin", "btc", "xbt"],
    "ETHUSDT": ["ethereum", "eth"],
    "SOLUSDT": ["solana", "sol"],
    "XRPUSDT": ["ripple", "xrp"],
    "ADAUSDT": ["cardano", "ada"],
    "DOGEUSDT": ["dogecoin", "doge"],
    "HYPEUSDT": ["hyperliquid", "hype"],
    "XAUUSDT": ["gold", "xau"],
    "XAGUSDT": ["silver", "xag"],
    "EURUSD": ["euro", "eur"],
    "GBPUSD": ["pound", "gbp", "sterling"],
    "USDJPY": ["yen", "jpy"],
    "USDCAD": ["loonie", "cad"],
}


def get_symbol_synonyms(symbol: str) -> list[str]:
    """Return keyword synonyms for a given trading symbol."""
    normalized = symbol.upper().replace(".P", "").replace("_", "").replace("-", "")
    return SYMBOL_SYNONYMS.get(normalized, [normalized[:4].lower()])
