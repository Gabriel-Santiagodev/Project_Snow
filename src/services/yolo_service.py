import time
import queue
from src.core.base_service import BaseService

class yolo_service(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

        self.model_path = self.config["software"]["ai_model"]["model_path"]
        self.frame_queue = self.shared_sate.get_volatile("camera_frame_queue")

        def _main_loop(self):
            while not self._stop_event.is_set():
                try:
                    #logica de abraham
                    pass
                except:
                    pass


