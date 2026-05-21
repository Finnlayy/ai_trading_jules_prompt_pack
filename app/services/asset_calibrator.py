"""
Asset Class Calibrator — maps symbols to calibrated parameters.

Calibration matrix:
  Crypto:   High volatility, high persistence thresholds, larger stops
  Forex:    Lower volatility, tighter stops, different alpha levels
  Metals:   Safe-haven logic, special crisis detection
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional


class AssetClassEnum(str, Enum):
    CRYPTO_BTC = "CRYPTO_BTC"
    CRYPTO_ETH = "CRYPTO_ETH"
    CRYPTO_ALTCOIN = "CRYPTO_ALTCOIN"
    FOREX_MAJOR = "FOREX_MAJOR"
    FOREX_MINOR = "FOREX_MINOR"
    FOREX_EXOTIC = "FOREX_EXOTIC"
    METAL_GOLD = "METAL_GOLD"
    METAL_SILVER = "METAL_SILVER"
    UNKNOWN = "UNKNOWN"


# Calibration defaults per asset class
CALIBRATION_MATRIX: Dict[str, Dict] = {
    AssetClassEnum.CRYPTO_BTC: {
        "hurst_trend": 0.62,
        "sl_atr_mul": 3.0,
        "tp_atr_mul": 6.0,
        "risk_per_trade": 1.0,
        "max_dd_pct": 10.0,
        "min_conf": 12,
        "alpha_level": 0.10,
        "safe_haven": False,
        "crisis_vol_threshold": 2.0,
    },
    AssetClassEnum.CRYPTO_ETH: {
        "hurst_trend": 0.60,
        "sl_atr_mul": 2.8,
        "tp_atr_mul": 5.6,
        "risk_per_trade": 1.5,
        "max_dd_pct": 12.0,
        "min_conf": 11,
        "alpha_level": 0.10,
        "safe_haven": False,
        "crisis_vol_threshold": 2.2,
    },
    AssetClassEnum.CRYPTO_ALTCOIN: {
        "hurst_trend": 0.58,
        "sl_atr_mul": 2.5,
        "tp_atr_mul": 5.0,
        "risk_per_trade": 2.0,
        "max_dd_pct": 15.0,
        "min_conf": 10,
        "alpha_level": 0.08,
        "safe_haven": False,
        "crisis_vol_threshold": 2.5,
    },
    AssetClassEnum.FOREX_MAJOR: {
        "hurst_trend": 0.55,
        "sl_atr_mul": 1.5,
        "tp_atr_mul": 3.0,
        "risk_per_trade": 0.5,
        "max_dd_pct": 5.0,
        "min_conf": 14,
        "alpha_level": 0.10,
        "safe_haven": False,
        "crisis_vol_threshold": 1.5,
    },
    AssetClassEnum.FOREX_MINOR: {
        "hurst_trend": 0.53,
        "sl_atr_mul": 1.8,
        "tp_atr_mul": 3.6,
        "risk_per_trade": 0.4,
        "max_dd_pct": 6.0,
        "min_conf": 13,
        "alpha_level": 0.08,
        "safe_haven": False,
        "crisis_vol_threshold": 1.8,
    },
    AssetClassEnum.FOREX_EXOTIC: {
        "hurst_trend": 0.50,
        "sl_atr_mul": 2.0,
        "tp_atr_mul": 4.0,
        "risk_per_trade": 0.3,
        "max_dd_pct": 4.0,
        "min_conf": 15,
        "alpha_level": 0.05,
        "safe_haven": False,
        "crisis_vol_threshold": 2.0,
    },
    AssetClassEnum.METAL_GOLD: {
        "hurst_trend": 0.58,
        "sl_atr_mul": 2.0,
        "tp_atr_mul": 4.0,
        "risk_per_trade": 0.5,
        "max_dd_pct": 6.0,
        "min_conf": 12,
        "alpha_level": 0.08,
        "safe_haven": True,
        "crisis_vol_threshold": 1.8,
    },
    AssetClassEnum.METAL_SILVER: {
        "hurst_trend": 0.56,
        "sl_atr_mul": 2.2,
        "tp_atr_mul": 4.4,
        "risk_per_trade": 0.35,
        "max_dd_pct": 8.0,
        "min_conf": 11,
        "alpha_level": 0.06,
        "safe_haven": True,
        "crisis_vol_threshold": 2.2,
    },
}


# Symbol → Asset Class mapping
SYMBOL_MAP: Dict[str, AssetClassEnum] = {
    # Crypto
    "BTCUSDT": AssetClassEnum.CRYPTO_BTC,
    "BTCUSD": AssetClassEnum.CRYPTO_BTC,
    "BTC": AssetClassEnum.CRYPTO_BTC,
    "ETHUSDT": AssetClassEnum.CRYPTO_ETH,
    "ETHUSD": AssetClassEnum.CRYPTO_ETH,
    "ETH": AssetClassEnum.CRYPTO_ETH,
    "HYPEUSDT": AssetClassEnum.CRYPTO_ALTCOIN,
    "HYPEUSD": AssetClassEnum.CRYPTO_ALTCOIN,
    "HYPE": AssetClassEnum.CRYPTO_ALTCOIN,
    "SOLUSDT": AssetClassEnum.CRYPTO_ALTCOIN,
    "SOLUSD": AssetClassEnum.CRYPTO_ALTCOIN,
    "SOL": AssetClassEnum.CRYPTO_ALTCOIN,
    "AVAXUSDT": AssetClassEnum.CRYPTO_ALTCOIN,
    "AVAXUSD": AssetClassEnum.CRYPTO_ALTCOIN,
    "AVAX": AssetClassEnum.CRYPTO_ALTCOIN,
    "XRPUSDT": AssetClassEnum.CRYPTO_ALTCOIN,
    "XRPUSD": AssetClassEnum.CRYPTO_ALTCOIN,
    "XRP": AssetClassEnum.CRYPTO_ALTCOIN,
    # Forex Majors
    "EURUSD": AssetClassEnum.FOREX_MAJOR,
    "GBPUSD": AssetClassEnum.FOREX_MAJOR,
    "USDJPY": AssetClassEnum.FOREX_MAJOR,
    "USDCHF": AssetClassEnum.FOREX_MAJOR,
    "AUDUSD": AssetClassEnum.FOREX_MAJOR,
    "USDCAD": AssetClassEnum.FOREX_MAJOR,
    "NZDUSD": AssetClassEnum.FOREX_MAJOR,
    # Forex Minors
    "EURGBP": AssetClassEnum.FOREX_MINOR,
    "EURJPY": AssetClassEnum.FOREX_MINOR,
    "GBPJPY": AssetClassEnum.FOREX_MINOR,
    # Metals
    "XAUUSD": AssetClassEnum.METAL_GOLD,
    "XAUUSDT": AssetClassEnum.METAL_GOLD,
    "GOLD": AssetClassEnum.METAL_GOLD,
    "XAGUSD": AssetClassEnum.METAL_SILVER,
    "XAGUSDT": AssetClassEnum.METAL_SILVER,
    "SILVER": AssetClassEnum.METAL_SILVER,
}


def get_asset_class(symbol: str) -> AssetClassEnum:
    """Map symbol to asset class."""
    symbol_upper = symbol.upper().replace(".P", "")
    return SYMBOL_MAP.get(symbol_upper, AssetClassEnum.UNKNOWN)


def get_calibration(symbol: str) -> Dict:
    """Get calibrated parameters for a symbol."""
    asset_class = get_asset_class(symbol)
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "calibration": CALIBRATION_MATRIX.get(asset_class, CALIBRATION_MATRIX[AssetClassEnum.CRYPTO_ALTCOIN]),
    }


def apply_calibration_to_payload(payload_dict: Dict, symbol: str) -> Dict:
    """
    Merge calibrated defaults into payload dict.
    Only overwrites if payload value is missing or at default.
    """
    cal = get_calibration(symbol)
    params = cal["calibration"]

    # Map calibration params to payload fields
    mapping = {
        "sl_atr_mul": "stop_atr_multiplier",
        "tp_atr_mul": "target_atr_multiplier",
        "risk_per_trade": "risk_percent",
        "max_dd_pct": "max_drawdown_pct",
        "min_conf": "min_confidence",
    }

    result = dict(payload_dict)
    for cal_key, payload_key in mapping.items():
        if payload_key not in result or result[payload_key] is None:
            result[payload_key] = params.get(cal_key)

    result["_asset_class"] = cal["asset_class"]
    result["_safe_haven"] = params.get("safe_haven", False)
    result["_crisis_vol_threshold"] = params.get("crisis_vol_threshold", 2.0)

    return result


# Global instance functions
asset_calibrator = {
    "get_asset_class": get_asset_class,
    "get_calibration": get_calibration,
    "apply_calibration": apply_calibration_to_payload,
}
