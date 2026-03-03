import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

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
    return SharedState()