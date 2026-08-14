"""E2E test isolation: strip pytest-asyncio markers to avoid event-loop conflict with playwright."""

import os

E2E_DIR = os.path.dirname(os.path.abspath(__file__))


def pytest_collection_modifyitems(config, items):
    for item in items:
        # Only strip asyncio markers from items that live inside tests/e2e
        if not str(item.path).startswith(E2E_DIR):
            continue
        to_remove = [m for m in getattr(item, "own_markers", []) if m.name == "asyncio"]
        for m in to_remove:
            item.own_markers.remove(m)
