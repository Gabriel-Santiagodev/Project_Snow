# ==============================================================================
# PROJECT SNOW - UNIT TESTS: cameras_service (CameraService)
# ==============================================================================
# Strategy:
#   - cv2 and numpy are fully mocked via sys.modules BEFORE any import.
#     This prevents the Python 3.14 / numpy experimental build from crashing.
#   - Frames are MagicMock objects; cv2.cvtColor/absdiff are mocked to
#     return controllable MagicMocks, and np.mean is mocked to return a
#     configurable float so movement detection can be driven precisely.
#   - time.time() is patched to control state machine timeout logic
#     deterministically, eliminating any real sleep or timing dependency.
# ==============================================================================

import sys
import queue
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# MODULE-LEVEL MOCK: stub out numpy and cv2 before any service import
# ---------------------------------------------------------------------------

_np_mock = MagicMock()
_cv2_mock = MagicMock()

# np.mean will be configured per-test to return floats
_np_mock.mean.return_value = 0.0

# cv2 constants needed by the service
_cv2_mock.COLOR_BGR2GRAY = 6
_cv2_mock.FONT_HERSHEY_SIMPLEX = 0

# cv2.absdiff returns a MagicMock frame (np.mean called on it later)
_cv2_mock.absdiff.return_value = MagicMock()

# cv2.cvtColor returns a MagicMock gray frame
_cv2_mock.cvtColor.return_value = MagicMock()

# VideoCapture mock factory — configured per-test
_mock_cap1 = MagicMock()
_mock_cap2 = MagicMock()

def _cv2_capture_factory(src):
    return _mock_cap1 if src == 0 else _mock_cap2

_cv2_mock.VideoCapture.side_effect = _cv2_capture_factory

sys.modules.setdefault("numpy", _np_mock)
sys.modules.setdefault("cv2", _cv2_mock)

# Also stub out the camera_service's direct `import numpy as np` and `import cv2`
# by ensuring the module is loaded with our stubs
import src.services.camera_service as _cam_mod  # noqa: E402
_cam_mod.cv2 = _cv2_mock
_cam_mod.np = _np_mock

from src.services.camera_service import cameras_service  # noqa: E402


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _make_service(mock_shared_state, service_config):
    """Build a cameras_service instance with both VideoCaptures mocked."""
    _mock_cap1.reset_mock()
    _mock_cap2.reset_mock()

    # Default: both cameras return a successful MagicMock frame
    _mock_cap1.read.return_value = (True, MagicMock())
    _mock_cap2.read.return_value = (True, MagicMock())

    # Patch VideoCapture factory
    original = _cam_mod.cv2.VideoCapture.side_effect
    _cam_mod.cv2.VideoCapture.side_effect = _cv2_capture_factory

    svc = cameras_service(mock_shared_state, service_config)
    return svc


def _run_one_iteration(svc, np_mean_value=0.0):
    """
    Run exactly one iteration of _main_loop.
    np.mean is configured to return np_mean_value (controls movement detection).
    """
    _np_mock.mean.return_value = np_mean_value

    def _stop():
        svc._stop_event.set()

    svc.report_health = MagicMock(side_effect=_stop)
    svc.report_error = MagicMock(side_effect=_stop)

    with patch.object(_cam_mod, "time") as mock_time:
        mock_time.time.return_value = 1000.0
        mock_time.sleep.return_value = None
        svc._main_loop()


def _run_one_iteration_with_time(svc, fake_time=1000.0, np_mean_value=0.0):
    """
    Like _run_one_iteration but with a configurable fake_time for state machine control.
    """
    _np_mock.mean.return_value = np_mean_value

    def _stop():
        svc._stop_event.set()

    svc.report_health = MagicMock(side_effect=_stop)
    svc.report_error = MagicMock(side_effect=_stop)

    with patch.object(_cam_mod, "time") as mock_time:
        mock_time.time.return_value = fake_time
        mock_time.sleep.return_value = None
        svc._main_loop()


# ===========================================================================
# __INIT__ TESTS
# ===========================================================================

class TestCameraServiceInit:
    """Verify constructor reads config and opens both cameras."""

    def test_init_opens_camera_sources_from_config(
        self, mock_shared_state, service_config
    ):
        """VideoCapture must be called for source 0 and source 1."""
        captured_sources = []

        def _capture_src(src):
            captured_sources.append(src)
            return MagicMock()

        original = _cam_mod.cv2.VideoCapture.side_effect
        _cam_mod.cv2.VideoCapture.side_effect = _capture_src
        try:
            svc = cameras_service(mock_shared_state, service_config)
        finally:
            _cam_mod.cv2.VideoCapture.side_effect = original

        assert 0 in captured_sources
        assert 1 in captured_sources

    def test_init_reads_movement_threshold_from_config(
        self, mock_shared_state, service_config
    ):
        """movement_threshold must come from config, not hardcoded."""
        svc = _make_service(mock_shared_state, service_config)
        assert svc.movement_threshold == 5.0

    def test_init_reads_sequence_timeout_from_config(
        self, mock_shared_state, service_config
    ):
        """sequence_timeout must come from config, not hardcoded."""
        svc = _make_service(mock_shared_state, service_config)
        assert svc.sequence_timeout == 10.0

    def test_init_starts_in_idle_state(self, mock_shared_state, service_config):
        """State machine must start in IDLE (state=0)."""
        svc = _make_service(mock_shared_state, service_config)
        assert svc.state == 0

    def test_init_grabs_frame_queue_from_shared_state(
        self, mock_shared_state, service_config
    ):
        """frame_queue must be retrieved from SharedState, not created locally."""
        svc = _make_service(mock_shared_state, service_config)
        call_args = [c.args[0] for c in mock_shared_state.get_volatile.call_args_list]
        assert "camera_frame_queue" in call_args


# ===========================================================================
# CAMERA READ FAILURE HANDLING
# ===========================================================================

class TestCameraServiceReadFailures:
    """Validate error handling when cameras fail to deliver frames."""

    def test_both_cameras_fail_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """If both cameras return ret=False, report_error() must be called."""
        svc = _make_service(mock_shared_state, service_config)
        _mock_cap1.read.return_value = (False, None)
        _mock_cap2.read.return_value = (False, None)

        _run_one_iteration(svc)

        svc.report_error.assert_called()

    def test_camera1_fails_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """If only camera 1 fails, report_error() must be called."""
        svc = _make_service(mock_shared_state, service_config)
        _mock_cap1.read.return_value = (False, None)
        _mock_cap2.read.return_value = (True, MagicMock())

        _run_one_iteration(svc)

        svc.report_error.assert_called()

    def test_camera2_fails_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """If only camera 2 fails, report_error() must be called."""
        svc = _make_service(mock_shared_state, service_config)
        _mock_cap1.read.return_value = (True, MagicMock())
        _mock_cap2.read.return_value = (False, None)

        _run_one_iteration(svc)

        svc.report_error.assert_called()

    def test_constant_failure_does_not_crash_service(
        self, mock_shared_state, service_config
    ):
        """
        Edge case (24/7): cameras continuously failing must not crash the thread.
        The service must loop, report_error, sleep, and remain alive.
        """
        svc = _make_service(mock_shared_state, service_config)
        _mock_cap1.read.return_value = (False, None)
        _mock_cap2.read.return_value = (False, None)

        call_count = {"n": 0}

        def _count_and_stop():
            call_count["n"] += 1
            if call_count["n"] >= 3:
                svc._stop_event.set()

        svc.report_error = MagicMock(side_effect=_count_and_stop)
        svc.report_health = MagicMock(side_effect=lambda: svc._stop_event.set())

        with patch.object(_cam_mod, "time") as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep.return_value = None
            svc._main_loop()

        assert call_count["n"] >= 3  # Service ran multiple failure cycles


# ===========================================================================
# STATE MACHINE TESTS
# ===========================================================================

class TestCameraServiceStateMachine:
    """
    Verify the 3-state sequence detection machine:
      IDLE (0) -> C1_ACTIVE (1) -> WAITING_FOR_C2 (2) -> IDLE (0)
    """

    def test_idle_no_movement_stays_idle(self, mock_shared_state, service_config):
        """
        IDLE + np.mean below threshold (no movement) → state stays 0.
        Dominant case: the hallway is empty most of the time.
        """
        svc = _make_service(mock_shared_state, service_config)
        # last_frame must not be None for diff to be computed
        svc.last_c1_frame = MagicMock()
        svc.last_c2_frame = MagicMock()

        # np.mean returns 0 → no movement
        _run_one_iteration(svc, np_mean_value=0.0)

        assert svc.state == 0

    def test_idle_c1_movement_transitions_to_state_1(
        self, mock_shared_state, service_config
    ):
        """
        IDLE + np.mean > movement_threshold (5.0) for C1 → state transitions to 1.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc.last_c1_frame = MagicMock()  # Prime last frame
        svc.last_c2_frame = None

        # np.mean = 10 → c1_movement = True (10 > 5.0 threshold)
        _run_one_iteration(svc, np_mean_value=10.0)

        assert svc.state == 1

    def test_c1_active_person_leaves_transitions_to_state_2(
        self, mock_shared_state, service_config
    ):
        """
        C1_ACTIVE + person has been gone from C1 for >1s → transitions to state 2.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc.state = 1
        svc.last_state_change = 1000.0
        # Person left C1 more than 1s ago
        svc.last_c1_movement = 998.5  # current_time(1000) - 998.5 = 1.5 > 1.0

        # No movement detected (np.mean=0) — confirms person left
        _run_one_iteration_with_time(svc, fake_time=1000.0, np_mean_value=0.0)

        assert svc.state == 2

    def test_c1_active_timeout_resets_to_idle(
        self, mock_shared_state, service_config
    ):
        """
        If person stays in C1 longer than sequence_timeout (10s), reset to IDLE.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc.state = 1
        # last_state_change 15s ago → current_time - last_state_change > 10
        svc.last_state_change = 985.0
        # Person still visible (recent movement) → won't trigger 'person left' branch
        svc.last_c1_movement = 999.5

        # np.mean > threshold so c1_movement=True (person still in C1)
        _run_one_iteration_with_time(svc, fake_time=1000.0, np_mean_value=10.0)

        assert svc.state == 0

    def test_complete_sequence_puts_frame_in_queue(
        self, mock_shared_state, service_config
    ):
        """
        Full sequence completion (state=2, C2 movement detected) must
        put a frame into the camera_frame_queue for YoloService.
        """
        frame_q = queue.Queue(maxsize=1)
        mock_shared_state._volatile_store["camera_frame_queue"] = frame_q

        svc = _make_service(mock_shared_state, service_config)
        svc.frame_queue = frame_q
        svc.state = 2
        svc.last_state_change = 999.0
        svc.last_c2_frame = MagicMock()  # Prime last frame

        # np.mean > threshold → c2_movement = True
        _run_one_iteration_with_time(svc, fake_time=1000.0, np_mean_value=10.0)

        assert not frame_q.empty()

    def test_complete_sequence_resets_state_to_idle(
        self, mock_shared_state, service_config
    ):
        """After a successful C1→C2 sequence, state must return to IDLE (0)."""
        frame_q = queue.Queue(maxsize=1)
        mock_shared_state._volatile_store["camera_frame_queue"] = frame_q

        svc = _make_service(mock_shared_state, service_config)
        svc.frame_queue = frame_q
        svc.state = 2
        svc.last_state_change = 999.0
        svc.last_c2_frame = MagicMock()

        _run_one_iteration_with_time(svc, fake_time=1000.0, np_mean_value=10.0)

        assert svc.state == 0

    def test_waiting_c2_timeout_resets_to_idle(
        self, mock_shared_state, service_config
    ):
        """
        In WAITING_FOR_C2 (state=2), if C2 never moves within sequence_timeout,
        state must reset to IDLE (0). Person went through C1 but never reached C2.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc.state = 2
        # last_state_change 15s ago → timeout exceeded (10s)
        svc.last_state_change = 985.0

        # No C2 movement (np.mean=0)
        _run_one_iteration_with_time(svc, fake_time=1000.0, np_mean_value=0.0)

        assert svc.state == 0

    def test_queue_full_drops_old_frame_on_new_detection(
        self, mock_shared_state, service_config
    ):
        """
        If the frame_queue is already full when a new detection completes,
        the old frame must be discarded and the new frame inserted.
        Prevents YOLO from processing stale frames in a congested pipeline.
        """
        frame_q = queue.Queue(maxsize=1)
        sentinel_old = object()
        frame_q.put_nowait(sentinel_old)  # Pre-fill the queue

        mock_shared_state._volatile_store["camera_frame_queue"] = frame_q

        svc = _make_service(mock_shared_state, service_config)
        svc.frame_queue = frame_q
        svc.state = 2
        svc.last_state_change = 999.0
        svc.last_c2_frame = MagicMock()

        _run_one_iteration_with_time(svc, fake_time=1000.0, np_mean_value=10.0)

        result = frame_q.get_nowait()
        # The item in the queue must NOT be the old sentinel
        assert result is not sentinel_old


# ===========================================================================
# HEALTH REPORTING
# ===========================================================================

class TestCameraServiceHealth:
    """Verify Watchdog integration on successful cycles."""

    def test_report_health_on_successful_cycle(
        self, mock_shared_state, service_config
    ):
        """A fully successful iteration must call report_health()."""
        svc = _make_service(mock_shared_state, service_config)
        _run_one_iteration(svc, np_mean_value=0.0)

        svc.report_health.assert_called()


# ===========================================================================
# GRACEFUL SHUTDOWN
# ===========================================================================

class TestCameraServiceShutdown:
    """Verify cameras are released when the service stops."""

    def test_shutdown_releases_both_cameras(
        self, mock_shared_state, service_config
    ):
        """
        When the service stops, both VideoCapture objects must have .release()
        called. Failing to do so leaks OS camera handles indefinitely on the Pi.
        """
        svc = _make_service(mock_shared_state, service_config)
        # Pre-set stop so the loop exits immediately on first iteration
        svc._stop_event.set()

        with patch.object(_cam_mod, "time") as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep.return_value = None
            svc._main_loop()

        svc.camera_uno.release.assert_called_once()
        svc.camera_dos.release.assert_called_once()
