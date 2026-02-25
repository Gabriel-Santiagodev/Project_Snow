from src.core.base_service import BaseService
import time
import os

class AudioService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        self.last_played = 0

    def _main_loop(self):
        self.logger.info("Audio Service Initialized (macOS 'say' Mode).")
        
        while not self._stop_event.is_set():
            person_detected = self.shared_state.get_volatile("person_detected")
            
            if person_detected:
                # Cooldown: Don't spam the audio. Play at most once every 5 seconds.
                current_time = time.time()
                if current_time - self.last_played > 5.0:
                    self.logger.info("Playing: 'Warning! Person detected.'")
                    # Use macOS built-in text-to-speech
                    os.system('say "Warning! Person detected."')
                    self.last_played = time.time()
                
            self.report_health()
            time.sleep(0.5)
