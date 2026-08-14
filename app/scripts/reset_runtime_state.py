"""Reset disposable runtime state for the paper-training engine.

This script is intentionally explicit. It archives current runtime files by
default, removes them from the active workspace, and recreates the SQLite schema
from SQLAlchemy models. It does not run automatically at app startup.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


RUNTIME_RELATIVE_PATHS = (
    "app/data/trading.db",
    "trade_journal.jsonl",
    "data/positions.json",
    "data/last_processed_bars.json",
    "data/shadow_queue.jsonl",
    "data/drill_results.jsonl",
    "data/agent_careers.jsonl",
    "data/agent_registry.json",
    "data/curriculum_progress.json",
    "data/strategies.json",
    "logs/confidence_registry.json",
    "logs/ai_memory.json",
)

SQLITE_COMPANION_SUFFIXES = ("-wal", "-shm")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _assert_within_root(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise RuntimeError(f"Refusing to reset path outside workspace: {resolved_path}")


def collect_runtime_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in RUNTIME_RELATIVE_PATHS:
        path = root / relative
        paths.append(path)
        if relative.endswith(".db"):
            for suffix in SQLITE_COMPANION_SUFFIXES:
                paths.append(root / f"{relative}{suffix}")
    return paths


def archive_or_remove(paths: list[Path], root: Path, archive: bool) -> tuple[list[Path], Path | None]:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return [], None

    archive_dir: Path | None = None
    if archive:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = root / "data" / "runtime_archive" / timestamp
        archive_dir.mkdir(parents=True, exist_ok=True)

    removed: list[Path] = []
    for path in existing:
        _assert_within_root(path, root)
        if archive_dir:
            relative = path.relative_to(root)
            target = archive_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path)

    return removed, archive_dir


def recreate_database() -> None:
    from app.db import Base, engine

    Base.metadata.create_all(bind=engine)


def reset_runtime_state(root: Path | None = None, archive: bool = True) -> dict[str, object]:
    root = root or repo_root()
    _assert_within_root(root, root)
    removed, archive_dir = archive_or_remove(collect_runtime_paths(root), root, archive)
    recreate_database()
    return {
        "status": "ok",
        "removed_count": len(removed),
        "removed": [str(path.relative_to(root)) for path in removed],
        "archive_dir": str(archive_dir.relative_to(root)) if archive_dir else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset disposable trading runtime state.")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete runtime files instead of archiving them first.",
    )
    args = parser.parse_args()

    result = reset_runtime_state(archive=not args.delete)
    print(f"status={result['status']}")
    print(f"removed_count={result['removed_count']}")
    if result["archive_dir"]:
        print(f"archive_dir={result['archive_dir']}")
    for path in result["removed"]:
        print(f"removed={path}")


if __name__ == "__main__":
    main()
