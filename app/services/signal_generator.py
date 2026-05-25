"""
Signal Generator — converts historical OHLCV into M8Payloads via CISD scoring.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict

import requests

from app.core.config import SIGNAL_MIN_CONFLUENCE_OVERRIDE
from app.schemas.m8_payload import M8Payload
from app.services.cisd_scorer import CISDScorer, Candle as CISDScorerCandle
from app.services.asset_calibrator import get_calibration


@dataclass(frozen=True)
class OHLCV:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float


class BybitDataFeed:
    """Fetches 1m candles from Bybit linear API."""

    BASE = "https://api.bybit.com"

    _TF_MAP = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "4h": "240",
        "1d": "D",
    }

    @staticmethod
    def _tf_to_ms(timeframe: str) -> int:
        if timeframe.endswith("m"):
            return int(timeframe[:-1]) * 60_000
        if timeframe.endswith("h"):
            return int(timeframe[:-1]) * 3_600_000
        if timeframe == "4h":
            return 14_400_000
        if timeframe == "1d":
            return 86_400_000
        return 60_000

    @classmethod
    def fetch(cls, symbol: str, bars: int = 1000, timeframe: str = "1m") -> List[OHLCV]:
        interval = cls._TF_MAP.get(timeframe, "1")
        all_bars: List[OHLCV] = []
        end_ms = int(time.time() * 1000)
        tf_ms = cls._tf_to_ms(timeframe)

        while len(all_bars) < bars:
            remaining = bars - len(all_bars)
            limit = 1000 if remaining > 1000 else remaining
            resp = requests.get(
                f"{BybitDataFeed.BASE}/v5/market/kline",
                params={
                    "category": "linear",
                    "symbol": symbol,
                    "interval": interval,
                    "end": end_ms,
                    "limit": limit,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {}).get("list", [])
            if not result:
                break

            chunk = [
                OHLCV(
                    ts=int(row[0]),
                    o=float(row[1]),
                    h=float(row[2]),
                    l=float(row[3]),
                    c=float(row[4]),
                    v=float(row[5]),
                )
                for row in result
            ]
            chunk.sort(key=lambda x: x.ts)
            all_bars = chunk + all_bars
            end_ms = chunk[0].ts - tf_ms
            time.sleep(0.08)
            if len(chunk) < limit:
                break

        # Deduplicate
        seen = {}
        for b in all_bars:
            seen[b.ts] = b
        ordered = [seen[k] for k in sorted(seen)]
        return ordered[-bars:] if len(ordered) > bars else ordered


class SignalGenerator:
    """
    Generates M8Payloads from historical OHLCV data using CISD scoring.
    Uses GA-optimized weights for HYPEUSDT to produce realistic confluence scores.
    """

    def __init__(self, scorer: Optional[CISDScorer] = None):
        # Use GA-optimized weights from cross-algo results
        self.scorer = scorer or CISDScorer(
            min_alignment=3,
            ob_atr_mul=0.798,
            ob_pivot=6,
            w_align_full=1,
            w_align_part=1,
            w_cisd=2,
            w_ob_touch=3,
            w_fvg_touch=2,
            w_vol_score=2,
            w_body_score=1,
            body_atr_mul=0.375,
            vol_mult=1.103,
            vol_period=20,
        )
        self.feed = BybitDataFeed()
        self.last_generation_summary: Dict = {}
        self.last_raw_bars: List[OHLCV] = []

    def _ohlcv_to_cisd_candles(self, bars: List[OHLCV]) -> List[CISDScorerCandle]:
        return [CISDScorerCandle(ts=b.ts, o=b.o, h=b.h, l=b.l, c=b.c, v=b.v) for b in bars]

    def generate_payloads(
        self,
        symbol: str = "HYPEUSDT",
        timeframe: str = "1m",
        bars: int = 200,
        min_confluence: Optional[float] = None,
    ) -> List[M8Payload]:
        """
        Fetch historical data, score every bar, and emit M8Payloads
        for bars that exceed the confidence threshold.
        """
        # Get asset calibration for thresholds
        cal = get_calibration(symbol)
        cal_params = cal.get("calibration", {})
        min_conf = (
            min_confluence
            if min_confluence is not None
            else SIGNAL_MIN_CONFLUENCE_OVERRIDE
            if SIGNAL_MIN_CONFLUENCE_OVERRIDE is not None
            else cal_params.get("min_conf", 11)
        )
        sl_atr_mul = cal_params.get("sl_atr_mul", 1.4)
        tp_atr_mul = cal_params.get("tp_atr_mul", 2.8)

        raw_bars = self.feed.fetch(symbol, bars, timeframe)
        self.last_raw_bars = raw_bars
        if len(raw_bars) < 50:
            self.last_generation_summary = {
                "symbol": symbol,
                "bars_requested": bars,
                "bars_loaded": len(raw_bars),
                "min_confluence": min_conf,
                "scores_count": 0,
                "max_confluence_score": None,
                "directional_scores": 0,
                "payloads_generated": 0,
                "message": "Insufficient bars for CISD scoring",
            }
            return []

        cisd_candles = self._ohlcv_to_cisd_candles(raw_bars)
        scores = self.scorer.score_series(cisd_candles)
        max_score = max((float(score["confluence_score"]) for score in scores), default=0.0)
        directional_scores = sum(1 for score in scores if score["direction_hint"] != "NEUTRAL")

        payloads = []
        for i, (bar, score) in enumerate(zip(raw_bars, scores)):
            if score["confluence_score"] < min_conf:
                continue
            if score["direction_hint"] == "NEUTRAL":
                continue

            # Compute ATR-based SL/TP for this bar
            # Use a simple windowed ATR for the SL/TP calculation
            if i < 14:
                continue
            atr_window = cisd_candles[i - 13 : i + 1]
            atr_val = self._simple_atr(atr_window)

            direction = score["direction_hint"]
            entry = bar.c
            if direction == "LONG":
                sl = entry - atr_val * sl_atr_mul
                tp = entry + atr_val * tp_atr_mul
            else:
                sl = entry + atr_val * sl_atr_mul
                tp = entry - atr_val * tp_atr_mul

            # Crisis score: ATR% scaled to 0-100 crisis scale
            # Normal ATR% for HYPE ~1-3%, crisis starts at >3%
            atr_pct = (atr_val / entry) * 100.0
            crisis = min(100.0, max(0.0, (atr_pct - 1.0) * 15.0))  # 1% ATR → 0 crisis, 3% ATR → 30 crisis, 7% ATR → 90 crisis
            spread = (bar.h - bar.l) / entry * 10000.0

            payload = M8Payload(
                signal_id=f"gen-{symbol}-{bar.ts}",
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                timestamp=datetime.fromtimestamp(bar.ts / 1000.0, tz=timezone.utc).isoformat(),
                entry_price=round(entry, 4),
                stop_price=round(sl, 4),
                target_price=round(tp, 4),
                confluence_score=round(score["confluence_score"], 2),
                relative_volume=round(bar.v / self._avg_volume(raw_bars[max(0, i - 20):i + 1]), 2) if i > 0 else 1.0,
                crisis_score=round(crisis, 2),
                mc_dispersion=round(score["alignment_count"] / 3.0 * 5.0, 2),  # proxy dispersion from alignment
                spread=round(spread, 2),
            )
            payloads.append(payload)

        self.last_generation_summary = {
            "symbol": symbol,
            "asset_class": str(cal.get("asset_class")),
            "bars_requested": bars,
            "bars_loaded": len(raw_bars),
            "min_confluence": min_conf,
            "scores_count": len(scores),
            "max_confluence_score": round(max_score, 2),
            "directional_scores": directional_scores,
            "payloads_generated": len(payloads),
        }
        return payloads

    def _simple_atr(self, candles: List[CISDScorerCandle]) -> float:
        if len(candles) < 2:
            return candles[0].h - candles[0].l if candles else 1.0
        trs = []
        prev = candles[0].c
        for c in candles:
            trs.append(max(c.h - c.l, abs(c.h - prev), abs(c.l - prev)))
            prev = c.c
        return sum(trs) / len(trs)

    def _avg_volume(self, bars: List[OHLCV]) -> float:
        if not bars:
            return 1.0
        return sum(b.v for b in bars) / len(bars)


# Global instance
signal_generator_instance = SignalGenerator()
