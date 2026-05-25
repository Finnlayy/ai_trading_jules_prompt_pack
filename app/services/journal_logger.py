import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from app.schemas.journal import TradeJournalEntry


class JournalLogger:
    """
    Logs TradeJournalEntry models to a local file/store for the MVP.
    In production, this would write to a DB (e.g. Postgres / timescale).

    Features:
    - Size-based rotation (default 10 MB)
    - Timestamped archive names
    """

    def __init__(
        self,
        filepath: str = "trade_journal.jsonl",
        max_size_bytes: int = 10 * 1024 * 1024,  # 10 MB
        max_backups: int = 5,
    ) -> None:
        self.filepath = filepath
        self.max_size_bytes = max_size_bytes
        self.max_backups = max_backups

    def _should_rotate(self) -> bool:
        try:
            return os.path.getsize(self.filepath) >= self.max_size_bytes
        except OSError:
            return False

    def _rotate(self) -> None:
        if not os.path.exists(self.filepath):
            return

        # Rotate existing backups: .1 -> .2, .2 -> .3, etc.
        for i in range(self.max_backups - 1, 0, -1):
            src = f"{self.filepath}.{i}"
            dst = f"{self.filepath}.{i + 1}"
            if os.path.exists(src):
                if i == self.max_backups - 1:
                    os.remove(src)
                else:
                    os.rename(src, dst)

        # Move current file to .1
        archive = f"{self.filepath}.1"
        os.rename(self.filepath, archive)

    def log(self, entry: TradeJournalEntry):
        if self._should_rotate():
            self._rotate()

        with open(self.filepath, "a") as f:
            f.write(entry.model_dump_json() + "\n")

        # Also persist to SQLite
        try:
            from app.db import SessionLocal
            from app.db.models import Trade
            db = SessionLocal()
            db.add(Trade(
                trade_id=entry.trade_id,
                signal_id=entry.payload.get("signal_id") if hasattr(entry, "payload") else None,
                symbol=entry.symbol,
                direction=entry.direction,
                strategy_id=entry.payload.get("strategy_id") if hasattr(entry, "payload") else None,
                timeframe=entry.payload.get("timeframe") if hasattr(entry, "payload") else None,
                entry_price=entry.entry_price,
                stop_price=entry.payload.get("stop_price") if hasattr(entry, "payload") else None,
                target_price=entry.payload.get("target_price") if hasattr(entry, "payload") else None,
                size=entry.result.get("size") if hasattr(entry, "result") else None,
                confluence_score=entry.payload.get("confluence_score") if hasattr(entry, "payload") else None,
                crisis_score=entry.payload.get("crisis_score") if hasattr(entry, "payload") else None,
                final_decision=entry.final_decision,
                reject_reason=entry.result.get("reject_reason") if hasattr(entry, "result") else None,
                pnl=entry.result.get("pnl") if hasattr(entry, "result") else None,
                fees=entry.result.get("fees") if hasattr(entry, "result") else 0.0,
            ))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_entries(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Read last N entries from the journal (and rotated files if needed)."""
        entries: List[Dict[str, Any]] = []
        # Read archives first (oldest), then current file (newest)
        files = []
        for i in range(self.max_backups, 0, -1):
            archive = f"{self.filepath}.{i}"
            if os.path.exists(archive):
                files.append(archive)
        files.append(self.filepath)

        for filepath in files:
            try:
                with open(filepath, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

        return entries[-limit:]


journal_logger_instance = JournalLogger()
