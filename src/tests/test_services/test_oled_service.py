# ==============================================================================
# PROJECT SNOW - UNIT TESTS: OledService
# ==============================================================================
# Strategy:
#   - luma.core and luma.oled are injected into sys.modules as MagicMocks
#     BEFORE the service module is imported, preventing any real I2C activity.
#   - Tests cover both simulated mode (luma absent) and hardware mode (mocked).
#   - The canvas context manager is mocked to allow _draw_message() to succeed.
#   - _stop_event.wait is patched to be instant for cycle tests.
# ==============================================================================

import sys
import time
import pytest
from unittest.mock import MagicMock, patch, call, PropertyMock


# ---------------------------------------------------------------------------
# MODULE-LEVEL MOCK: inject luma stubs into sys.modules BEFORE import
# ---------------------------------------------------------------------------
_mock_i2c_class = MagicMock()
_mock_ssd1309_class = MagicMock()
_mock_canvas_class = MagicMock()

_luma_core_mock = MagicMock()
_luma_core_interface_mock = MagicMock()
_luma_core_render_mock = MagicMock()
_luma_oled_mock = MagicMock()
_luma_oled_device_mock = MagicMock()

_luma_core_interface_mock.serial.i2c = _mock_i2c_class
_luma_oled_device_mock.ssd1309 = _mock_ssd1309_class
_luma_core_render_mock.canvas = _mock_canvas_class

sys.modules.setdefault("luma", MagicMock())
sys.modules.setdefault("luma.core", _luma_core_mock)
sys.modules.setdefault("luma.core.interface", _luma_core_interface_mock)
sys.modules.setdefault("luma.core.interface.serial", _luma_core_interface_mock.serial)
sys.modules.setdefault("luma.core.render", _luma_core_render_mock)
sys.modules.setdefault("luma.oled", _luma_oled_mock)
sys.modules.setdefault("luma.oled.device", _luma_oled_device_mock)

# Now safe to import
import importlib
import src.services.oled_service as _oled_mod  # noqa: E402


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _make_service_luma_available(mock_shared_state, service_config):
    """
    Instantiate OledService with LUMA_AVAILABLE=True and a mocked device.
    The mock device has .width=128, .height=64 so centering math works.
    """
    mock_device_instance = MagicMock()
    mock_device_instance.width = 128
    mock_device_instance.height = 64

    _mock_ssd1309_class.reset_mock()
    _mock_ssd1309_class.return_value = mock_device_instance

    # Mock the canvas context manager
    mock_draw = MagicMock()
    _mock_canvas_class.return_value.__enter__ = MagicMock(return_value=mock_draw)
    _mock_canvas_class.return_value.__exit__ = MagicMock(return_value=False)

    original_luma = _oled_mod.LUMA_AVAILABLE
    _oled_mod.LUMA_AVAILABLE = True
    try:
        from src.services.oled_service import OledService
        svc = OledService(mock_shared_state, service_config)
    finally:
        _oled_mod.LUMA_AVAILABLE = original_luma

    return svc, mock_device_instance, mock_draw


def _make_service_luma_unavailable(mock_shared_state, service_config):
    """
    Instantiate OledService with LUMA_AVAILABLE=False (simulated mode).
    """
    original_luma = _oled_mod.LUMA_AVAILABLE
    _oled_mod.LUMA_AVAILABLE = False
    try:
        from src.services.oled_service import OledService
        svc = OledService(mock_shared_state, service_config)
    finally:
        _oled_mod.LUMA_AVAILABLE = original_luma

    return svc


def _run_one_loop_iteration(svc):
    """
    Drive exactly one pass through _main_loop. Stop after first health/error call.
    _stop_event.wait is patched to be instant.
    """
    def _stop_after():
        svc._stop_event.set()

    svc.report_health = MagicMock(side_effect=_stop_after)
    svc.report_error = MagicMock(side_effect=_stop_after)

    with patch("src.services.oled_service.time.sleep"):
        svc._stop_event.wait = MagicMock(return_value=False)
        svc._main_loop()


# ===========================================================================
# __INIT__ TESTS
# ===========================================================================

class TestOledServiceInit:
    """Verify constructor reads config and initialises display correctly."""

    def test_init_simulated_mode_when_luma_absent(
        self, mock_shared_state, service_config
    ):
        """
        When luma is not installed, _device must be None.
        Validates simulated mode runs on a developer machine.
        """
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)
        assert svc._device is None

    def test_init_reads_i2c_port_from_config(self, mock_shared_state, service_config):
        """I2C port must come from config (port=1), not hardcoded."""
        svc, _, _ = _make_service_luma_available(mock_shared_state, service_config)
        assert svc._i2c_port == 1

    def test_init_reads_i2c_address_from_config(
        self, mock_shared_state, service_config
    ):
        """I2C address must come from config (0x3C), not hardcoded."""
        svc, _, _ = _make_service_luma_available(mock_shared_state, service_config)
        assert svc._i2c_address == 0x3C

    def test_init_reads_display_duration_from_config(
        self, mock_shared_state, service_config
    ):
        """Display duration must come from config (5s), not hardcoded."""
        svc, _, _ = _make_service_luma_available(mock_shared_state, service_config)
        assert svc._display_duration == 5

    def test_init_draws_idle_message_on_start(self, mock_shared_state, service_config):
        """
        Upon successful hardware init, 'SNOW' must be drawn immediately.
        This ensures the display is not blank when the system starts up.
        """
        svc, device, draw = _make_service_luma_available(mock_shared_state, service_config)
        # canvas was used to draw something during __init__
        _mock_canvas_class.assert_called()

    def test_init_hardware_failure_sets_device_to_none(
        self, mock_shared_state, service_config
    ):
        """
        If ssd1309() raises (e.g. I2C bus error), _device must be None
        and the service must not crash.
        """
        _mock_ssd1309_class.side_effect = Exception("I2C bus error")
        original_luma = _oled_mod.LUMA_AVAILABLE
        _oled_mod.LUMA_AVAILABLE = True
        try:
            from src.services.oled_service import OledService
            svc = OledService(mock_shared_state, service_config)
        finally:
            _oled_mod.LUMA_AVAILABLE = original_luma
            _mock_ssd1309_class.side_effect = None

        assert svc._device is None


# ===========================================================================
# MAIN LOOP — IDLE STATE
# ===========================================================================

class TestOledServiceIdle:
    """Verify behaviour when person_detected is False."""

    def test_no_display_update_when_flag_false(
        self, mock_shared_state, service_config
    ):
        """
        In idle state, canvas must not be called for a 'PERSONA DETECTADA' draw.
        The display must remain on the idle 'SNOW' message.
        """
        mock_shared_state._volatile_store["person_detected"] = False
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)

        _mock_canvas_class.reset_mock()
        _run_one_loop_iteration(svc)

        # In simulated mode, canvas should not be touched
        _mock_canvas_class.assert_not_called()

    def test_report_health_on_idle(self, mock_shared_state, service_config):
        """An idle iteration must call report_health() — Watchdog requirement."""
        mock_shared_state._volatile_store["person_detected"] = False
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)

        health_called = {"v": False}

        def _mark():
            health_called["v"] = True
            svc._stop_event.set()

        svc.report_health = MagicMock(side_effect=_mark)

        with patch("src.services.oled_service.time.sleep"):
            svc._stop_event.wait = MagicMock(return_value=False)
            svc._main_loop()

        assert health_called["v"] is True


# ===========================================================================
# MAIN LOOP — DETECTION CYCLE
# ===========================================================================

class TestOledServiceDetection:
    """Verify full detection → display alert → return to idle → flag reset."""

    def test_full_detection_cycle_simulated(self, mock_shared_state, service_config):
        """
        In simulated mode:
          1. Cycle must complete without errors
          2. person_detected must be reset to False
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)

        _run_one_loop_iteration(svc)

        assert mock_shared_state._volatile_store["person_detected"] is False

    def test_draw_detected_message_called_on_detection(
        self, mock_shared_state, service_config
    ):
        """
        When person_detected=True, _draw_message must be called with
        'PERSONA DETECTADA' followed by 'SNOW' (return to idle).
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)

        svc._draw_message = MagicMock()
        _run_one_loop_iteration(svc)

        calls = svc._draw_message.call_args_list
        messages = [c.args[0] for c in calls]
        assert "PERSONA DETECTADA" in messages
        assert "SNOW" in messages
        # SNOW must come AFTER PERSONA DETECTADA
        assert messages.index("SNOW") > messages.index("PERSONA DETECTADA")

    def test_flag_reset_after_cycle(self, mock_shared_state, service_config):
        """
        After the display cycle, person_detected must be False.
        Edge case (24/7): prevents infinite display loop if flag gets stuck.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)
        _run_one_loop_iteration(svc)
        assert mock_shared_state._volatile_store["person_detected"] is False


# ===========================================================================
# DRAW MESSAGE TESTS
# ===========================================================================

class TestOledServiceDrawMessage:
    """Unit tests for the _draw_message() helper."""

    def test_draw_message_simulated_mode_does_not_crash(
        self, mock_shared_state, service_config
    ):
        """In simulated mode, _draw_message() must only log — never crash."""
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)
        # Should NOT raise
        svc._draw_message("TEST")

    def test_draw_message_hardware_error_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """
        If the canvas context manager raises during draw,
        report_error() must be called and the exception must not propagate.
        """
        svc, device, _ = _make_service_luma_available(mock_shared_state, service_config)
        # Force canvas to raise
        _mock_canvas_class.return_value.__enter__.side_effect = Exception("I2C write fail")

        svc.report_error = MagicMock()
        svc._draw_message("PERSONA DETECTADA")

        svc.report_error.assert_called_once()
        # Restore
        _mock_canvas_class.return_value.__enter__.side_effect = None


# ===========================================================================
# FAULT TOLERANCE
# ===========================================================================

class TestOledServiceFaultTolerance:
    """Verify unexpected errors are caught and reported to the Watchdog."""

    def test_unexpected_exception_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """
        An arbitrary exception in the loop body must call report_error()
        and NOT terminate the thread prematurely.
        """
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)

        call_count = {"n": 0}

        def _boom(key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Unexpected error")
            svc._stop_event.set()
            return False

        svc.shared_state.get_volatile = MagicMock(side_effect=_boom)
        svc.report_error = MagicMock()

        with patch("src.services.oled_service.time.sleep"):
            svc._stop_event.wait = MagicMock(return_value=False)
            svc._main_loop()

        svc.report_error.assert_called()


# ===========================================================================
# GRACEFUL SHUTDOWN
# ===========================================================================

class TestOledServiceShutdown:
    """Verify display is cleared and resources released on stop."""

    def test_shutdown_clears_display_hardware(self, mock_shared_state, service_config):
        """_shutdown_hardware() must call device.clear() to blank the screen."""
        svc, device, _ = _make_service_luma_available(mock_shared_state, service_config)
        svc._shutdown_hardware()
        device.clear.assert_called()

    def test_shutdown_calls_device_cleanup(self, mock_shared_state, service_config):
        """_shutdown_hardware() must call device.cleanup() to release I2C."""
        svc, device, _ = _make_service_luma_available(mock_shared_state, service_config)
        svc._shutdown_hardware()
        device.cleanup.assert_called_once()

    def test_shutdown_in_simulated_mode_does_not_crash(
        self, mock_shared_state, service_config
    ):
        """_shutdown_hardware() in simulated mode must not raise."""
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)
        # Should NOT raise
        svc._shutdown_hardware()

    def test_stop_during_display_wait_exits_immediately(
        self, mock_shared_state, service_config
    ):
        """
        Calling stop() during the display wait (display_duration_seconds)
        must cause the loop to exit without waiting the full duration.
        Validates the use of _stop_event.wait() over time.sleep().
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc = _make_service_luma_unavailable(mock_shared_state, service_config)

        def _stop_mid_wait(timeout=None):
            svc._stop_event.set()
            return True

        svc._stop_event.wait = _stop_mid_wait

        start = time.monotonic()
        with patch("src.services.oled_service.time.sleep"):
            svc._main_loop()
        elapsed = time.monotonic() - start

        # Must finish in well under the 5s display_duration
        assert elapsed < 2.0
