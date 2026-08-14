"""Persistent idempotency store for live-candle processing."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class LastProcessedBar:
    symbol: str
    timeframe: str
    bar_ts: int
    updated_at: str


class LastProcessedBarStore:
    """Tracks the latest processed closed candle per symbol/timeframe."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._path = Path(persist_path or "data/last_processed_bars.json")
        self._items: dict[str, LastProcessedBar] = {}
        self._load()

    @staticmethod
    def _key(symbol: str, timeframe: str) -> str:
        return f"{symbol.upper().strip()}:{timeframe.strip()}"

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for item in raw.get("items", []):
                record = LastProcessedBar(
                    symbol=str(item["symbol"]).upper(),
                    timeframe=str(item["timeframe"]),
                    bar_ts=int(item["bar_ts"]),
                    updated_at=str(item.get("updated_at") or datetime.now(timezone.utc).isoformat()),
                )
                self._items[self._key(record.symbol, record.timeframe)] = record
        except Exception:
            self._items = {}

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "items": [asdict(item) for item in self._items.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, symbol: str, timeframe: str) -> int | None:
        record = self._items.get(self._key(symbol, timeframe))
        return record.bar_ts if record else None

    def should_process(self, symbol: str, timeframe: str, bar_ts: int | None) -> bool:
        if bar_ts is None:
            return False
        last = self.get(symbol, timeframe)
        return last is None or int(bar_ts) > last

    def mark_processed(self, symbol: str, timeframe: str, bar_ts: int) -> None:
        symbol = symbol.upper().strip()
        timeframe = timeframe.strip()
        self._items[self._key(symbol, timeframe)] = LastProcessedBar(
            symbol=symbol,
            timeframe=timeframe,
            bar_ts=int(bar_ts),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._persist()

    def dump(self) -> dict[str, dict]:
        return {key: asdict(value) for key, value in sorted(self._items.items())}

    def reset(self) -> None:
        self._items.clear()
        self._persist()


last_processed_bar_store = LastProcessedBarStore()
