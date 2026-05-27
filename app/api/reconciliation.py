"""
API endpoint for ledger ↔ exchange reconciliation.
"""

from fastapi import APIRouter
from typing import Any

from app.api.orchestrator import broker_instance

router = APIRouter()


@router.post("/run", tags=["reconciliation"])
async def run_reconciliation() -> dict[str, Any]:
    """Run a manual reconciliation between local ledger and exchange positions."""
    if hasattr(broker_instance, "reconcile_ledger"):
        result = broker_instance.reconcile_ledger()
        return {"status": "ok", **result}
    return {"status": "not_supported", "reason": "Current broker does not support reconciliation"}
