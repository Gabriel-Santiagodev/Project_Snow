import pytest
import time
from unittest.mock import MagicMock, patch
from src.services.camera_service import CameraService
import queue

@pytest.fixture
def mock_queue():
    return queue.Queue(maxsize=10)

def test_camera_service_synthetic_frame(clean_shared_state, mock_config, mock_queue, mocker):
    """Test camera service generating synthetic frames when cv2 fails or is absent."""
    clean_shared_state.set_volatile("camera_frame_queue", mock_queue)
    
    # Mock cv2 and random
    mocker.patch('src.services.camera_service.HAS_CV2', False)
    mocker.patch('random.random', return_value=1.0) # Prevent random breaking
    
    service = CameraService(clean_shared_state, mock_config)
    service.start()
    
    # Wait for a couple frames to be pushed
    time.sleep(0.15)
    service.stop()
    service.join(timeout=1.0)
    
    # Queue should have synthetic frames
    assert not mock_queue.empty()
    frame = mock_queue.get_nowait()
    assert frame == "SIMULATED_FRAME_DATA"
    assert service.consecutive_errors == 0
    
def test_camera_service_simulated_break(clean_shared_state, mock_config, mock_queue, mocker):
    """Test that camera service transitions to broken state properly."""
    clean_shared_state.set_volatile("camera_frame_queue", mock_queue)
    
    mocker.patch('src.services.camera_service.HAS_CV2', False)
    # Force the 2% random break to trigger immediately
    mocker.patch('random.random', return_value=0.01)
    
    service = CameraService(clean_shared_state, mock_config)
    service.start()
    
    # Wait for break logic to execute
    time.sleep(0.1)
    service.stop()
    service.join(timeout=1.0)
    
    # It should have registered errors
    assert service.consecutive_errors > 0
    assert service.broken is True

def test_camera_service_missing_queue(clean_shared_state, mock_config, mocker):
    """Test camera service error reporting if the queue is missing."""
    # Target the missing queue branch by removing the default queue
    if "camera_frame_queue" in clean_shared_state._volatile_data:
        del clean_shared_state._volatile_data["camera_frame_queue"]
    
    mocker.patch('src.services.camera_service.HAS_CV2', False)
    mocker.patch('random.random', return_value=1.0) 
    
    service = CameraService(clean_shared_state, mock_config)
    service.start()
    
    # Wait
    time.sleep(0.1)
    service.stop()
    service.join(timeout=1.0)
    
    # Missing queue means it hit the error path
    assert service.consecutive_errors > 0
