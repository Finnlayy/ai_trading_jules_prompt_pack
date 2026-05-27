rm -f fix_*.py orig.py test_perf.py update_hurst.py test_*.py
pnpm lint || true
python -m pytest tests/
