import time
from src.core.base_service import BaseService

class DummyProducer(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

    def _main_loop(self):
        counter = 0
        q = self.shared_state.get_volatile("camera_frame_queue")
        # Services cannot use whiles because if they get died, they will staty kind of zombie
        # for that reason we use self._stop_event.is_set()
        while not self._stop_event.is_set():
            counter += 1
            # In complex objetcs such as queues or lists we must only use get_volatile
            # because these objetcs are mutables so we are changing the original object
            # but if we use "set" we are creating a new object so a new queue each iteration
            # In simple objects such as booleans or numbers we must use sent_volatile becuase
            # we want to make it again
            q.put(counter)
            self.logger.info(f"{counter} added")
            self.report_health()
            time.sleep(1)