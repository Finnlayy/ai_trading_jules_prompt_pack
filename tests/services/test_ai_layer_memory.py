import json
from pathlib import Path
import pytest
from app.services.ai_layer_memory import AILayerMemoryStore

def test_load_state_missing_file_returns_default(tmp_path):
    """Test that a missing memory file correctly initializes the default state."""
    file_path = tmp_path / "missing_memory.json"
    store = AILayerMemoryStore(filepath=str(file_path))

    state = store._load_state()

    assert "profile" in state
    assert "memory" in state
    assert state["memory"] == []

def test_load_state_invalid_json_returns_default(tmp_path):
    """Test that invalid JSON triggers the JSONDecodeError fallback to default state."""
    file_path = tmp_path / "bad_memory.json"
    file_path.write_text("{invalid json", encoding="utf-8")

    store = AILayerMemoryStore(filepath=str(file_path))
    state = store._load_state()

    assert "profile" in state
    assert "memory" in state
    assert state["memory"] == []

def test_load_state_os_error_returns_default(tmp_path, monkeypatch):
    """Test that file read errors trigger the OSError fallback to default state."""
    file_path = tmp_path / "error_memory.json"
    file_path.write_text('{"profile": {}, "memory": []}', encoding="utf-8")

    # Mock read_text to raise an OSError
    def mock_read_text(*args, **kwargs):
        raise OSError("Mocked OS Error")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    store = AILayerMemoryStore(filepath=str(file_path))
    state = store._load_state()

    assert "profile" in state
    assert "memory" in state
    assert state["memory"] == []
