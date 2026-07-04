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
