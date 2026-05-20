import json
from typing import Dict, Any, List
from app.schemas.journal import TradeJournalEntry

class JournalLogger:
    """
    Logs TradeJournalEntry models to a local file/store for the MVP.
    In production, this would write to a DB (e.g. Postgres / timescale).
    """
    def __init__(self, filepath: str = "trade_journal.jsonl"):
        self.filepath = filepath

    def log(self, entry: TradeJournalEntry):
        with open(self.filepath, "a") as f:
            f.write(entry.model_dump_json() + "\n")

journal_logger_instance = JournalLogger()
