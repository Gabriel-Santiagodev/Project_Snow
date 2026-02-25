from src.core.base_service import BaseService
import time
import random

class YoloService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        self.frame_count = 0

    def _main_loop(self):
        self.logger.info("YOLO AI Service Initialized (Simulated Mode).")
        
        while not self._stop_event.is_set():
            frame_queue = self.shared_state.get_volatile("camera_frame_queue")
            
            if frame_queue is not None:
                if not frame_queue.empty():
                    # Consume a frame
                    frame = frame_queue.get()
                    self.frame_count += 1
                    
                    # Simulate processing time
                    time.sleep(0.05)
                    
                    # Every ~100 frames (~3 seconds), randomly decide if a person is detected
                    if self.frame_count % 100 == 0:
                        detected = random.choice([True, False])
                        self.shared_state.set_volatile("person_detected", detected)
                        
                        if detected:
                            self.logger.info("!!! SIMULATED PERSON DETECTED !!!")
                        else:
                            self.logger.info("Area clear.")
                    
                    self.report_health()
                else:
                    # Queue is empty, wait a bit
                    time.sleep(0.1)
                    self.report_health() # Being empty isn't an error
            else:
                self.logger.warning("Camera queue not found by YoloService.")
                self.report_error()
                time.sleep(1)
