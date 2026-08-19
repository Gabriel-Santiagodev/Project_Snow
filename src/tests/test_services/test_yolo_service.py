# ==============================================================================
# PROJECT SNOW - UNIT TESTS: YoloService
# ==============================================================================
# Strategy:
#   - ultralytics.YOLO is patched in sys.modules before import so no model
#     file or Hailo hardware is needed.
#   - A mock YOLO model returns configurable Results objects that mimic the
#     real ultralytics Results API (results[0].boxes[i].conf[0]).
#   - The frame_queue (from SharedState) is a real queue.Queue so queue
#     mechanics (Empty, timeout) are exercised for real.
#   - person_detected is backed by the mock_shared_state volatile store.
# ==============================================================================

import sys
import time
import queue
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# MODULE-LEVEL MOCK: patch ultralytics before any import
# ---------------------------------------------------------------------------
_mock_yolo_class = MagicMock()
_ultralytics_mock = MagicMock()
_ultralytics_mock.YOLO = _mock_yolo_class

sys.modules.setdefault("ultralytics", _ultralytics_mock)

from src.services.yolo_service import YoloService  # noqa: E402


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _make_results(confidences):
    """
    Build a mock ultralytics Results object with the given confidence values.

    confidences: list of float  — one per detected bounding box.
                 Empty list    — no boxes (nothing detected).
    """
    mock_boxes = []
    for conf in confidences:
        box = MagicMock()
        box.conf = [conf]
        mock_boxes.append(box)

    mock_result = MagicMock()
    mock_result.boxes = mock_boxes

    return [mock_result]  # ultralytics returns a list


def _make_service(mock_shared_state, service_config):
    """Instantiate YoloService with a fresh mock YOLO model."""
    _mock_yolo_class.reset_mock()
    mock_model_instance = MagicMock()
    _mock_yolo_class.return_value = mock_model_instance

    with patch("src.services.yolo_service.YOLO", _mock_yolo_class):
        svc = YoloService(mock_shared_state, service_config)

    svc._mock_model = mock_model_instance
    return svc


def _run_with_frame(svc, frame, expected_stop_after="health"):
    """
    Put frame into the queue and run one iteration of _main_loop.
    Stops after the first report_health or report_error call.
    """
    svc.frame_queue.put_nowait(frame)

    def _stop():
        svc._stop_event.set()

    svc.report_health = MagicMock(side_effect=_stop)
    svc.report_error = MagicMock(side_effect=_stop)

    with patch("src.services.yolo_service.time.sleep"):
        svc._main_loop()


def _run_empty_queue(svc):
    """
    Run one iteration with an empty queue (simulates idle / no traffic).
    """
    def _stop():
        svc._stop_event.set()

    svc.report_health = MagicMock(side_effect=_stop)
    svc.report_error = MagicMock(side_effect=_stop)

    with patch("src.services.yolo_service.time.sleep"):
        svc._main_loop()


# ===========================================================================
# __INIT__ TESTS
# ===========================================================================

class TestYoloServiceInit:
    """Verify constructor reads config and loads the model correctly."""

    def test_init_calls_yolo_with_model_path(
        self, mock_shared_state, service_config
    ):
        """YOLO() must be called with the model_path from config."""
        _mock_yolo_class.reset_mock()
        mock_model = MagicMock()
        _mock_yolo_class.return_value = mock_model

        with patch("src.services.yolo_service.YOLO", _mock_yolo_class):
            svc = YoloService(mock_shared_state, service_config)

        _mock_yolo_class.assert_called_once_with("data/models/best.pt")

    def test_init_reads_confidence_threshold_from_config(
        self, mock_shared_state, service_config
    ):
        """conf_threshold must be sourced from config (0.85), not hardcoded."""
        svc = _make_service(mock_shared_state, service_config)
        assert svc.conf_threshold == 0.85

    def test_init_grabs_frame_queue_from_shared_state(
        self, mock_shared_state, service_config
    ):
        """frame_queue must be retrieved from SharedState volatile store."""
        svc = _make_service(mock_shared_state, service_config)
        call_args = [c.args[0] for c in mock_shared_state.get_volatile.call_args_list]
        assert "camera_frame_queue" in call_args


# ===========================================================================
# DETECTION LOGIC
# ===========================================================================

class TestYoloServiceDetection:
    """Verify correct inference and person_detected flag management."""

    def test_detection_above_threshold_sets_flag_true(
        self, mock_shared_state, service_config
    ):
        """
        When any bounding box has confidence >= 0.85 (from config),
        person_detected must be set to True in SharedState.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.return_value = _make_results([0.91])

        dummy_frame = MagicMock()
        _run_with_frame(svc, dummy_frame)

        assert mock_shared_state._volatile_store["person_detected"] is True

    def test_detection_below_threshold_does_not_set_flag(
        self, mock_shared_state, service_config
    ):
        """
        When all boxes are below the threshold, person_detected must stay False.
        This prevents false positives from low-confidence detections.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.return_value = _make_results([0.50, 0.72])

        mock_shared_state._volatile_store["person_detected"] = False
        dummy_frame = MagicMock()
        _run_with_frame(svc, dummy_frame)

        assert mock_shared_state._volatile_store["person_detected"] is False

    def test_detection_at_exact_threshold_sets_flag(
        self, mock_shared_state, service_config
    ):
        """
        Edge case: confidence exactly equal to threshold (0.85) must trigger
        detection (>= is the condition, boundary must be inclusive).
        """
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.return_value = _make_results([0.85])

        dummy_frame = MagicMock()
        _run_with_frame(svc, dummy_frame)

        assert mock_shared_state._volatile_store["person_detected"] is True

    def test_no_boxes_does_not_set_flag(self, mock_shared_state, service_config):
        """
        If the model returns zero bounding boxes (empty scene),
        person_detected must not change.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.return_value = _make_results([])  # No boxes

        mock_shared_state._volatile_store["person_detected"] = False
        dummy_frame = MagicMock()
        _run_with_frame(svc, dummy_frame)

        assert mock_shared_state._volatile_store["person_detected"] is False

    def test_multiple_boxes_one_above_threshold_sets_flag(
        self, mock_shared_state, service_config
    ):
        """
        With multiple detections, if ANY box is >= threshold, flag must be True.
        Simulates a crowded frame with mixed-confidence detections.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.return_value = _make_results([0.30, 0.60, 0.92])

        dummy_frame = MagicMock()
        _run_with_frame(svc, dummy_frame)

        assert mock_shared_state._volatile_store["person_detected"] is True

    def test_confidence_threshold_respected_from_config(
        self, mock_shared_state, service_config
    ):
        """
        The threshold used for comparison must come from config.
        This test mutates the config threshold and verifies the service
        still applies the correct boundary, proving there is no hardcoded value.
        """
        service_config["software"]["ai_model"]["confidence_threshold"] = 0.95
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.return_value = _make_results([0.90])  # Below new threshold

        mock_shared_state._volatile_store["person_detected"] = False
        dummy_frame = MagicMock()
        _run_with_frame(svc, dummy_frame)

        # 0.90 < 0.95 threshold — flag must stay False
        assert mock_shared_state._volatile_store["person_detected"] is False


# ===========================================================================
# QUEUE BEHAVIOUR
# ===========================================================================

class TestYoloServiceQueue:
    """Verify correct handling of the frame queue under various conditions."""

    def test_empty_queue_reports_health_not_error(
        self, mock_shared_state, service_config
    ):
        """
        An empty queue (queue.Empty timeout) is NOT an error — it simply means
        no person is in the ROI. report_health() must be called, not report_error().
        This is critical: a false error here would trigger unnecessary Watchdog restarts.
        """
        svc = _make_service(mock_shared_state, service_config)
        # Queue is empty — model should never be called
        _run_empty_queue(svc)

        svc.report_health.assert_called()
        svc._mock_model.assert_not_called()

    def test_successful_inference_reports_health(
        self, mock_shared_state, service_config
    ):
        """A successful inference cycle must call report_health()."""
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.return_value = _make_results([0.91])

        dummy_frame = MagicMock()
        _run_with_frame(svc, dummy_frame)

        svc.report_health.assert_called()


# ===========================================================================
# FAULT TOLERANCE
# ===========================================================================

class TestYoloServiceFaultTolerance:
    """Verify the service handles model errors without crashing."""

    def test_model_exception_calls_report_error(
        self, mock_shared_state, service_config
    ):
        """
        If the YOLO model raises (e.g. Hailo hardware error, corrupted frame),
        report_error() must be called and the service must stay alive.
        This is critical: a model crash must NOT kill the monitoring thread.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.side_effect = RuntimeError("Hailo inference error")

        dummy_frame = MagicMock()

        def _stop_on_error():
            svc._stop_event.set()

        svc.report_health = MagicMock()
        svc.report_error = MagicMock(side_effect=_stop_on_error)

        svc.frame_queue.put_nowait(dummy_frame)

        with patch("src.services.yolo_service.time.sleep"):
            svc._main_loop()

        svc.report_error.assert_called()
        # Restore
        svc._mock_model.side_effect = None

    def test_model_exception_does_not_set_person_detected(
        self, mock_shared_state, service_config
    ):
        """
        After a model exception, person_detected must remain False.
        We must not signal a detection on a failed inference.
        """
        svc = _make_service(mock_shared_state, service_config)
        svc._mock_model.side_effect = RuntimeError("Hailo inference error")
        mock_shared_state._volatile_store["person_detected"] = False

        dummy_frame = MagicMock()

        svc.report_health = MagicMock()
        svc.report_error = MagicMock(side_effect=lambda: svc._stop_event.set())

        svc.frame_queue.put_nowait(dummy_frame)

        with patch("src.services.yolo_service.time.sleep"):
            svc._main_loop()

        assert mock_shared_state._volatile_store["person_detected"] is False
        # Restore
        svc._mock_model.side_effect = None
