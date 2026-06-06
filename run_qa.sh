#!/usr/bin/env bash
set -euo pipefail

echo "=== Backend + TDD Tests ==="
python -m pytest tests/api/ tests/db/ tests/research/ tests/schemas/ tests/services/ tests/tdd_autonomous_queue.py tests/tdd_architectural_audit.py -v

echo ""
echo "=== E2E Playwright Tests ==="
python -m pytest tests/e2e/ -v --browser chromium

echo ""
echo "=== All QA passed ==="
