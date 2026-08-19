# ==============================================================================
# PROJECT SNOW - CONFTEST FOR SERVICE TESTS
# ==============================================================================
# Purpose: Shared fixtures exclusively for the test_services suite.
#          Provides a full mock_config that mirrors the shape of settings.yaml
#          so every service can be instantiated without touching real hardware.
# ==============================================================================

import queue
import pytest
from unittest.mock import MagicMock


# ------------------------------------------------------------------------------
# CONFIGURATION FIXTURE
# ------------------------------------------------------------------------------

@pytest.fixture
def service_config():
    """
    Full mock configuration that mirrors settings.yaml structure.

    Every service reads from this dict via self.config.get(...).
    Values are representative defaults — identical to what the real YAML holds —
    so tests exercise the same code paths as production.
    """
    return {
        "hardware": {
            "cameras": {
                "camera1": {
                    "src": 0,
                    "zones": {
                        "capture_zone": {
                            "coords": [160, 120, 480, 360]
                        }
                    },
                },
                "camera2": {
                    "src": 1,
                    "zones": {
                        "capture_zone": {
                            "coords": [160, 120, 480, 360]
                        }
                    },
                },
            },
            "audio": {
                "volume": 0.8,
                "cooldown_seconds": 2.0,
                "audio_files": {
                    "testing_audio0_path": "data/audio/testing_audio0.mp3",
                },
            },
            "pins": {
                "indicator_led": 18,
                "emergency_light": 17,
                "reset_button": 27,
            },
            "light": {
                "on_duration_seconds": 5,
            },
            "oled": {
                "i2c_port": 1,
                "i2c_address": 0x3C,
                "display_duration_seconds": 5,
            },
        },
        "software": {
            "ai_model": {
                "model_path": "data/models/best.pt",
                "confidence_threshold": 0.85,
            },
            "camera_service": {
                "movement_threshold": 5.0,
                "freeze_timeout_seconds": 5.0,
                "sequence_timeout_seconds": 10.0,
                "debug": False,
            },
        },
        "system": {
            "max_thread_restarts": 3,
            "max_errors_before_reboot": 5,
        },
    }


# ------------------------------------------------------------------------------
# SHARED STATE FIXTURE
# ------------------------------------------------------------------------------

@pytest.fixture
def mock_shared_state():
    """
    MagicMock of SharedState pre-configured with the volatile keys that
    services read/write during normal operation.

    Using a MagicMock (instead of the real SharedState) isolates service
    logic from persistence/threading concerns and lets us assert exactly
    which methods were called with which arguments.
    """
    state = MagicMock()

    # Backing store for get/set_volatile so calls reflect each other
    volatile_store = {
        "person_detected": False,
        "camera_frame_queue": queue.Queue(maxsize=1),
    }

    def _get_volatile(key):
        return volatile_store.get(key)

    def _set_volatile(key, value):
        volatile_store[key] = value

    state.get_volatile.side_effect = _get_volatile
    state.set_volatile.side_effect = _set_volatile

    # Expose the backing store so tests can inspect / mutate it directly
    state._volatile_store = volatile_store

    return state
