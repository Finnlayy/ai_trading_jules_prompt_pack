"""Tests for the disposable runtime-state reset script."""

from __future__ import annotations

from pathlib import Path

from app.scripts import reset_runtime_state as reset_script


def test_collect_runtime_paths_includes_sqlite_companions(tmp_path):
    paths = {path.relative_to(tmp_path).as_posix() for path in reset_script.collect_runtime_paths(tmp_path)}

    assert "app/data/trading.db" in paths
    assert "app/data/trading.db-wal" in paths
    assert "app/data/trading.db-shm" in paths


def test_reset_runtime_state_archives_runtime_files(tmp_path, monkeypatch):
    db_path = tmp_path / "app" / "data" / "trading.db"
    confidence_path = tmp_path / "logs" / "confidence_registry.json"
    db_path.parent.mkdir(parents=True)
    confidence_path.parent.mkdir(parents=True)
    db_path.write_text("old db", encoding="utf-8")
    confidence_path.write_text("{}", encoding="utf-8")

    recreated = {"called": False}

    def fake_recreate_database() -> None:
        recreated["called"] = True

    monkeypatch.setattr(reset_script, "recreate_database", fake_recreate_database)

    result = reset_script.reset_runtime_state(root=tmp_path, archive=True)

    assert result["status"] == "ok"
    assert result["removed_count"] == 2
    assert result["archive_dir"] is not None
    assert recreated["called"] is True
    assert not db_path.exists()
    assert not confidence_path.exists()

    archive_dir = tmp_path / str(result["archive_dir"])
    assert (archive_dir / "app" / "data" / "trading.db").read_text(encoding="utf-8") == "old db"
    assert (archive_dir / "logs" / "confidence_registry.json").read_text(encoding="utf-8") == "{}"


def test_reset_refuses_paths_outside_root(tmp_path):
    outside = Path(tmp_path).parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")

    try:
        try:
            reset_script.archive_or_remove([outside], tmp_path, archive=False)
        except RuntimeError as exc:
            assert "outside workspace" in str(exc)
        else:
            raise AssertionError("Expected outside path to be rejected")
    finally:
        outside.unlink(missing_ok=True)
