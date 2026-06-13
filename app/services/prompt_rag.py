import logging
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import PaperPosition

logger = logging.getLogger(__name__)

class PromptRAG:
    def __init__(self):
        pass

    def get_past_outcomes(self, symbol: str, limit: int = 3):
        """Query past trade outcomes from the SQLite database."""
        gen = get_db()
        db: Session = next(gen)
        try:
            outcomes = db.query(PaperPosition).filter(
                PaperPosition.symbol == symbol,
                PaperPosition.status == "CLOSED"
            ).order_by(PaperPosition.closed_at.desc()).limit(limit).all()

            return outcomes
        except Exception as e:
            logger.error(f"Error querying past outcomes: {e}")
            return []
        finally:
            try:
                next(gen)
            except StopIteration:
                pass

prompt_rag = PromptRAG()
