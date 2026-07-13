import time
import queue
from src.core.base_service import BaseService

class yolo_service(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

        self.model_path = self.config["software"]["ai_model"]["model_path"]
        self.frame_queue = self.shared_sate.get_volatile("camera_frame_queue")  # gets image -> queue.get()

        def _main_loop(self):
            while not self._stop_event.is_set():
                try:
                    results = self.model_path(self.frame_queue.get(timeout=1) )     # We took a frame from the tail (the last one)

                    detected = len(results[0].boxes) > 0        # If it has a length greater than zero, it means it found an object

                    self.shared_state.set_volatile("person_detected", detected)     # We assign the detection to person_detected

                    self.report_health()                        # We made sure everything went well
                except:
                    self.logger.warning("Report error in Yolo Service")
                    self.report_error()
                    pass


