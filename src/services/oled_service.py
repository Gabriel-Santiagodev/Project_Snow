# ==============================================================================
# PROJECT SNOW - OLED SERVICE
# ==============================================================================
# Version: 1.0
# Last Updated: August 2026
# Author: Ruben Gabriel Aguilar Santiago
# Purpose: Controls a 2.42" IIC OLED display connected to the Raspberry Pi via
#          I2C. Default state displays "SNOW". When a blind person is detected
#          (person_detected = True), the display changes to "PERSONA DETECTADA"
#          for a configurable duration, then returns to "SNOW" and resets the
#          shared state flag to allow the detection cycle to repeat.
# ==============================================================================

import time

try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1309
    from luma.core.render import canvas
    LUMA_AVAILABLE = True
except ImportError:
    LUMA_AVAILABLE = False

from src.core.base_service import BaseService


class OledService(BaseService):
    """
    Threaded service that drives a 2.42" I2C OLED display (SSD1309 controller).

    Reads the `person_detected` volatile flag from SharedState. When the flag
    is True, the display is updated to "PERSONA DETECTADA" for
    `display_duration_seconds`. After the wait period the display returns to its
    idle message "SNOW" and the flag is reset to False so the detection cycle
    can repeat.

    The waiting period uses `_stop_event.wait()` instead of a plain
    `time.sleep()` so the service shuts down immediately and gracefully even
    if the display is currently showing an alert.

    The service falls back to a fully simulated (log-only) mode when the
    `luma.oled` library is not available, which enables unit-testing and
    development on non-Raspberry Pi hardware.

    Parameters
    ----------
    shared_state : SharedState
        Central thread-safe data store.
    config : dict
        Configuration dictionary loaded from settings.yaml.
    """

    # Messages shown on the display
    _MSG_IDLE = "SNOW"
    _MSG_DETECTED = "PERSONA DETECTADA"

    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

        # 1. Read parameters from settings.yaml -- no hardcoded values
        oled_cfg = self.config.get("hardware", {}).get("oled", {})

        self._i2c_port = oled_cfg.get("i2c_port", 1)
        self._i2c_address = oled_cfg.get("i2c_address", 0x3C)
        self._display_duration = oled_cfg.get("display_duration_seconds", 5)

        # 2. Hardware initialization
        self._device = None
        if LUMA_AVAILABLE:
            try:
                serial = i2c(port=self._i2c_port, address=self._i2c_address)
                self._device = ssd1309(serial)
                self.logger.info(
                    f"OLED display initialized on I2C port {self._i2c_port}, "
                    f"address 0x{self._i2c_address:02X}."
                )
                # Draw the idle message immediately on start
                self._draw_message(self._MSG_IDLE)
            except Exception as e:
                self._device = None
                self.logger.error(
                    f"Failed to initialize OLED display: {e}"
                )
        else:
            self.logger.warning(
                "luma.oled not available. Running in simulated mode -- "
                "display actions will be logged only."
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
        2. If current time is within `display_duration_seconds` of last detection, show alert.
        3. If time expires, show idle message.
        4. Report health or error to the Watchdog on each iteration.
        """
        self.logger.info("Starting OLED service main loop...")
        
        is_on = False

        while not self._stop_event.is_set():
            try:
                # 1. Read the detection timestamp from SharedState
                last_detection_time = self.shared_state.get_volatile("last_person_detected_time")

                if last_detection_time > 0 and (time.time() - last_detection_time) <= self._display_duration:
                    if not is_on:
                        self.logger.info("Detection active. Updating OLED display.")
                        self._draw_message(self._MSG_DETECTED)
                        is_on = True
                else:
                    if is_on:
                        self.logger.info("Detection expired. Display returned to idle.")
                        self._draw_message(self._MSG_IDLE)
                        is_on = False

                # 3. Report healthy iteration to the Watchdog
                self.report_health()

                # 4. Prevent 100% CPU utilization
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Unexpected error in OLED service: {e}")
                self.report_error()
                time.sleep(1)

        # Graceful shutdown: clear the display before the thread exits
        self._shutdown_hardware()

    # --------------------------------------------------------------------------
    # DISPLAY HELPERS
    # --------------------------------------------------------------------------

    def _draw_message(self, message):
        """
        Renders a centered text message on the OLED display.

        In simulated mode (no hardware), the action is only logged.

        Parameters
        ----------
        message : str
            The text string to display.
        """
        if self._device is not None:
            try:
                with canvas(self._device) as draw:
                    # Use the default PIL bitmap font. A scalable font could be
                    # injected via config if larger text is needed in the future.
                    w, h = self._device.width, self._device.height
                    # Approximate bounding box for centering (default PIL font)
                    char_w, char_h = 6, 8  # Default PIL font glyph size (pixels)
                    text_w = len(message) * char_w
                    x = max((w - text_w) // 2, 0)
                    y = (h - char_h) // 2
                    draw.text((x, y), message, fill="white")
                self.logger.debug(f"Display updated: '{message}'")
            except Exception as e:
                self.logger.error(f"Hardware error updating OLED display: {e}")
                self.report_error()
        else:
            self.logger.info(f"[SIMULATED] DISPLAY: '{message}'")

    def _clear_display(self):
        """Blanks the OLED screen, or logs the action in simulated mode."""
        if self._device is not None:
            try:
                self._device.clear()
            except Exception as e:
                self.logger.error(f"Hardware error clearing OLED display: {e}")
        else:
            self.logger.info("[SIMULATED] DISPLAY CLEARED")

    def _shutdown_hardware(self):
        """Clears and releases OLED hardware resources when the thread stops."""
        self.logger.info("Releasing OLED hardware resources...")
        self._clear_display()
        if self._device is not None:
            try:
                self._device.cleanup()
            except Exception as e:
                self.logger.error(f"Error releasing OLED hardware resources: {e}")
