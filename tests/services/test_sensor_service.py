import pytest
import time
from unittest.mock import patch
from src.services.sensor_service import SensorsService

def test_sensor_service_initialization(clean_shared_state, mock_config, mocker):
    """Test SensorService updates shared state volatile variables."""
    # Mock sleep to speed up the test
    mocker.patch('time.sleep', return_value=None)
    mocker.patch('random.uniform', return_value=0.0)
    mocker.patch('random.random', return_value=1.0)
    
    service = SensorsService(clean_shared_state, mock_config)
    service.start()
    
    # Give it a tiny moment since run() is in a thread
    time.sleep(0.1)
    service.stop()
    service.join(timeout=1.0)
    
    # Values should be initialized and set in volatile memory
    assert clean_shared_state.get_volatile("voltage") == 12.5
    assert clean_shared_state.get_volatile("cpu_temp") == 45.0
    assert service.consecutive_errors == 0
