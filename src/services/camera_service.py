import time
import queue
import cv2
import numpy as np

from src.core.base_service import BaseService


class CameraService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

        # Safe config access — uses .get() with fallbacks throughout
        cameras_cfg = self.config.get("hardware", {}).get("cameras", {})
        self.cameras_config = cameras_cfg

        cam1_cfg = cameras_cfg.get("camera1", {})
        cam2_cfg = cameras_cfg.get("camera2", {})

        self.camera_uno = cv2.VideoCapture(cam1_cfg.get("src", 0))
        self.camera_dos = cv2.VideoCapture(cam2_cfg.get("src", 1))

        # Mutable object: get the reference once, never call set_volatile on it
        self.frame_queue = self.shared_state.get_volatile("camera_frame_queue")

        # Thresholds from settings.yaml
        camera_svc_cfg = self.config.get("software", {}).get("camera_service", {})
        self.movement_threshold = camera_svc_cfg.get("movement_threshold", 5.0)
        self.freeze_timeout = camera_svc_cfg.get("freeze_timeout_seconds", 10.0)

        # Previous frames for pixel-diff comparison
        self.previous_frame_uno = None
        self.previous_frame_dos = None
        self.previous_zone_a1 = None
        self.previous_zone_b1 = None
        self.previous_zone_b2 = None
        self.previous_zone_b3 = None

        # Freeze detection: tracks the last time motion was detected on each camera
        self.last_motion_time_uno = time.time()
        self.last_motion_time_dos = time.time()

        # Journey state machine
        # Flow: None → "a1" or "b2" → "b1" → (trigger on b3) → None
        # Pattern 1: Zone 1 (a1) → Zone 2 (b1) → Zone 4 (b3) → send frame
        # Pattern 2: Zone 3 (b2) → Zone 2 (b1) → Zone 4 (b3) → send frame
        self.journey_state = None
        self.last_frame_b1 = None  # Zone 2 frame saved to push to queue on journey completion

    def _main_loop(self):
        self.logger.info("Initializing camera service")
        while not self._stop_event.is_set():
            try:
                ret_uno, frame_uno = self.camera_uno.read()
                ret_dos, frame_dos = self.camera_dos.read()

                camera_uno_ok = ret_uno and frame_uno is not None
                camera_dos_ok = ret_dos and frame_dos is not None

                # --- Hardware connectivity checks ---
                if not camera_uno_ok and not camera_dos_ok:
                    self.logger.error("Both cameras are not working. Vision service inoperative")
                    self.report_error()
                    time.sleep(1)
                    continue

                if not camera_uno_ok:
                    self.logger.warning("Camera 1 is not working")
                    self.report_error()
                    time.sleep(1)
                    continue

                if not camera_dos_ok:
                    self.logger.warning("Camera 2 is not working")
                    self.report_error()
                    time.sleep(1)
                    continue

                # --- Freeze detection (timestamp-based) ---
                # A camera is only declared "frozen" if NO motion is detected
                # for freeze_timeout seconds. This avoids false positives on
                # static scenes (e.g., an empty hallway at night).
                current_time = time.time()
                camera_uno_frozen = False
                camera_dos_frozen = False

                gray_uno = cv2.cvtColor(frame_uno, cv2.COLOR_BGR2GRAY)
                if self.previous_frame_uno is not None:
                    if np.mean(cv2.absdiff(gray_uno, self.previous_frame_uno)) > self.movement_threshold:
                        self.last_motion_time_uno = current_time  # Reset timer on any motion
                    elif (current_time - self.last_motion_time_uno) > self.freeze_timeout:
                        self.logger.warning(f"Camera 1 appears frozen (static for over {self.freeze_timeout}s)")
                        camera_uno_frozen = True
                self.previous_frame_uno = gray_uno

                gray_dos = cv2.cvtColor(frame_dos, cv2.COLOR_BGR2GRAY)
                if self.previous_frame_dos is not None:
                    if np.mean(cv2.absdiff(gray_dos, self.previous_frame_dos)) > self.movement_threshold:
                        self.last_motion_time_dos = current_time
                    elif (current_time - self.last_motion_time_dos) > self.freeze_timeout:
                        self.logger.warning(f"Camera 2 appears frozen (static for over {self.freeze_timeout}s)")
                        camera_dos_frozen = True
                self.previous_frame_dos = gray_dos

                # Only escalate to report_error (Watchdog) if BOTH cameras are frozen
                if camera_uno_frozen and camera_dos_frozen:
                    self.logger.error("Both cameras frozen. Vision service inoperative.")
                    self.report_error()
                    time.sleep(1)
                    continue

                # --- Zone processing: Camera 1 ---
                if not camera_uno_frozen:
                    zones1 = self.cameras_config.get("camera1", {}).get("zones", {})

                    # Zone A1 (Zona 1): Entry point for Journey Pattern 1
                    coords_a1 = zones1.get("zone_a1", {}).get("coords", [0, 0, 320, 480])
                    x_min_a1, y_min_a1, x_max_a1, y_max_a1 = coords_a1
                    cropped_a1 = frame_uno[y_min_a1:y_max_a1, x_min_a1:x_max_a1]
                    gray_cropped_a1 = cv2.cvtColor(cropped_a1, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_a1 is not None:
                        if np.mean(cv2.absdiff(gray_cropped_a1, self.previous_zone_a1)) > self.movement_threshold:
                            if self.journey_state is None:
                                self.journey_state = "a1"
                                self.logger.info("Journey Pattern 1 started: motion in Zone 1 (a1)")

                    self.previous_zone_a1 = gray_cropped_a1

                # --- Zone processing: Camera 2 ---
                if not camera_dos_frozen:
                    zones2 = self.cameras_config.get("camera2", {}).get("zones", {})

                    # Zone B2 (Zona 3): Entry point for Journey Pattern 2
                    # Checked before B1 to avoid same-frame short-circuit
                    coords_b2 = zones2.get("zone_b2", {}).get("coords", [320, 0, 640, 480])
                    x_min_b2, y_min_b2, x_max_b2, y_max_b2 = coords_b2
                    cropped_b2 = frame_dos[y_min_b2:y_max_b2, x_min_b2:x_max_b2]
                    gray_cropped_b2 = cv2.cvtColor(cropped_b2, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_b2 is not None:
                        if np.mean(cv2.absdiff(gray_cropped_b2, self.previous_zone_b2)) > self.movement_threshold:
                            if self.journey_state is None:
                                self.journey_state = "b2"
                                self.logger.info("Journey Pattern 2 started: motion in Zone 3 (b2)")

                    self.previous_zone_b2 = gray_cropped_b2

                    # Zone B1 (Zona 2): Common second step for both patterns
                    # Best field of view — this frame is saved and sent to the queue
                    coords_b1 = zones2.get("zone_b1", {}).get("coords", [0, 0, 320, 480])
                    x_min_b1, y_min_b1, x_max_b1, y_max_b1 = coords_b1
                    cropped_b1 = frame_dos[y_min_b1:y_max_b1, x_min_b1:x_max_b1]
                    gray_cropped_b1 = cv2.cvtColor(cropped_b1, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_b1 is not None:
                        if np.mean(cv2.absdiff(gray_cropped_b1, self.previous_zone_b1)) > self.movement_threshold:
                            if self.journey_state in ("a1", "b2"):
                                self.journey_state = "b1"
                                self.last_frame_b1 = cropped_b1.copy()
                                self.logger.info("Journey: motion in Zone 2 (b1) — frame saved")

                    self.previous_zone_b1 = gray_cropped_b1

                    # Zone B3 (Zona 4): Trigger zone — confirms journey completion
                    coords_b3 = zones2.get("zone_b3", {}).get("coords", [0, 0, 640, 200])
                    x_min_b3, y_min_b3, x_max_b3, y_max_b3 = coords_b3
                    cropped_b3 = frame_dos[y_min_b3:y_max_b3, x_min_b3:x_max_b3]
                    gray_cropped_b3 = cv2.cvtColor(cropped_b3, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_b3 is not None:
                        if np.mean(cv2.absdiff(gray_cropped_b3, self.previous_zone_b3)) > self.movement_threshold:
                            if self.journey_state == "b1" and self.last_frame_b1 is not None:
                                self.logger.info("Journey complete! Sending Zone 2 frame to inference queue.")
                                if self.frame_queue.full():
                                    try:
                                        self.frame_queue.get_nowait()
                                    except queue.Empty:
                                        pass
                                self.frame_queue.put_nowait({
                                    "camera_id": "camera2",
                                    "zone": "zone_b1",
                                    "timestamp": time.time(),
                                    "frame": self.last_frame_b1,
                                })
                                self.journey_state = None
                                self.last_frame_b1 = None

                    self.previous_zone_b3 = gray_cropped_b3

                self.report_health()
                time.sleep(0.03)

            except queue.Full:
                self.logger.warning("Frame queue is full, dropping this cycle's frames.")
                self.report_error()
            except Exception as e:
                self.logger.error(f"Unexpected error capturing frames: {e}")
                self.report_error()
                time.sleep(1)