import time
from os import environ

import pygame

from src.core.base_service import BaseService

# Hide the Pygame support prompt in the console
environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"


class AudioService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

        # 1. Read parameters from settings.yaml
        audio_cfg = self.config.get("hardware", {}).get("audio", {})
        audio_files_cfg = audio_cfg.get("audio_files", {})

        # Fetch the specific alert audio path
        self.audio_file = audio_files_cfg.get(
            "testing_audio0_path", "data/audio/testing_audio0.mp3"
        )
        self.volume = audio_cfg.get("volume", 0.8)
        self.cooldown = audio_cfg.get("cooldown_seconds", 2.0)

        # 2. Internal state variables
        self.last_played_time = 0.0

        # 3. Hardware initialization
        try:
            pygame.mixer.init()
            self.logger.info(f"Audio system initialized. File: {self.audio_file}")
        except Exception as e:
            self.logger.error(f"Critical failure initializing Pygame Mixer: {e}")

    def _main_loop(self):
        self.logger.info("Starting audio service main loop...")

        # Safe lifecycle loop
        while not self._stop_event.is_set():
            try:
                # 1. Read the immutable flag
                play_signal = self.shared_state.get_volatile("person_detected")

                if play_signal:
                    current_time = time.time()

                    # Check if the cooldown period has elapsed
                    if (current_time - self.last_played_time) >= self.cooldown:
                        self.logger.info("Audio signal received. Playing...")

                        try:
                            pygame.mixer.music.load(self.audio_file)
                            pygame.mixer.music.set_volume(self.volume)
                            pygame.mixer.music.play()
                            self.last_played_time = current_time
                        except pygame.error as e:
                            self.logger.error(f"Hardware error playing audio: {e}")
                            self.report_error()  # <- Report failure to Watchdog
                            time.sleep(1)
                            continue  # <- Skip report_health()

                    # 2. Turn off the flag immediately to prevent infinite looping
                    self.shared_state.set_volatile("person_detected", False)

                # 3. If successful, report health to the Watchdog
                self.report_health()

                # 4. Prevent 100% CPU utilization
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Unexpected error in audio service: {e}")
                self.report_error()
                time.sleep(1)

        # Safe shutdown upon exiting the loop
        self._shutdown_hardware()

    def _shutdown_hardware(self):
        """Releases hardware resources when the thread stops."""
        self.logger.info("Closing audio system and releasing hardware...")
        try:
            pygame.mixer.quit()
        except Exception as e:
            self.logger.error(f"Error closing Pygame Mixer: {e}")
