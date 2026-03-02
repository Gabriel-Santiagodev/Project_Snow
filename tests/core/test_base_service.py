import pytest
import time
from src.core.base_service import BaseService

class DummyService(BaseService):
    """A concrete implementation of BaseService for testing."""
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        self.loop_count = 0

    def _main_loop(self):
        while not self._stop_event.is_set():
            self.loop_count += 1
            time.sleep(0.01)

class DummyCrashingService(BaseService):
    """A service that simulates an unhandled crash."""
    def _main_loop(self):
        raise ValueError("Simulated unhandled exception")

def test_base_service_lifecycle(clean_shared_state, mock_config):
    """Test standard start and gracefully stop behavior."""
    service = DummyService(clean_shared_state, mock_config)
    
    # Thread should not be alive initially
    assert not service.is_alive()
    
    # Start the service
    service.start()
    time.sleep(0.05) # Let it run a few loops
    
    assert service.is_alive()
    assert service.loop_count > 0
    
    # Stop the service
    service.stop()
    service.join(timeout=1.0)
    
    assert not service.is_alive()
    assert service._stop_event.is_set()

def test_health_reporting(clean_shared_state, mock_config):
    """Test error and health reporting increments/resets correctly."""
    service = DummyService(clean_shared_state, mock_config)
    
    assert service.consecutive_errors == 0
    
    service.report_error()
    assert service.consecutive_errors == 1
    
    service.report_error()
    assert service.consecutive_errors == 2
    
    service.report_health()
    assert service.consecutive_errors == 0

def test_unhandled_crash(clean_shared_state, mock_config):
    """Test that an unhandled exception in _main_loop doesn't crash the main process."""
    service = DummyCrashingService(clean_shared_state, mock_config)
    service.start()
    service.join(timeout=1.0)
    
    # Thread should be dead, but main thread is fine
    assert not service.is_alive()
