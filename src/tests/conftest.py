import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.shared_state import SharedState

@pytest.fixture
def mock_config():
    """Provides a basic mock configuration for tests."""
    return {
        'system': {
            'max_thread_restarts': 3,
            'max_errors_before_reboot': 5
        },
        'services': {
            'MockService': {'enabled': True, 'camera_index': 0}
        }
    }

@pytest.fixture
def clean_shared_state():
    """Provides a fresh instance of SharedState for each test."""
    state = SharedState()
    # Reset internal tracking explicitly just in case (SharedState is a singleton usually, 
    # but in python classes without metaclass it returns a new instance unless logic prevents it)
    state.data = {}
    
    # We should make sure we're getting a fresh state per test. 
    # If SharedState is imported, we should reset it.
    
    # Looking at src/core/shared_state.py ... I need to verify its implementation.
    return state