from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PositionState:
    symbol: str
    account_mode: str
    direction: str
    size_base: float
    avg_entry_price: float
    risk_amount: float


class PositionLedger:
    def __init__(self) -> None:
        self._positions: dict[tuple[str, str], PositionState] = {}

    def _key(self, symbol: str, account_mode: str) -> tuple[str, str]:
        return account_mode.upper(), symbol.upper()

    def get(self, symbol: str, account_mode: str) -> Optional[PositionState]:
        return self._positions.get(self._key(symbol, account_mode))

    def apply_entry(
        self,
        symbol: str,
        account_mode: str,
        direction: str,
        size_base: float,
        entry_price: float,
        risk_amount: float,
    ) -> PositionState:
        key = self._key(symbol, account_mode)
        direction = direction.upper()
        size_base = max(float(size_base), 0.0)
        risk_amount = max(float(risk_amount), 0.0)
        current = self._positions.get(key)

        if current is None:
            state = PositionState(
                symbol=symbol.upper(),
                account_mode=account_mode.upper(),
                direction=direction,
                size_base=size_base,
                avg_entry_price=float(entry_price),
                risk_amount=risk_amount,
            )
            self._positions[key] = state
            return state

        if current.direction == direction:
            total_size = current.size_base + size_base
            if total_size <= 0:
                total_size = 0.0
            if total_size > 0:
                current.avg_entry_price = (
                    (current.avg_entry_price * current.size_base) + (float(entry_price) * size_base)
                ) / total_size
            current.size_base = total_size
            current.risk_amount += risk_amount
            return current

        # Opposite-direction entry nets the existing exposure first.
        if size_base < current.size_base:
            remaining_ratio = (current.size_base - size_base) / current.size_base if current.size_base > 0 else 0.0
            current.size_base -= size_base
            current.risk_amount *= max(remaining_ratio, 0.0)
            return current

        # Full net-out or side flip.
        leftover = size_base - current.size_base
        if leftover <= 0:
            self._positions.pop(key, None)
            return PositionState(
                symbol=symbol.upper(),
                account_mode=account_mode.upper(),
                direction=direction,
                size_base=0.0,
                avg_entry_price=float(entry_price),
                risk_amount=0.0,
            )

        current.direction = direction
        current.size_base = leftover
        current.avg_entry_price = float(entry_price)
        current.risk_amount = risk_amount
        return current

    def apply_close(
        self,
        symbol: str,
        account_mode: str,
        close_size_base: Optional[float] = None,
    ) -> dict[str, float | str]:
        key = self._key(symbol, account_mode)
        current = self._positions.get(key)
        if current is None:
            return {
                "closed_size_base": 0.0,
                "remaining_size_base": 0.0,
                "entry_price": 0.0,
                "risk_amount": 0.0,
                "direction": "NONE",
            }

        requested = float(close_size_base) if close_size_base is not None else current.size_base
        requested = max(requested, 0.0)
        close_size = min(requested, current.size_base)
        if close_size <= 0:
            return {
                "closed_size_base": 0.0,
                "remaining_size_base": current.size_base,
                "entry_price": current.avg_entry_price,
                "risk_amount": current.risk_amount,
                "direction": current.direction,
            }

        risk_share = (close_size / current.size_base) * current.risk_amount if current.size_base > 0 else 0.0
        current.size_base -= close_size
        current.risk_amount = max(current.risk_amount - risk_share, 0.0)

        remaining = current.size_base
        entry_price = current.avg_entry_price
        direction = current.direction
        if current.size_base <= 0:
            self._positions.pop(key, None)

        return {
            "closed_size_base": close_size,
            "remaining_size_base": max(remaining, 0.0),
            "entry_price": entry_price,
            "risk_amount": risk_share,
            "direction": direction,
        }

    def restore_from_journal(self, journal_path: str) -> None:
        path = Path(journal_path)
        if not path.exists():
            return

        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                # ⚡ Bolt Optimization: Fast string match to skip JSON parsing for irrelevant lines
                if "ledger_delta" not in raw_line:
                    continue

                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                result = entry.get("result") or {}
                delta = result.get("ledger_delta")
                if not isinstance(delta, dict):
                    continue

                action = str(delta.get("action", "")).upper()
                symbol = str(delta.get("symbol", entry.get("symbol", ""))).upper()
                account_mode = str(delta.get("account_mode", "SPOT")).upper()
                if not symbol:
                    continue

                if action == "ENTRY":
                    self.apply_entry(
                        symbol=symbol,
                        account_mode=account_mode,
                        direction=str(delta.get("direction", entry.get("direction", "LONG"))).upper(),
                        size_base=float(delta.get("size_base", 0.0) or 0.0),
                        entry_price=float(delta.get("entry_price", entry.get("entry_price", 0.0)) or 0.0),
                        risk_amount=float(delta.get("risk_amount", 0.0) or 0.0),
                    )
                elif action == "CLOSE":
                    close_size = delta.get("closed_size_base")
                    self.apply_close(
                        symbol=symbol,
                        account_mode=account_mode,
                        close_size_base=float(close_size) if close_size is not None else None,
                    )
