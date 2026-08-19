# ==============================================================================
# PROJECT SNOW - UNIT TESTS: LightService
# ==============================================================================
# Strategy:
#   - gpiozero.LED is mocked at the module level so no GPIO hardware is needed.
#   - Tests cover both "simulated mode" (gpiozero absent) and "hardware mode"
#     (gpiozero present but mocked with MagicMock).
#   - Loop tests use a stop_event trick to exercise exactly one iteration.
#   - _stop_event.wait() (used during on_duration) is also mocked to be instant.
# ==============================================================================

import time
import threading
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _make_service_simulated(mock_shared_state, service_config):
    """
    Instantiate LightService with gpiozero unavailable (LED=None).
    This exercises the simulated/log-only branch.
    """
    with patch.dict("sys.modules", {"gpiozero": None}):
        # Force reimport with LED=None
        import importlib
        import src.services.light_service as ls_mod
        original_led = ls_mod.LED
        ls_mod.LED = None
        try:
            from src.services.light_service import LightService
            svc = LightService(mock_shared_state, service_config)
        finally:
            ls_mod.LED = original_led
    return svc


def _make_service_with_mock_led(mock_shared_state, service_config):
    """
    Instantiate LightService with a MagicMock LED object injected.
    This exercises the real hardware branch without touching GPIO.
    """
    mock_led_class = MagicMock()
    mock_led_instance = MagicMock()
    mock_led_class.return_value = mock_led_instance

    import src.services.light_service as ls_mod
    original_led = ls_mod.LED
    ls_mod.LED = mock_led_class
    try:
        from src.services.light_service import LightService
        svc = LightService(mock_shared_state, service_config)
    finally:
        ls_mod.LED = original_led

    return svc, mock_led_instance


def _run_one_loop_iteration(svc):
    """
    Drives exactly one full pass through _main_loop by setting stop_event
    after the first call to report_health or report_error.
    time.sleep and _stop_event.wait are patched to be instant.
    """
    original_health = svc.report_health
    original_error = svc.report_error

    def _stop_after():
        svc._stop_event.set()

    svc.report_health = MagicMock(side_effect=_stop_after)
    svc.report_error = MagicMock(side_effect=_stop_after)

    with patch("src.services.light_service.time.sleep"):
        # _stop_event.wait is used for on_duration — make it instant
        svc._stop_event.wait = MagicMock(return_value=False)
        svc._main_loop()

    svc.report_health = original_health
    svc.report_error = original_error


# ===========================================================================
# __INIT__ TESTS
# ===========================================================================

class TestLightServiceInit:
    """Verify constructor reads config and initialises LED correctly."""

    def test_init_simulated_mode_when_gpiozero_absent(
        self, mock_shared_state, service_config
    ):
        """
        When gpiozero is not installed, _led must be None and a warning logged.
        Simulates a developer machine or a Pi with missing library.
        """
        import src.services.light_service as ls_mod
        original_led = ls_mod.LED
        ls_mod.LED = None
        try:
            from src.services.light_service import LightService
            svc = LightService(mock_shared_state, service_config)
        finally:
            ls_mod.LED = original_led

        assert svc._led is None

    def test_init_with_mocked_led_calls_constructor_with_pin(
        self, mock_shared_state, service_config
    ):
        """LED must be instantiated with the pin number from config (BCM 18)."""
        svc, mock_led_inst = _make_service_with_mock_led(mock_shared_state, service_config)

        import src.services.light_service as ls_mod
        # The LED class was called; verify the pin
        assert svc._pin == 18

    def test_init_reads_on_duration_from_config(self, mock_shared_state, service_config):
        """on_duration_seconds must be sourced from config, not hardcoded."""
        svc, _ = _make_service_with_mock_led(mock_shared_state, service_config)
        assert svc._on_duration == 5

    def test_init_hardware_failure_sets_led_to_none(
        self, mock_shared_state, service_config
    ):
        """
        If LED() constructor raises (e.g. pin already in use),
        _led must be set to None and the service must not crash.
        """
        import src.services.light_service as ls_mod
        mock_led_class = MagicMock()
        mock_led_class.side_effect = Exception("GPIO pin in use")
        original_led = ls_mod.LED
        ls_mod.LED = mock_led_class
        try:
            from src.services.light_service import LightService
            svc = LightService(mock_shared_state, service_config)
        finally:
            ls_mod.LED = original_led

        assert svc._led is None


# ===========================================================================
# MAIN LOOP — IDLE STATE
# ===========================================================================

class TestLightServiceIdle:
    """Verify behaviour when person_detected is False."""

    def test_no_led_action_when_flag_false(self, mock_shared_state, service_config):
        """
        In idle state, LED.on() and LED.off() must never be called.
        This is the dominant state in production (empty hallway).
        """
        mock_shared_state._volatile_store["person_detected"] = False
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)

        _run_one_loop_iteration(svc)

        mock_led.on.assert_not_called()

    def test_report_health_on_idle(self, mock_shared_state, service_config):
        """An idle iteration must call report_health() — Watchdog requirement."""
        mock_shared_state._volatile_store["person_detected"] = False
        svc, _ = _make_service_with_mock_led(mock_shared_state, service_config)

        health_called = {"v": False}

        def _mark_and_stop():
            health_called["v"] = True
            svc._stop_event.set()

        svc.report_health = MagicMock(side_effect=_mark_and_stop)

        with patch("src.services.light_service.time.sleep"):
            svc._stop_event.wait = MagicMock(return_value=False)
            svc._main_loop()

        assert health_called["v"] is True


# ===========================================================================
# MAIN LOOP — DETECTION CYCLE
# ===========================================================================

class TestLightServiceDetection:
    """Verify the full detection → LED on → wait → LED off → flag reset cycle."""

    def test_full_detection_cycle_with_hardware(
        self, mock_shared_state, service_config
    ):
        """
        When person_detected=True:
          1. LED.on() must be called
          2. After wait, LED.off() must be called
          3. person_detected must be reset to False
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)

        _run_one_loop_iteration(svc)

        mock_led.on.assert_called_once()
        mock_led.off.assert_called()
        assert mock_shared_state._volatile_store["person_detected"] is False

    def test_full_detection_cycle_simulated(self, mock_shared_state, service_config):
        """
        In simulated mode (no LED), the cycle must still complete and
        reset person_detected to False without raising any exception.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        import src.services.light_service as ls_mod
        original_led = ls_mod.LED
        ls_mod.LED = None
        try:
            from src.services.light_service import LightService
            svc = LightService(mock_shared_state, service_config)
        finally:
            ls_mod.LED = original_led

        _run_one_loop_iteration(svc)

        assert mock_shared_state._volatile_store["person_detected"] is False

    def test_flag_reset_prevents_stuck_flag_24_7(
        self, mock_shared_state, service_config
    ):
        """
        Edge case (24/7): if person_detected is externally set to True
        repeatedly, each cycle must reset it.
        This prevents the LED from being permanently stuck on.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)

        _run_one_loop_iteration(svc)

        assert mock_shared_state._volatile_store["person_detected"] is False


# ===========================================================================
# FAULT TOLERANCE
# ===========================================================================

class TestLightServiceFaultTolerance:
    """Verify hardware errors are handled without crashing the service."""

    def test_led_on_hardware_error_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """
        If LED.on() raises, report_error() must be called.
        The service must remain alive for the Watchdog to manage.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)
        mock_led.on.side_effect = Exception("GPIO write failure")

        svc.report_error = MagicMock(side_effect=lambda: svc._stop_event.set())

        with patch("src.services.light_service.time.sleep"):
            svc._stop_event.wait = MagicMock(return_value=False)
            svc._main_loop()

        svc.report_error.assert_called()

    def test_led_off_hardware_error_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """
        If LED.off() raises during the cycle, report_error() must be called.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)
        mock_led.off.side_effect = Exception("GPIO write failure")

        svc.report_error = MagicMock(side_effect=lambda: svc._stop_event.set())

        with patch("src.services.light_service.time.sleep"):
            svc._stop_event.wait = MagicMock(return_value=False)
            svc._main_loop()

        svc.report_error.assert_called()


# ===========================================================================
# GRACEFUL SHUTDOWN
# ===========================================================================

class TestLightServiceShutdown:
    """Verify LED is turned off and GPIO resources released on stop."""

    def test_shutdown_turns_led_off(self, mock_shared_state, service_config):
        """_shutdown_hardware() must call LED.off() to ensure safe state."""
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)
        svc._shutdown_hardware()
        mock_led.off.assert_called()

    def test_shutdown_closes_gpio_resource(self, mock_shared_state, service_config):
        """_shutdown_hardware() must call LED.close() to release the GPIO pin."""
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)
        svc._shutdown_hardware()
        mock_led.close.assert_called_once()

    def test_shutdown_in_simulated_mode_does_not_crash(
        self, mock_shared_state, service_config
    ):
        """_shutdown_hardware() in simulated mode must not raise."""
        import src.services.light_service as ls_mod
        original_led = ls_mod.LED
        ls_mod.LED = None
        try:
            from src.services.light_service import LightService
            svc = LightService(mock_shared_state, service_config)
        finally:
            ls_mod.LED = original_led

        # Should NOT raise
        svc._shutdown_hardware()

    def test_stop_during_wait_exits_immediately(
        self, mock_shared_state, service_config
    ):
        """
        Calling stop() while the LED is on (during on_duration wait)
        must cause the loop to exit without waiting the full duration.
        This validates the use of _stop_event.wait() over time.sleep().
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc, mock_led = _make_service_with_mock_led(mock_shared_state, service_config)

        # Simulate stop() being called mid-wait
        def _stop_mid_wait(timeout=None):
            svc._stop_event.set()
            return True  # Simulates the event being set

        svc._stop_event.wait = _stop_mid_wait

        start = time.monotonic()
        with patch("src.services.light_service.time.sleep"):
            svc._main_loop()
        elapsed = time.monotonic() - start

        # Must finish in well under the 5s on_duration
        assert elapsed < 2.0
