"""
Shadow Queue — persists rejected signals and evaluates them after enough
bars have elapsed, so scouts still get learning feedback from trades that
never executed.

File: data/shadow_queue.jsonl
"""

from __future__ import annotations

import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List

from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview
from app.schemas.journal import DecisionEnum
from app.services.confidence_registry import confidence_registry
from app.services.signal_generator import BybitDataFeed


@dataclass
class ShadowEntry:
    signal_id: str
    timestamp: str
    symbol: str
    timeframe: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    scout_decisions: dict
    added_at: str
    evaluated: bool = False


class ShadowQueue:
    """Singleton file-backed queue for rejected-trade shadow evaluation."""

    _instance: ShadowQueue | None = None

    def __new__(cls) -> ShadowQueue:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, filepath: str = "data/shadow_queue.jsonl") -> None:
        if self._initialized:
            return
        self._initialized = True
        self._path = Path(filepath)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> List[ShadowEntry]:
        entries: List[ShadowEntry] = []
        if not self._path.exists():
            return entries
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    entries.append(ShadowEntry(**data))
        except Exception:
            pass
        return entries

    def _save(self, entries: List[ShadowEntry]) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(asdict(e)) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, payload: M8Payload, ai_review: SignalReview) -> None:
        """Add a rejected signal to the shadow queue."""
        if not ai_review.audit_trace:
            return
        scout_decisions = ai_review.audit_trace.get("scouts", {})
        if not scout_decisions:
            return
        entry = ShadowEntry(
            signal_id=payload.signal_id,
            timestamp=payload.timestamp,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe,
            direction=payload.direction,
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            scout_decisions=scout_decisions,
            added_at=datetime.now(timezone.utc).isoformat(),
        )
        entries = self._load()
        entries.append(entry)
        # Cap at 500 entries, purge oldest
        if len(entries) > 500:
            entries = entries[-500:]
        self._save(entries)

    async def process_pending(self) -> int:
        """Evaluate pending entries that are old enough to have future bars.
        Returns number of entries evaluated.
        """
        from app.services.shadow_paper_engine import ShadowPaperEngine

        entries = self._load()
        if not entries:
            return 0

        tf_ms_map = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        evaluated_count = 0
        updated_entries: List[ShadowEntry] = []

        for entry in entries:
            if entry.evaluated:
                updated_entries.append(entry)
                continue

            # Need at least 2 bars of elapsed time to have meaningful future data
            tf_ms = tf_ms_map.get(entry.timeframe, 60_000)
            signal_ts = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00")).timestamp() * 1000
            if now_ms < signal_ts + 2 * tf_ms:
                updated_entries.append(entry)
                continue

            try:
                bars = await asyncio.to_thread(
                    BybitDataFeed.fetch,
                    entry.symbol,
                    bars=200,
                    timeframe=entry.timeframe,
                )
                if not bars or len(bars) < 20:
                    updated_entries.append(entry)
                    continue

                entry_idx = min(range(len(bars)), key=lambda i: abs(bars[i].ts - signal_ts))
                if entry_idx >= len(bars) - 1:
                    updated_entries.append(entry)
                    continue

                engine = ShadowPaperEngine()
                # Reconstruct a minimal M8Payload-like object for simulation
                class _FakePayload:
                    def __init__(self, entry):
                        self.symbol = entry.symbol
                        self.direction = entry.direction
                        self.entry_price = entry.entry_price
                        self.stop_price = entry.stop_price
                        self.target_price = entry.target_price

                outcome = engine.simulate_trade(_FakePayload(entry), bars, entry_idx, max_holding_bars=20)

                for scout_name, scout_report in entry.scout_decisions.items():
                    scout_approved = isinstance(scout_report, dict) and scout_report.get("decision") == DecisionEnum.PROCEED_TO_SIMULATION.value
                    if not scout_approved and isinstance(scout_report, str):
                        scout_approved = "PROCEED" in scout_report.upper() or "APPROVE" in scout_report.upper()
                    was_correct = (scout_approved and outcome.win) or (not scout_approved and not outcome.win)
                    confidence_registry.mark_scout_outcome(
                        symbol=entry.symbol,
                        scout_names=[scout_name],
                        was_correct=was_correct,
                    )

                entry.evaluated = True
                evaluated_count += 1
            except Exception:
                pass

            updated_entries.append(entry)

        self._save(updated_entries)
        return evaluated_count

    def purge_old(self, max_age_days: int = 7) -> int:
        """Remove entries older than max_age_days. Returns number removed."""
        entries = self._load()
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
        fresh = []
        removed = 0
        for e in entries:
            try:
                added_ts = datetime.fromisoformat(e.added_at.replace("Z", "+00:00")).timestamp()
                if added_ts < cutoff:
                    removed += 1
                    continue
            except Exception:
                pass
            fresh.append(e)
        self._save(fresh)
        return removed


# Global singleton
shadow_queue = ShadowQueue()
