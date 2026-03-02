import pytest
import time
from unittest.mock import patch
import queue

from src.services.camera_service import CameraService
from src.services.yolo_service import YoloService

def test_camera_yolo_pipeline(clean_shared_state, mock_config, mocker):
    """Test the interaction between Camera producing frames and Yolo processing them."""
    # Ensure a queue is set up
    clean_shared_state.set_volatile("camera_frame_queue", queue.Queue(maxsize=10))
    
    # Mock for Camera
    mocker.patch('src.services.camera_service.HAS_CV2', False)
    mocker.patch('src.services.camera_service.random.random', return_value=1.0) # Avoid breaking
    
    # Mock for Yolo: Make it much faster and process synthetic frames instantly
    mocker.patch('src.services.yolo_service.time.sleep', return_value=None)
    # Force YOLO to always detect a person on frame 3
    # Yolo uses `self.frame_count % 100 == 0`, let's patch that logic or just let it consume 100 frames
    # Or we can patch YoloService._main_loop? Better to patch random.choice to always be True
    mocker.patch('src.services.yolo_service.random.choice', return_value=True)
    
    # Start both services
    # We will not mock time.sleep here because it causes CPU pegging (infinite loops).
    # Instead, we just set yolo's frame count to 99 so the very first frame it processes
    # triggers the 'person_detected' logic.
    camera = CameraService(clean_shared_state, mock_config)
    yolo = YoloService(clean_shared_state, mock_config)
    
    yolo.frame_count = 99
    
    camera.start()
    yolo.start()
    
    # Wait for frame processing - realistically shouldn't take more than 0.2s
    time.sleep(0.5) 
    
    camera.stop()
    yolo.stop()
    
    camera.join(timeout=1.0)
    yolo.join(timeout=1.0)
    
    # Verification
    assert yolo.frame_count >= 100
    assert clean_shared_state.get_volatile("person_detected") is True
    
    # Health checks
    assert camera.consecutive_errors == 0
    assert yolo.consecutive_errors == 0
