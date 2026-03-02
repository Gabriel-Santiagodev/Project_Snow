import time
from src.core.base_service import BaseService

class DummyProducer(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

    def _main_loop(self):
        counter = 0
        
        # CRITICAL MUTABILITY RULE:
        # Obtain the reference to mutable objects (Queues, Lists) ONLY ONCE before the loop.
        q = self.shared_state.get_volatile("camera_frame_queue")
        
        # LIFECYCLE RULE: 
        # Standard 'while True' loops are prohibited to prevent zombie threads.
        # Always use self._stop_event.is_set() to allow graceful shutdowns.
        while not self._stop_event.is_set():
            counter += 1
            
            # Using native methods (.put) on the mutable object.
            # NEVER use set_volatile() for a Queue, as it overrides the original memory reference.
            q.put(counter)
            
            self.logger.info(f"Producer: {counter} added to the queue.")
            self.report_health()
            time.sleep(1)