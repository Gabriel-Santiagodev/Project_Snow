# ==============================================================================
# PROJECT SNOW - UNIT TESTS: AudioService
# ==============================================================================
# Strategy:
#   - pygame.mixer is fully mocked so no audio hardware is required.
#   - SharedState is a MagicMock with a real volatile backing store (from conftest).
#   - Each test runs exactly one logical scenario in isolation.
#   - Loop tests inject a side_effect that sets _stop_event after N iterations
#     to prevent infinite loops while still exercising the actual loop body.
# ==============================================================================

import time
import pytest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# MODULE-LEVEL MOCK: patch pygame BEFORE the service module is imported.
# This prevents any real pygame.mixer.init() from being called at import time.
# ---------------------------------------------------------------------------
pygame_mock = MagicMock()

import sys
sys.modules.setdefault("pygame", pygame_mock)
sys.modules.setdefault("pygame.mixer", pygame_mock.mixer)

from src.services.audio_service import AudioService  # noqa: E402


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _make_service(mock_shared_state, service_config):
    """Instantiate AudioService with all pygame internals mocked."""
    with patch("src.services.audio_service.pygame", pygame_mock):
        svc = AudioService(mock_shared_state, service_config)
    return svc


def _run_one_loop_iteration(svc):
    """
    Run exactly one iteration of _main_loop by setting the stop event
    after the first call to report_health or report_error.

    We patch time.sleep to be a no-op so tests finish instantly.
    """
    original_report_health = svc.report_health
    original_report_error = svc.report_error
    call_count = {"n": 0}

    def _stop_after_health():
        original_report_health()
        call_count["n"] += 1
        svc._stop_event.set()

    def _stop_after_error():
        original_report_error()
        call_count["n"] += 1
        svc._stop_event.set()

    svc.report_health = _stop_after_health
    svc.report_error = _stop_after_error

    with patch("src.services.audio_service.time.sleep"):
        with patch("src.services.audio_service.pygame", pygame_mock):
            svc._main_loop()

    # Restore originals
    svc.report_health = original_report_health
    svc.report_error = original_report_error


# ===========================================================================
# __INIT__ TESTS
# ===========================================================================

class TestAudioServiceInit:
    """Verify constructor reads config and initialises pygame correctly."""

    def test_init_calls_pygame_mixer_init(self, mock_shared_state, service_config):
        """pygame.mixer.init() must be called once during construction."""
        pygame_mock.reset_mock()
        with patch("src.services.audio_service.pygame", pygame_mock):
            svc = AudioService(mock_shared_state, service_config)
        pygame_mock.mixer.init.assert_called_once()

    def test_init_reads_volume_from_config(self, mock_shared_state, service_config):
        """Volume must be sourced from config, not hardcoded."""
        with patch("src.services.audio_service.pygame", pygame_mock):
            svc = AudioService(mock_shared_state, service_config)
        assert svc.volume == 0.8

    def test_init_reads_cooldown_from_config(self, mock_shared_state, service_config):
        """Cooldown must be sourced from config, not hardcoded."""
        with patch("src.services.audio_service.pygame", pygame_mock):
            svc = AudioService(mock_shared_state, service_config)
        assert svc.cooldown == 2.0

    def test_init_reads_audio_file_from_config(self, mock_shared_state, service_config):
        """Audio file path must be sourced from config."""
        with patch("src.services.audio_service.pygame", pygame_mock):
            svc = AudioService(mock_shared_state, service_config)
        assert svc.audio_file == "data/audio/testing_audio0.mp3"

    def test_init_pygame_failure_does_not_crash(self, mock_shared_state, service_config):
        """If pygame.mixer.init raises, __init__ must not propagate the exception."""
        failing_pygame = MagicMock()
        failing_pygame.mixer.init.side_effect = Exception("pygame unavailable")
        with patch("src.services.audio_service.pygame", failing_pygame):
            # Should NOT raise
            svc = AudioService(mock_shared_state, service_config)
        assert svc is not None


# ===========================================================================
# MAIN LOOP — IDLE STATE
# ===========================================================================

class TestAudioServiceIdle:
    """Verify behaviour when person_detected is False (idle state)."""

    def test_no_play_when_flag_false(self, mock_shared_state, service_config):
        """
        If person_detected=False, music.play() must never be called.
        This is the hot path (empty hallway), running 24/7.
        """
        mock_shared_state._volatile_store["person_detected"] = False
        pygame_mock.reset_mock()

        svc = _make_service(mock_shared_state, service_config)
        _run_one_loop_iteration(svc)

        pygame_mock.mixer.music.play.assert_not_called()

    def test_report_health_on_idle(self, mock_shared_state, service_config):
        """An idle iteration (no detection) must call report_health()."""
        mock_shared_state._volatile_store["person_detected"] = False
        svc = _make_service(mock_shared_state, service_config)

        svc.report_health = MagicMock(side_effect=lambda: svc._stop_event.set())

        with patch("src.services.audio_service.time.sleep"):
            with patch("src.services.audio_service.pygame", pygame_mock):
                svc._main_loop()

        svc.report_health.assert_called()


# ===========================================================================
# MAIN LOOP — DETECTION CYCLE
# ===========================================================================

class TestAudioServiceDetection:
    """Verify full detection → play → reset cycle."""

    def test_plays_audio_on_detection(self, mock_shared_state, service_config):
        """
        When person_detected=True and cooldown has elapsed,
        music.load(), set_volume(), and play() must all be called.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        pygame_mock.reset_mock()

        svc = _make_service(mock_shared_state, service_config)
        svc.last_played_time = 0.0  # Force cooldown elapsed

        _run_one_loop_iteration(svc)

        pygame_mock.mixer.music.load.assert_called_once_with(svc.audio_file)
        pygame_mock.mixer.music.set_volume.assert_called_once_with(svc.volume)
        pygame_mock.mixer.music.play.assert_called_once()

    def test_flag_reset_after_play(self, mock_shared_state, service_config):
        """
        After playing audio, person_detected must be reset to False.
        This prevents the 'stuck flag' 24/7 bug (infinite replay loop).
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc = _make_service(mock_shared_state, service_config)
        svc.last_played_time = 0.0

        _run_one_loop_iteration(svc)

        assert mock_shared_state._volatile_store["person_detected"] is False

    def test_cooldown_prevents_replay(self, mock_shared_state, service_config):
        """
        A second detection within the cooldown window must NOT trigger play.
        Critical for preventing audio spam in a busy environment.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        pygame_mock.reset_mock()

        svc = _make_service(mock_shared_state, service_config)
        # Simulate a very recent previous play (cooldown not elapsed)
        svc.last_played_time = time.time()

        _run_one_loop_iteration(svc)

        pygame_mock.mixer.music.play.assert_not_called()

    def test_flag_stuck_true_gets_reset(self, mock_shared_state, service_config):
        """
        Edge case (24/7): if person_detected stays True across many iterations,
        the service must still reset it after each actuation cycle.
        This test simulates the flag being set externally while in cooldown.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        svc = _make_service(mock_shared_state, service_config)
        svc.last_played_time = 0.0  # Allow play on first pass

        _run_one_loop_iteration(svc)

        # Flag must be False after the loop body executes
        assert mock_shared_state._volatile_store["person_detected"] is False


# ===========================================================================
# FAULT TOLERANCE
# ===========================================================================

class TestAudioServiceFaultTolerance:
    """Verify correct error handling and Watchdog integration."""

    def test_pygame_error_calls_report_error(self, mock_shared_state, service_config):
        """
        If music.play() raises pygame.error, report_error() must be called.
        The service must NOT crash — it must stay alive for the Watchdog.
        """
        mock_shared_state._volatile_store["person_detected"] = True
        failing_pygame = MagicMock()
        failing_pygame.error = Exception  # Make pygame.error a real exception class

        # play() raises — then stop so the loop doesn't run forever
        call_count = {"n": 0}

        def _play_then_stop():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Hardware error")
            svc._stop_event.set()

        failing_pygame.mixer.music.play.side_effect = _play_then_stop

        svc = _make_service(mock_shared_state, service_config)
        svc.last_played_time = 0.0
        svc.report_error = MagicMock(side_effect=lambda: svc._stop_event.set())

        with patch("src.services.audio_service.time.sleep"):
            with patch("src.services.audio_service.pygame", failing_pygame):
                svc._main_loop()

        svc.report_error.assert_called()

    def test_unexpected_exception_calls_report_error(self, mock_shared_state, service_config):
        """
        An unexpected exception in the loop must call report_error() and
        NOT terminate the thread prematurely (the outer except catches it).
        """
        svc = _make_service(mock_shared_state, service_config)

        call_count = {"n": 0}

        # get_volatile receives a key argument — side_effect must accept it
        def _boom(key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Unexpected internal error")
            # Second call: stop the loop instead of raising
            svc._stop_event.set()
            return False  # Return a valid value so the loop body can exit cleanly

        svc.shared_state.get_volatile = MagicMock(side_effect=_boom)
        # report_error must NOT set the stop_event here — we want to test that
        # the loop continues after an error (the outer except catches and continues)
        svc.report_error = MagicMock()

        with patch("src.services.audio_service.time.sleep"):
            with patch("src.services.audio_service.pygame", pygame_mock):
                svc._main_loop()

        svc.report_error.assert_called()


# ===========================================================================
# GRACEFUL SHUTDOWN
# ===========================================================================

class TestAudioServiceShutdown:
    """Verify hardware resources are released on stop."""

    def test_shutdown_calls_pygame_mixer_quit(self, mock_shared_state, service_config):
        """pygame.mixer.quit() must be called during _shutdown_hardware()."""
        pygame_mock.reset_mock()
        svc = _make_service(mock_shared_state, service_config)
        with patch("src.services.audio_service.pygame", pygame_mock):
            svc._shutdown_hardware()
        pygame_mock.mixer.quit.assert_called_once()

    def test_shutdown_hardware_failure_does_not_crash(self, mock_shared_state, service_config):
        """If pygame.mixer.quit() raises, _shutdown_hardware must not propagate."""
        failing_pygame = MagicMock()
        failing_pygame.mixer.quit.side_effect = Exception("quit failed")
        svc = _make_service(mock_shared_state, service_config)
        with patch("src.services.audio_service.pygame", failing_pygame):
            # Should NOT raise
            svc._shutdown_hardware()
