"""
Strategy Engine — pluggable, configurable trading strategy framework.

Supports:
- BaseStrategy ABC for custom strategies
- CISDStrategy (wrapper around existing CISDScorer)
- PatternEnhancedStrategy (CISD + pattern recognition weighted)
- StrategyRegistry (singleton, persistence, runtime switching)
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from app.core.config import SIGNAL_MIN_CONFLUENCE_OVERRIDE
from app.services.cisd_scorer import CISDScorer, Candle as CISDCandle


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyScore:
    direction: str  # "LONG", "SHORT", "NEUTRAL"
    confluence_score: float  # 0-100
    confidence: float  # 0.0-1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyMetadata:
    strategy_id: str
    name: str
    description: str
    strategy_type: str
    timeframes: list[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Base strategy
# ---------------------------------------------------------------------------

class BaseStrategy(ABC):
    """Abstract base for all trading strategies."""

    def __init__(self, strategy_id: str, name: str, description: str = "") -> None:
        self.strategy_id = strategy_id
        self.name = name
        self.description = description

    @abstractmethod
    def score_bars(self, bars: Sequence) -> list[StrategyScore]:
        """
        Score every bar in the sequence.

        Args:
            bars: sequence of candle-like objects with .o, .h, .l, .c, .v, .ts

        Returns:
            List of StrategyScore, one per bar.
        """
        ...

    @abstractmethod
    def required_timeframes(self) -> list[str]:
        """Timeframes this strategy supports."""
        ...

    def get_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id=self.strategy_id,
            name=self.name,
            description=self.description,
            strategy_type="custom",
            timeframes=self.required_timeframes(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _bars_to_cisd_candles(self, bars: Sequence) -> list[CISDCandle]:
        return [
            CISDCandle(ts=b.ts, o=b.o, h=b.h, l=b.l, c=b.c, v=b.v)
            for b in bars
        ]


# ---------------------------------------------------------------------------
# CISD Strategy
# ---------------------------------------------------------------------------

class CISDStrategy(BaseStrategy):
    """
    Wrapper around the existing CISDScorer.
    Preserves backward-compatible behaviour.
    """

    def __init__(
        self,
        strategy_id: str = "default",
        name: str = "CISD Default",
        description: str = "GA-optimized CISD scoring with OB/FVG confluence.",
        scorer: CISDScorer | None = None,
    ) -> None:
        super().__init__(strategy_id, name, description)
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

    def score_bars(self, bars: Sequence) -> list[StrategyScore]:
        cisd_candles = self._bars_to_cisd_candles(bars)
        raw_scores = self.scorer.score_series(cisd_candles)
        return [
            StrategyScore(
                direction=score.get("direction_hint", "NEUTRAL"),
                confluence_score=score.get("confluence_score", 0.0),
                confidence=min(1.0, score.get("confluence_score", 0.0) / 100.0),
                metadata={
                    "raw_score": score.get("raw_score", 0.0),
                    "bull_conf": score.get("bull_conf", 0.0),
                    "bear_conf": score.get("bear_conf", 0.0),
                    "alignment_count": score.get("alignment_count", 0),
                },
            )
            for score in raw_scores
        ]

    def required_timeframes(self) -> list[str]:
        return ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

    def get_metadata(self) -> StrategyMetadata:
        meta = super().get_metadata()
        meta.strategy_type = "cisd"
        return meta


# ---------------------------------------------------------------------------
# Pattern Enhanced Strategy
# ---------------------------------------------------------------------------

class PatternEnhancedStrategy(BaseStrategy):
    """
    Combines CISD scoring with classical chart-pattern recognition.
    Weights are configurable per instance.
    """

    def __init__(
        self,
        cisd_weight: float = 0.6,
        pattern_weight: float = 0.4,
        scorer: CISDScorer | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("strategy_id", "pattern_enhanced")
        kwargs.setdefault("name", "Pattern Enhanced")
        kwargs.setdefault("description", "CISD + classical chart patterns (H&S, Double Top/Bottom, Flags, Triangles, Wedges).")
        super().__init__(**kwargs)
        if not (0.0 <= cisd_weight <= 1.0 and 0.0 <= pattern_weight <= 1.0):
            raise ValueError("Weights must be between 0 and 1")
        total = cisd_weight + pattern_weight
        self.cisd_weight = cisd_weight / total
        self.pattern_weight = pattern_weight / total
        self.cisd_strategy = CISDStrategy(
            strategy_id=f"{kwargs['strategy_id']}_cisd",
            scorer=scorer,
        )

    def score_bars(self, bars: Sequence) -> list[StrategyScore]:
        from app.services.pattern_recognition import scan_bars, aggregate_pattern_score

        cisd_scores = self.cisd_strategy.score_bars(bars)
        pattern_matches = scan_bars(bars)
        pattern_score, pattern_type, pattern_conf = aggregate_pattern_score(pattern_matches)

        combined: list[StrategyScore] = []
        for cisd in cisd_scores:
            # Blend CISD direction with pattern direction
            final_direction = cisd.direction
            if pattern_type and pattern_conf > 0.5:
                # If pattern strongly disagrees, consider pattern's direction for a subset
                pattern_dir = self._pattern_direction_hint(pattern_matches)
                if pattern_dir != "NEUTRAL" and cisd.direction != pattern_dir:
                    # Weighted direction: only boost if they agree
                    pass  # Keep CISD direction, but pattern affects score

            # Blend confluence scores
            blended_conf = (
                cisd.confluence_score * self.cisd_weight
                + pattern_score * self.pattern_weight
            )

            combined.append(
                StrategyScore(
                    direction=final_direction,
                    confluence_score=round(min(100.0, blended_conf), 2),
                    confidence=min(1.0, (cisd.confidence * self.cisd_weight + pattern_conf * self.pattern_weight)),
                    metadata={
                        **cisd.metadata,
                        "pattern_type": pattern_type,
                        "pattern_score": pattern_score,
                        "pattern_confidence": pattern_conf,
                        "cisd_confluence": cisd.confluence_score,
                        "weights": {"cisd": self.cisd_weight, "pattern": self.pattern_weight},
                    },
                )
            )
        return combined

    @staticmethod
    def _pattern_direction_hint(matches: list) -> str:
        if not matches:
            return "NEUTRAL"
        long_weight = sum(m.confidence for m in matches if m.direction == "LONG")
        short_weight = sum(m.confidence for m in matches if m.direction == "SHORT")
        if long_weight > short_weight * 1.2:
            return "LONG"
        if short_weight > long_weight * 1.2:
            return "SHORT"
        return "NEUTRAL"

    def required_timeframes(self) -> list[str]:
        return self.cisd_strategy.required_timeframes()

    def get_metadata(self) -> StrategyMetadata:
        meta = super().get_metadata()
        meta.strategy_type = "pattern_enhanced"
        return meta


class PineScriptPlaceholderStrategy(BaseStrategy):
    """Placeholder strategy representing an uploaded TradingView/Pionex Pine Script."""

    def __init__(self, strategy_id: str, name: str, description: str = "", code: str = "") -> None:
        super().__init__(strategy_id, name, description)
        self.code = code

    def score_bars(self, bars: Sequence) -> list[StrategyScore]:
        # Fallback to default CISD strategy scoring
        from app.services.strategy_engine import CISDStrategy
        fallback = CISDStrategy()
        return fallback.score_bars(bars)

    def required_timeframes(self) -> list[str]:
        return ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

    def get_metadata(self) -> StrategyMetadata:
        meta = super().get_metadata()
        meta.strategy_type = "pine_placeholder"
        return meta


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------

class StrategyRegistry:
    """
    Singleton registry that holds all available strategies and manages
    the active strategy. Persists custom strategy configs to disk.
    """

    _instance: StrategyRegistry | None = None

    def __new__(cls) -> StrategyRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._strategies: Dict[str, BaseStrategy] = {}
        self._active_strategy_id: str = "default"
        self._last_switch: datetime | None = None
        self._persist_path = Path("data/strategies.json")
        self._load_defaults()
        self._load_persisted()

    def _load_defaults(self) -> None:
        """Register built-in strategies."""
        self.register(CISDStrategy())
        self.register(PatternEnhancedStrategy())

        # Scan and register uploaded pine strategies
        try:
            base = Path(__file__).resolve().parents[2] / "app" / "scripts" / "generated_pines"
            if base.exists():
                for f in base.glob("*.pine"):
                    strategy_id = f.stem
                    name = f.stem.replace("_", " ")
                    code = f.read_text(encoding="utf-8")
                    self.register(
                        PineScriptPlaceholderStrategy(
                            strategy_id,
                            name,
                            f"Uploaded Pine Script: {name}",
                            code
                        )
                    )
        except Exception:
            pass

    def _load_persisted(self) -> None:
        """Load any custom strategy configs from disk."""
        if not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            active = data.get("active_strategy_id", "default")
            if active in self._strategies:
                self._active_strategy_id = active
                self._last_switch = datetime.fromisoformat(data.get("last_switch")) if data.get("last_switch") else None
        except Exception:
            # Fail open — keep defaults
            pass

    def _persist(self) -> None:
        """Save active strategy to disk."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "active_strategy_id": self._active_strategy_id,
                "last_switch": self._last_switch.isoformat() if self._last_switch else None,
                "available": list(self._strategies.keys()),
            }
            self._persist_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    # -- Public API --------------------------------------------------------

    def register(self, strategy: BaseStrategy) -> None:
        self._strategies[strategy.strategy_id] = strategy

    def unregister(self, strategy_id: str) -> None:
        if strategy_id == "default":
            raise ValueError("Cannot unregister the default strategy")
        self._strategies.pop(strategy_id, None)
        if self._active_strategy_id == strategy_id:
            self._active_strategy_id = "default"
            self._persist()

    def get(self, strategy_id: str) -> BaseStrategy:
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy '{strategy_id}' not found")
        return self._strategies[strategy_id]

    def get_active_strategy(self) -> BaseStrategy:
        return self._strategies.get(self._active_strategy_id, self._strategies["default"])

    def set_active_strategy(self, strategy_id: str) -> None:
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy '{strategy_id}' not found")
        self._active_strategy_id = strategy_id
        self._last_switch = datetime.now(timezone.utc)
        self._persist()

    def list_strategies(self) -> list[str]:
        return list(self._strategies.keys())

    def list_metadata(self) -> list[StrategyMetadata]:
        return [s.get_metadata() for s in self._strategies.values()]

    @property
    def active_strategy_id(self) -> str:
        return self._active_strategy_id

    @property
    def last_switch(self) -> datetime | None:
        return self._last_switch

    def reset(self) -> None:
        """Reset to factory defaults."""
        self._strategies.clear()
        self._active_strategy_id = "default"
        self._last_switch = None
        self._load_defaults()
        self._persist()


# Global singleton
strategy_registry = StrategyRegistry()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def get_active_strategy() -> BaseStrategy:
    return strategy_registry.get_active_strategy()
