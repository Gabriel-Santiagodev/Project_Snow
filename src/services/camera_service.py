import time
import queue
from src.core.base_service import BaseService

class cameras_service(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        self.resololution_camera_uno = config["hardware"]["cameras"]["camera1"]["resolution"]

        self.frame_queue = self.shared_state.get_volatile("camera_frame_queue")
    
    def _main_loop(self):
        self.logger.info("schos va a iniciar su servicio")
        while not self._stop_event.is_set():
            try:
                #la logica de camaras de schos :D
                pass
            except queue.emtpy:
                self.logger.error("schos no hizo su chamba")