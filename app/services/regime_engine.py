"""
Regime Engine — classifies market state using statistical test battery.

Regime taxonomy:
  RW1 (Strong Efficient)  : LB + VR pass, no autocorr, no predictability
  RW2 (Weak Efficient)    : LB passes, some VR predictability
  RW3 (Heteroskedastic)   : ARCH detected, volatility clustering
  Inefficient             : LB rejects, strong autocorrelation/memory
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Sequence

from app.services.statistical_battery import run_battery


class RegimeEnum(str, Enum):
    RW1 = "RW1_EFFICIENT"
    RW2 = "RW2_WEAK_EFFICIENT"
    RW3 = "RW3_HETEROSKEDASTIC"
    INEFFICIENT_TREND = "INEFFICIENT_TREND"
    INEFFICIENT_MR = "INEFFICIENT_MEAN_REVERSION"
    UNKNOWN = "UNKNOWN"


class SignalModeEnum(str, Enum):
    NO_SIGNALS = "NO_SIGNALS"
    TREND_ONLY = "TREND_ONLY"
    MR_ONLY = "MR_ONLY"
    FULL_SUITE = "FULL_SUITE"
    VOL_BREAKOUT = "VOL_BREAKOUT"


class RegimeEngine:
    """
    Detects market regime from price series.
    Outputs regime + recommended signal mode + confidence.
    """

    def __init__(self, allow_rw1_signals: bool = False):
        self.allow_rw1_signals = allow_rw1_signals

    def classify(self, prices: Sequence[float]) -> Dict:
        """
        Run full battery and classify regime.
        Returns dict with regime, signal_mode, confidence, raw_tests.
        """
        battery = run_battery(prices)
        if "error" in battery:
            return {
                "regime": RegimeEnum.UNKNOWN,
                "signal_mode": SignalModeEnum.FULL_SUITE,
                "confidence": 0.0,
                "battery": battery,
            }

        summary = battery["summary"]
        hurst = battery["hurst"]["value"]
        uncorrelated = summary["uncorrelated"]
        predictable = summary["predictable"]
        vol_clustering = summary["vol_clustering"]
        random_seq = summary["random_sequence"]

        # Regime classification logic
        regime = RegimeEnum.UNKNOWN
        signal_mode = SignalModeEnum.FULL_SUITE
        confidence = 0.5

        if uncorrelated and not predictable and random_seq and not vol_clustering:
            regime = RegimeEnum.RW1
            signal_mode = SignalModeEnum.NO_SIGNALS if not self.allow_rw1_signals else SignalModeEnum.MR_ONLY
            confidence = 0.9

        elif uncorrelated and not predictable and random_seq and vol_clustering:
            regime = RegimeEnum.RW3
            signal_mode = SignalModeEnum.VOL_BREAKOUT
            confidence = 0.8

        elif not uncorrelated or predictable:
            # Inefficient market — determine trend vs mean-reversion
            if hurst > 0.55:
                regime = RegimeEnum.INEFFICIENT_TREND
                signal_mode = SignalModeEnum.TREND_ONLY
                confidence = min(0.95, 0.6 + abs(hurst - 0.5))
            elif hurst < 0.45:
                regime = RegimeEnum.INEFFICIENT_MR
                signal_mode = SignalModeEnum.MR_ONLY
                confidence = min(0.95, 0.6 + abs(hurst - 0.5))
            else:
                regime = RegimeEnum.RW2
                signal_mode = SignalModeEnum.FULL_SUITE
                confidence = 0.7

        elif uncorrelated and predictable:
            regime = RegimeEnum.RW2
            signal_mode = SignalModeEnum.FULL_SUITE
            confidence = 0.65

        else:
            regime = RegimeEnum.RW2
            signal_mode = SignalModeEnum.FULL_SUITE
            confidence = 0.5

        return {
            "regime": regime,
            "signal_mode": signal_mode,
            "confidence": round(confidence, 3),
            "hurst": hurst,
            "battery": battery,
        }

    def should_trade(self, prices: Sequence[float]) -> Dict:
        """
        Quick check: should we trade given current regime?
        Returns {trade_allowed, regime, reason}.
        """
        result = self.classify(prices)
        regime = result["regime"]
        signal_mode = result["signal_mode"]

        trade_allowed = signal_mode != SignalModeEnum.NO_SIGNALS

        reasons = {
            RegimeEnum.RW1: "Market is strongly efficient — no edge available",
            RegimeEnum.RW2: "Weak efficiency — full signal suite permitted",
            RegimeEnum.RW3: "Volatility clustering — breakout signals only",
            RegimeEnum.INEFFICIENT_TREND: "Persistent memory detected — trend following",
            RegimeEnum.INEFFICIENT_MR: "Anti-persistent memory — mean reversion",
            RegimeEnum.UNKNOWN: "Insufficient data for classification",
        }

        return {
            "trade_allowed": trade_allowed,
            "regime": regime,
            "signal_mode": signal_mode,
            "confidence": result["confidence"],
            "reason": reasons.get(regime, "Unknown regime"),
        }


# Global instance
regime_engine_instance = RegimeEngine(allow_rw1_signals=False)
