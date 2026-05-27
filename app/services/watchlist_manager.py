"""
Watchlist Manager — persists and manages the list of symbols to trade.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass
class WatchlistItem:
    symbol: str
    timeframes: list[str] = field(default_factory=lambda: ["1m", "5m", "15m"])
    active: bool = True
    strategy_id: str | None = None
    min_confluence: float | None = None
    max_position_size_usdt: float | None = None
    added_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframes": self.timeframes,
            "active": self.active,
            "strategy_id": self.strategy_id,
            "min_confluence": self.min_confluence,
            "max_position_size_usdt": self.max_position_size_usdt,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> WatchlistItem:
        return cls(
            symbol=data["symbol"],
            timeframes=data.get("timeframes", ["1m", "5m", "15m"]),
            active=data.get("active", True),
            strategy_id=data.get("strategy_id"),
            min_confluence=data.get("min_confluence"),
            max_position_size_usdt=data.get("max_position_size_usdt"),
            added_at=data.get("added_at", datetime.now(timezone.utc).isoformat()),
        )


class WatchlistManager:
    """Manages a persistently stored watchlist."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._path = Path(persist_path or "data/watchlist.json")
        self._items: dict[str, WatchlistItem] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for item_data in data.get("items", []):
                item = WatchlistItem.from_dict(item_data)
                self._items[item.symbol.upper()] = item
        except Exception:
            pass

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "items": [item.to_dict() for item in self._items.values()],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add(self, item: WatchlistItem) -> None:
        self._items[item.symbol.upper()] = item
        self._persist()

    def remove(self, symbol: str) -> None:
        self._items.pop(symbol.upper(), None)
        self._persist()

    def update(self, symbol: str, **kwargs) -> WatchlistItem | None:
        sym = symbol.upper()
        if sym not in self._items:
            return None
        item = self._items[sym]
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self._persist()
        return item

    def get(self, symbol: str) -> WatchlistItem | None:
        return self._items.get(symbol.upper())

    def get_active(self) -> List[WatchlistItem]:
        return [item for item in self._items.values() if item.active]

    def list_all(self) -> List[WatchlistItem]:
        return list(self._items.values())

    def reset(self) -> None:
        self._items.clear()
        self._persist()


# Global singleton
watchlist_manager = WatchlistManager()
