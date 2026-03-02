import pytest
import time
from unittest.mock import patch
from src.services.yolo_service import YoloService
import queue

@pytest.fixture
def mock_queue():
    return queue.Queue(maxsize=105)

def test_yolo_service_processes_frames(clean_shared_state, mock_config, mock_queue, mocker):
    """Test YoloService reads frames from queue and sets person_detected."""
    clean_shared_state.set_volatile("camera_frame_queue", mock_queue)
    
    # Push 100 frames so it hits the % 100 check
    for _ in range(100):
        mock_queue.put("DUMMY_FRAME")
        
    mocker.patch('src.services.yolo_service.time.sleep', return_value=None) # Speed up test
    mocker.patch('src.services.yolo_service.random.choice', return_value=True) # Force detection
    
    service = YoloService(clean_shared_state, mock_config)
    service.start()
    
    # Wait for the thread to process the 100 frames
    # Since sleep is mocked, it should be near instant
    time.sleep(0.2)
    service.stop()
    service.join(timeout=1.0)
    
    assert mock_queue.empty()
    assert clean_shared_state.get_volatile("person_detected") is True
    assert service.consecutive_errors == 0

def test_yolo_service_missing_queue(clean_shared_state, mock_config, mocker):
    """Test YoloService when the camera queue does not exist."""
    if "camera_frame_queue" in clean_shared_state._volatile_data:
        del clean_shared_state._volatile_data["camera_frame_queue"]
        
    mocker.patch('src.services.yolo_service.time.sleep', return_value=None)
    
    service = YoloService(clean_shared_state, mock_config)
    service.start()
    
    time.sleep(0.1)
    service.stop()
    service.join(timeout=1.0)
    
    # Missing queue means it hit the report_error() path
    assert service.consecutive_errors > 0
