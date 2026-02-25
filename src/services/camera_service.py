from src.core.base_service import BaseService
import time
import random

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

class CameraService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        self.cap = None
        self.broken = False

    def _main_loop(self):
        if HAS_CV2:
            # Open the default webcam
            self.cap = cv2.VideoCapture(0)
            
            if not self.cap.isOpened():
                self.logger.warning("Failed to open webcam via cv2. Falling back to simulated frames.")
                self.cap = None
            else:
                self.logger.info("Webcam successfully opened.")
        else:
            self.logger.warning("cv2 not installed. Proceeding with simulated frames.")

        try:
            while not self._stop_event.is_set():
                frame = None
                ret = False
                
                if self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                
                if not ret:
                    # Generate a dummy synthetic frame
                    # representing a 640x480 gray image
                    frame = "SIMULATED_FRAME_DATA" 
                    ret = True
                
                if ret:
                    # SIMULATE RANDOM HARDWARE FAILURE FOR TESTING
                    if not self.broken and random.random() < 0.02: # 2% chance to break permanently
                        self.broken = True
                        
                    if self.broken:
                        self.logger.error("SIMULATED ERROR: Camera hardware permanently glitching!")
                        self.report_error()
                        time.sleep(0.5)
                        continue # Skip putting frame
                        
                    # Grab the volatile queue from shared state
                    frame_queue = self.shared_state.get_volatile("camera_frame_queue")
                    
                    # Keep the queue from growing infinitely if YoloService is slow/dead
                    if frame_queue is not None:
                        if frame_queue.full():
                            # Discard oldest frame to keep latency low
                            try:
                                frame_queue.get_nowait()
                            except:
                                pass
                        
                        frame_queue.put(frame)
                        self.report_health()
                    else:
                        self.logger.warning("Camera queue not found in shared state.")
                        self.report_error()
                        time.sleep(1)
                
                # Small sleep to limit frame rate ~30 FPS
                time.sleep(0.033)
                
        finally:
            if self.cap:
                self.cap.release()
                self.logger.info("Webcam released.")
