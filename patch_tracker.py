with open("app/services/live_fill_tracker.py", "r") as f:
    content = f.read()

# Ensure we're not replacing multiple times
if "_db_exit_queue" not in content:
    init_old = """        self._positions: Dict[str, OpenPosition] = {}
        self._intents: Dict[str, PositionIntent] = {}
        self._history: List[dict] = []
        self._persist_path = Path("data/positions.json")
        self._load()"""

    init_new = """        self._positions: Dict[str, OpenPosition] = {}
        self._intents: Dict[str, PositionIntent] = {}
        self._history: List[dict] = []
        self._db_exit_queue: List[tuple] = []
        self._persist_path = Path("data/positions.json")
        self._load()"""

    content = content.replace(init_old, init_new)


    record_exit_old = """        # Also update SQLite
        try:
            from app.db import SessionLocal
            from app.db.models import Position
            db = SessionLocal()
            db_pos = db.query(Position).filter(Position.trade_id == trade_id).first()
            if db_pos:
                db_pos.is_open = False
                db_pos.current_price = exit_price
                db_pos.realized_pnl = pnl
                db_pos.closed_at = exit
                db.commit()
            db.close()
        except Exception:
            pass"""

    record_exit_new = """        # Also update SQLite (queued)
        self._db_exit_queue.append((trade_id, exit_price, pnl, exit))
        if len(self._db_exit_queue) >= 50:
            self.flush_db_exit_queue()

    def flush_db_exit_queue(self) -> None:
        if not self._db_exit_queue:
            return
        try:
            from app.db import SessionLocal
            from app.db.models import Position
            db = SessionLocal()
            trade_ids = [q[0] for q in self._db_exit_queue]

            # Use in_() to fetch all at once
            db_positions = db.query(Position).filter(Position.trade_id.in_(trade_ids)).all()
            pos_map = {p.trade_id: p for p in db_positions}

            for tid, x_price, x_pnl, x_time in self._db_exit_queue:
                if tid in pos_map:
                    pos_map[tid].is_open = False
                    pos_map[tid].current_price = x_price
                    pos_map[tid].realized_pnl = x_pnl
                    pos_map[tid].closed_at = x_time

            db.commit()
            db.close()
        except Exception:
            pass
        finally:
            self._db_exit_queue.clear()"""

    content = content.replace(record_exit_old, record_exit_new)

    with open("app/services/live_fill_tracker.py", "w") as f:
        f.write(content)
