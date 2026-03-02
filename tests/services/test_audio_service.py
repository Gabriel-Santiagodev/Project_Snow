import pytest
import time
from unittest.mock import patch
from src.services.audio_service import AudioService

@patch('os.system')
def test_audio_service_no_detection(mock_os_system, clean_shared_state, mock_config):
    """Test that AudioService does nothing when person_detected is False."""
    clean_shared_state.set_volatile("person_detected", False)
    
    service = AudioService(clean_shared_state, mock_config)
    service.start()
    
    time.sleep(0.1)
    service.stop()
    service.join(timeout=1.0)
    
    # Should report health, but not call os.system
    assert service.consecutive_errors == 0
    mock_os_system.assert_not_called()

@patch('os.system')
def test_audio_service_person_detected(mock_os_system, clean_shared_state, mock_config):
    """Test that AudioService plays audio exactly once when person is detected (respecting cooldown)."""
    clean_shared_state.set_volatile("person_detected", True)
    
    service = AudioService(clean_shared_state, mock_config)
    service.start()
    
    # Wait enough for a few loops (loop sleep is 0.5s)
    time.sleep(1.2)
    service.stop()
    service.join(timeout=1.0)
    
    # Should report health
    assert service.consecutive_errors == 0
    # Because cooldown is 5 seconds, it should have only called 'say' exactly once 
    # despite parsing the detection variable twice (at t=0, t=0.5, t=1.0)
    mock_os_system.assert_called_once_with('say "Warning! Person detected."')
