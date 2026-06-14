import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.services.reconciliation_daemon import ReconciliationDaemon

@pytest.mark.asyncio
async def test_reconciliation_kill_trigger():
    daemon = ReconciliationDaemon()
    daemon.broker = MagicMock()
    daemon.broker.get_positions.return_value = [1, 2, 3] # 3 remote
    daemon.broker.close_all_positions = MagicMock()
    daemon.broker.cancel_all_orders = MagicMock()

    with patch('app.services.reconciliation_daemon.SessionLocal') as mock_session_cls:
        mock_session = mock_session_cls.return_value
        mock_session.query.return_value.all.return_value = [1, 2] # 2 local

        await daemon._reconcile()

        # Should have called close_all_positions due to divergence
        daemon.broker.close_all_positions.assert_called_once()
        daemon.broker.cancel_all_orders.assert_called_once()
