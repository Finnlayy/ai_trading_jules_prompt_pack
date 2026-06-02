import time
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Position
from app.services.live_fill_tracker import live_fill_tracker, FillData

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

import app.db
app.db.SessionLocal = Session

trade_ids = []
for _ in range(100):
    trade_id = f"test-{uuid4()}"
    trade_ids.append(trade_id)
    live_fill_tracker.record_intent(
        trade_id=trade_id,
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=50000.0,
        stop_price=49000.0,
        target_price=52000.0,
        decision="PROCEED_TO_SIMULATION",
    )
    live_fill_tracker.record_fill(
        trade_id=trade_id,
        fill_data=FillData(
            entry_price=50000.0,
            size=1.0,
            side="buy",
            fees=0.0,
            slippage=0.0,
            fill_time=datetime.now(timezone.utc),
        )
    )

start_time = time.perf_counter()
for trade_id in trade_ids:
    live_fill_tracker.record_exit(trade_id, 51000.0)
end_time = time.perf_counter()
print(f"BASELINE: Time taken to exit 100 positions: {(end_time - start_time) * 1000:.2f} ms")
