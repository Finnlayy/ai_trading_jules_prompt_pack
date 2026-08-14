from __future__ import annotations

import sys


def require_python_311() -> None:
    if sys.version_info[:2] != (3, 11):
        detected = f"{sys.version_info[0]}.{sys.version_info[1]}"
        raise SystemExit(f"Academy PPO requires Python 3.11; detected Python {detected}")
