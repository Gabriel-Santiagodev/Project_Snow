import time
import queue
from src.core.base_service import BaseService
from ultralytics import YOLO

class YoloService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

        self.model = YOLO(self.config.get("software",{}).get("ai_model", {}).get("model_path","data/models/best.pt"))
        self.frame_queue = self.shared_state.get_volatile("camera_frame_queue")  # gets image -> queue.get()
        self.conf_threshold = self.config.get("software",{}).get("ai_model",{}).get("confidence_threshold", 0.85)

    def _main_loop(self):
        while not self._stop_event.is_set():
            try:
                results = self.model(self.frame_queue.get(timeout=1) )          # We took a frame from the tail (the last one)

                detected = any(box.conf[0] >= self.conf_threshold for box in results[0].boxes)

                if detected:
                    self.shared_state.set_volatile("person_detected", True)

                self.report_health()                                            # We made sure everything went well

                time.sleep(0.05)                                                   # throttle
            
            except queue.Empty:                                                # Frame queue vacía es normal, no es un errorreal
                self.report_health()
                pass
            except Exception as e:
                self.logger.error(f"Unexpected error in YOLOservice: {e}")
                self.report_error()
                time.sleep(1)


