import pytest
import os
import json
from src.core.shared_state import SharedState

@pytest.fixture
def tmp_state_path(tmp_path):
    """Provides a temporary json path for testing SharedState."""
    return str(tmp_path / "test_system_state.json")

@pytest.fixture
def shared_state(tmp_state_path):
    """Provides a clean SharedState instance with a temporary file."""
    state = SharedState(json_path=tmp_state_path)
    return state

def test_shared_state_initialization(shared_state, tmp_state_path):
    """Test that it initializes correctly and creates the default json."""
    assert os.path.exists(tmp_state_path)
    
    with open(tmp_state_path, 'r') as f:
        data = json.load(f)
    
    assert "resilience" in data
    assert "scientific_metrics" in data

def test_get_set_resilience(shared_state):
    """Test setting and getting resilience metrics."""
    shared_state.set_resilience("test_key", 42)
    assert shared_state.get_resilience("test_key") == 42
    
def test_get_set_metric(shared_state):
    """Test setting and getting scientific metrics."""
    shared_state.set_metric("people_count", 5)
    assert shared_state.get_metric("people_count") == 5

def test_get_set_volatile(shared_state):
    """Test volatile storage (not saved to disk)."""
    shared_state.set_volatile("temp_var", "hello")
    assert shared_state.get_volatile("temp_var") == "hello"

def test_persistence_across_instances(tmp_state_path):
    """Test that data is actually saved and loaded from disk."""
    state1 = SharedState(json_path=tmp_state_path)
    state1.set_resilience("saved_val", 99)
    
    # Create a new instance pointing to the same file
    state2 = SharedState(json_path=tmp_state_path)
    assert state2.get_resilience("saved_val") == 99
