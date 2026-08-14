import asyncio
import logging
from app.core.config import BROKER_MODE
from app.services.broker_factory import BrokerFactory
from app.db import SessionLocal
from app.db.models import PaperPosition, PaperTrade

logger = logging.getLogger(__name__)

class ReconciliationDaemon:
    def __init__(self):
        self.running = False
        self.broker = None

    async def start(self):
        self.running = True
        self.broker = BrokerFactory.create(BROKER_MODE)
        logger.info(f"ReconciliationDaemon started with broker mode: {BROKER_MODE}")

        while self.running:
            await self._reconcile()
            await asyncio.sleep(30)

    async def _reconcile(self):
        db = SessionLocal()
        try:
            local_positions = db.query(PaperPosition).all()
            if self.broker:
                remote_positions = await asyncio.to_thread(self.broker.get_positions)
                if len(local_positions) != len(remote_positions):
                    logger.warning("Divergence detected between local DB and exchange!")
                    await self._emergency_kill()
        except Exception as e:
            logger.error(f"Error during reconciliation: {e}")
        finally:
            db.close()

    async def _emergency_kill(self):
        logger.critical("Triggering Emergency Kill loop due to divergence!")
        if self.broker:
            try:
                await asyncio.to_thread(self.broker.close_all_positions)
                await asyncio.to_thread(self.broker.cancel_all_orders)
            except Exception as e:
                logger.error(f"Failed to execute emergency kill: {e}")

    def stop(self):
        self.running = False

reconciliation_daemon = ReconciliationDaemon()
