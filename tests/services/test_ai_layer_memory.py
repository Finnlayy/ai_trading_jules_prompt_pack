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
import pytest
from app.services.ai_layer_memory import AILayerMemoryStore
from app.schemas.ai_layer import AIBehaviorProfile

def test_default_state(tmp_path):
    filepath = tmp_path / "ai_layer_memory.json"
    store = AILayerMemoryStore(filepath=str(filepath))

    # Should load default state if file doesn't exist
    profile = store.get_profile()
    assert profile.trading_style == "balanced"
    assert profile.risk_tolerance == "moderate"
    assert len(store.get_memory()) == 0

def test_corrupt_file(tmp_path):
    filepath = tmp_path / "ai_layer_memory.json"
    filepath.write_text("invalid json", encoding="utf-8")
    store = AILayerMemoryStore(filepath=str(filepath))

    # Should fall back to default state safely
    profile = store.get_profile()
    assert profile.trading_style == "balanced"

def test_get_and_update_profile(tmp_path):
    filepath = tmp_path / "ai_layer_memory.json"
    store = AILayerMemoryStore(filepath=str(filepath))

    # Update profile with allowed fields
    patch = {"trading_style": "aggressive", "invalid_field": "ignore"}
    updated = store.update_profile(patch)

    assert updated.trading_style == "aggressive"
    assert not hasattr(updated, "invalid_field")

    # Verify changes were saved
    profile = store.get_profile()
    assert profile.trading_style == "aggressive"

    # File should exist now
    assert filepath.exists()
    data = json.loads(filepath.read_text(encoding="utf-8"))
    assert data["profile"]["trading_style"] == "aggressive"

def test_append_message_and_get_memory(tmp_path):
    filepath = tmp_path / "ai_layer_memory.json"
    store = AILayerMemoryStore(filepath=str(filepath))

    # Append 45 messages (more than the 40 returned by get_memory, but less than 80 stored)
    for i in range(45):
        store.append_message(role="user", content=f"msg_{i}")

    memory = store.get_memory()

    # get_memory() limits to 40 items
    assert len(memory) == 40
    # ensure we get the latest ones
    assert memory[-1].content == "msg_44"
    assert memory[0].content == "msg_5"

    # file should have stored up to 80 (so 45 here)
    data = json.loads(filepath.read_text(encoding="utf-8"))
    assert len(data["memory"]) == 45

def test_reset(tmp_path):
    filepath = tmp_path / "ai_layer_memory.json"
    store = AILayerMemoryStore(filepath=str(filepath))

    store.update_profile({"trading_style": "aggressive"})
    store.append_message(role="user", content="hello")

    assert store.get_profile().trading_style == "aggressive"
    assert len(store.get_memory()) == 1

    # Reset
    store.reset()

    assert store.get_profile().trading_style == "balanced"
    assert len(store.get_memory()) == 0

def test_behavior_prompt(tmp_path):
    filepath = tmp_path / "ai_layer_memory.json"
    store = AILayerMemoryStore(filepath=str(filepath))

    store.update_profile({
        "trading_style": "conservative",
        "risk_tolerance": "low",
        "preferred_symbols": ["BTCUSDT", "ETHUSDT"],
        "max_risk_pct": 2.5
    })

    prompt = store.behavior_prompt()

    assert "conservative" in prompt
    assert "low" in prompt
    assert "BTCUSDT, ETHUSDT" in prompt
    assert "2.5" in prompt
import pytest
import json
from app.services.ai_layer_memory import AILayerMemoryStore
from app.schemas.ai_layer import AIBehaviorProfile

def test_ai_layer_memory_initialization_and_default_state(tmp_path):
    path = tmp_path / "memory.json"
    store = AILayerMemoryStore(filepath=str(path))
    profile = store.get_profile()
    assert isinstance(profile, AIBehaviorProfile)
    assert len(store.get_memory()) == 0

def test_ai_layer_memory_truncation(tmp_path):
    path = tmp_path / "memory.json"
    store = AILayerMemoryStore(filepath=str(path))

    # Append 100 messages
    for i in range(100):
        store.append_message("user", f"msg {i}")

    memory = store.get_memory()
    assert len(memory) == 40  # Returns the last 40 messages
    assert memory[0].content == "msg 60"
    assert memory[-1].content == "msg 99"

def test_ai_layer_memory_corrupted_json(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{corrupted: true")

    # Initialize pointing to corrupted file
    store = AILayerMemoryStore(filepath=str(path))
    profile = store.get_profile()
    # Should fallback to default profile gracefully
    assert isinstance(profile, AIBehaviorProfile)
    assert len(store.get_memory()) == 0
