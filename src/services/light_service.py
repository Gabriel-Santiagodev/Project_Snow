# ==============================================================================
# PROJECT SNOW - LIGHT SERVICE
# ==============================================================================
# Version: 1.0
# Last Updated: August 2026
# Author: Ruben Gabriel Aguilar Santiago
# Purpose: Controls an industrial LED indicator connected to the Raspberry Pi
#          GPIO. When a blind person is detected (person_detected = True), the
#          LED turns on for a configurable duration, then turns off and resets
#          the shared state flag to allow the detection cycle to repeat.
# ==============================================================================

import time

try:
    from gpiozero import LED
except ImportError:
    LED = None

from src.core.base_service import BaseService


class LightService(BaseService):
    """
    Threaded service that drives an industrial LED indicator via GPIO.

    Reads the `person_detected` volatile flag from SharedState. When the flag
    is True, the LED is switched on for `on_duration_seconds`, then switched
    off and the flag is reset to False so the detection cycle can repeat.

    The waiting period uses `_stop_event.wait()` instead of a plain
    `time.sleep()` so the service shuts down immediately and gracefully even
    if the LED is currently on.

    Parameters
    ----------
    shared_state : SharedState
        Central thread-safe data store.
    config : dict
        Configuration dictionary loaded from settings.yaml.
    """

    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

        # 1. Read parameters from settings.yaml -- no hardcoded values
        pins_cfg = self.config.get("hardware", {}).get("pins", {})
        light_cfg = self.config.get("hardware", {}).get("light", {})

        self._pin = pins_cfg.get("indicator_led", 18)
        self._on_duration = light_cfg.get("on_duration_seconds", 5)

        # 2. Hardware initialization
        if LED is not None:
            try:
                self._led = LED(self._pin, initial_value=False)
                self.logger.info(
                    f"LED indicator initialized on BCM pin {self._pin}."
                )
            except Exception as e:
                self._led = None
                self.logger.error(
                    f"Failed to initialize LED on pin {self._pin}: {e}"
                )
        else:
            self._led = None
            self.logger.warning(
                "gpiozero not available. Running in simulated mode -- "
                "LED actions will be logged only."
            )

    # --------------------------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------------------------

    def _main_loop(self):
        """
        Service business logic.

        Lifecycle
        ---------
        1. Poll `last_person_detected_time` from SharedState at 10 Hz.
        2. If current time is within `on_duration_seconds` of last detection, LED stays ON.
        3. If time expires, LED goes OFF.
        4. Report health or error to the Watchdog on each iteration.
        """
        self.logger.info("Starting light service main loop...")

        is_on = False

        while not self._stop_event.is_set():
            try:
                # 1. Read the detection timestamp from SharedState
                last_detection_time = self.shared_state.get_volatile("last_person_detected_time")

                if last_detection_time > 0 and (time.time() - last_detection_time) <= self._on_duration:
                    if not is_on:
                        self.logger.info("Detection active. Activating LED indicator.")
                        self._turn_led_on()
                        is_on = True
                else:
                    if is_on:
                        self.logger.info("Detection expired. LED deactivated.")
                        self._turn_led_off()
                        is_on = False

                # 3. Report healthy iteration to the Watchdog
                self.report_health()

                # 4. Prevent 100% CPU utilization
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Unexpected error in light service: {e}")
                self.report_error()
                time.sleep(1)

        # Graceful shutdown: ensure LED is off before the thread exits
        self._shutdown_hardware()

    # --------------------------------------------------------------------------
    # HARDWARE HELPERS
    # --------------------------------------------------------------------------

    def _turn_led_on(self):
        """Switches the LED on, or logs the action in simulated mode."""
        if self._led is not None:
            try:
                self._led.on()
            except Exception as e:
                self.logger.error(f"Hardware error turning LED on: {e}")
                self.report_error()
        else:
            self.logger.info("[SIMULATED] LED ON")

    def _turn_led_off(self):
        """Switches the LED off, or logs the action in simulated mode."""
        if self._led is not None:
            try:
                self._led.off()
            except Exception as e:
                self.logger.error(f"Hardware error turning LED off: {e}")
                self.report_error()
        else:
            self.logger.info("[SIMULATED] LED OFF")

    def _shutdown_hardware(self):
        """Releases GPIO resources when the thread stops."""
        self.logger.info("Releasing LED hardware resources...")
        self._turn_led_off()
        if self._led is not None:
            try:
                self._led.close()
            except Exception as e:
                self.logger.error(f"Error closing LED GPIO resource: {e}")
