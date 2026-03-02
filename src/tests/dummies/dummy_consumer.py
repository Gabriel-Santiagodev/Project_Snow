import time
import queue
from src.core.base_service import BaseService

class DummyConsumer(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

    def _main_loop(self):
        # Obtain the Queue memory reference
        q = self.shared_state.get_volatile("camera_frame_queue")
        
        while not self._stop_event.is_set():
            try:
                # We apply a timeout because q.get() is a blocking operation.
                # If the queue is empty for 1 second, it raises queue.Empty,
                # allowing the while loop to check the _stop_event flag and not get permanently stuck.
                number = q.get(timeout=1.0)
                
                self.logger.info(f"Consumer: Processed the number: {number}")
                self.report_health()
                time.sleep(0.5)
                
            except queue.Empty:
                # Queue is empty. Not an error, just wait for the producer.
                pass