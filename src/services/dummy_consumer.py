import time
import queue
from src.core.base_service import BaseService

class DummyConsumer(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

    def _main_loop(self):
        q = self.shared_state.get_volatile("camera_frame_queue")
        # Services cannot use whiles because if they get died, they will staty kind of zombie
        # for that reason we use self._stop_event.is_set()
        while not self._stop_event.is_set():
            try:
                number = q.get(timeout=1.0)
                # I added a timeout because "q.get" will take one second checking if there's a value
                # if not it will give a queue.Empty immediately we jump into the except
                self.logger.info(f"Consumed the number: {number}")
                self.report_health()
                time.sleep(0.5)
            except queue.Empty:
                pass