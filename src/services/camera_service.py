import time
import queue
import cv2
import numpy as np

from src.core.base_service import BaseService


class cameras_service(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        
        self.cameras_config = self.config.get("hardware", {}).get("cameras", {})
        self.software_config = self.config.get("software", {}).get("camera_service", {})

        self.camera_uno = cv2.VideoCapture(self.cameras_config.get("camera1", {}).get("src", 0))
        self.camera_dos = cv2.VideoCapture(self.cameras_config.get("camera2", {}).get("src", 1))

        self.frame_queue = self.shared_state.get_volatile("camera_frame_queue")
        
        self.movement_threshold = self.software_config.get("movement_threshold", 5.0)
        self.freeze_timeout = self.software_config.get("freeze_timeout_seconds", 5.0)
        self.sequence_timeout = self.software_config.get("sequence_timeout_seconds", 10.0)
        self.debug_mode = self.software_config.get("debug", False)
        self.debug_win_w = self.software_config.get("debug_window_width", 640)
        self.debug_win_h = self.software_config.get("debug_window_height", 480)

        # Minimize RTSP internal buffer to 1 frame to prevent accumulated lag.
        # Without this, OpenCV buffers several seconds of frames and the feed
        # appears frozen or heavily delayed during heavy processing.
        self.camera_uno.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.camera_dos.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Region of Interest (ROI) for Camera 1 and Camera 2
        # Fallback to [160, 120, 480, 360] if not defined
        self.roi_c1 = self.cameras_config.get("camera1", {}).get("zones", {}).get("capture_zone", {}).get("coords", [160, 120, 480, 360])
        self.roi_c2 = self.cameras_config.get("camera2", {}).get("zones", {}).get("capture_zone", {}).get("coords", [160, 120, 480, 360])
        
        # State machine variables
        # States: 0 = IDLE, 1 = C1_ACTIVE, 2 = WAITING_FOR_C2
        self.state = 0
        self.last_state_change = time.time()
        self.last_c1_movement = 0.0

        # Freeze tracking
        self.last_c1_frame = None
        self.last_c2_frame = None
        self.c1_last_movement_time = time.time()
        self.c2_last_movement_time = time.time()

    def _main_loop(self):
        self.logger.info("Initializing camera service (Exhibition Sequence Mode)")
        if self.debug_mode:
            self.logger.info("DEBUG MODE ENABLED: Visual windows will be shown.")

        while not self._stop_event.is_set():
            try:
                ret_uno, frame_uno = self.camera_uno.read()
                ret_dos, frame_dos = self.camera_dos.read()

                if not ret_uno and not ret_dos:
                    self.logger.error("Both cameras failed to read frames.")
                    self.report_error()
                    time.sleep(1)
                    continue

                if not ret_uno:
                    self.logger.warning("Camera 1 failed to read frame.")
                    self.report_error()
                    time.sleep(1)
                    continue

                if not ret_dos:
                    self.logger.warning("Camera 2 failed to read frame.")
                    self.report_error()
                    time.sleep(1)
                    continue

                current_time = time.time()

                # 1. Evaluate movement in ROIs
                # Crop ROIs
                x1_1, y1_1, x2_1, y2_1 = self.roi_c1
                cropped_c1 = frame_uno[y1_1:y2_1, x1_1:x2_1]
                gray_c1 = cv2.cvtColor(cropped_c1, cv2.COLOR_BGR2GRAY)

                x1_2, y1_2, x2_2, y2_2 = self.roi_c2
                cropped_c2 = frame_dos[y1_2:y2_2, x1_2:x2_2]
                gray_c2 = cv2.cvtColor(cropped_c2, cv2.COLOR_BGR2GRAY)

                c1_movement = False
                c2_movement = False

                if self.last_c1_frame is not None:
                    diff_c1 = cv2.absdiff(gray_c1, self.last_c1_frame)
                    if np.mean(diff_c1) > self.movement_threshold:
                        c1_movement = True
                        self.c1_last_movement_time = current_time

                if self.last_c2_frame is not None:
                    diff_c2 = cv2.absdiff(gray_c2, self.last_c2_frame)
                    if np.mean(diff_c2) > self.movement_threshold:
                        c2_movement = True
                        self.c2_last_movement_time = current_time

                self.last_c1_frame = gray_c1
                self.last_c2_frame = gray_c2

                # 2. Freeze detection (Watchdog trigger)
                c1_frozen = (current_time - self.c1_last_movement_time) > self.freeze_timeout
                c2_frozen = (current_time - self.c2_last_movement_time) > self.freeze_timeout
                
                # In exhibition mode, a frozen camera is normal if nobody passes for a while.
                # Only log it at debug level to avoid Watchdog resets if the hallway is just empty.
                if c1_frozen or c2_frozen:
                    pass # We intentionally don't report_error() for freeze to prevent false positives

                # 3. State Machine Logic
                # STATE 0: IDLE
                if self.state == 0:
                    if c1_movement:
                        self.logger.info("Sequence Triggered: Person detected in Camera 1 ROI. State -> 1")
                        self.state = 1
                        self.last_state_change = current_time
                        self.last_c1_movement = current_time

                # STATE 1: C1_ACTIVE
                elif self.state == 1:
                    if c1_movement:
                        self.last_c1_movement = current_time
                    
                    # If person has left C1 for more than 1 second
                    if (current_time - self.last_c1_movement) > 1.0:
                        self.logger.info("Sequence Progress: Person left Camera 1. State -> 2")
                        self.state = 2
                        self.last_state_change = current_time
                        
                    # Timeout guard
                    elif (current_time - self.last_state_change) > self.sequence_timeout:
                        self.logger.warning("Sequence Timeout: Person stayed in C1 too long. State -> 0")
                        self.state = 0

                # STATE 2: WAITING_FOR_C2
                elif self.state == 2:
                    if c2_movement:
                        self.logger.info("Sequence Complete! Person detected in Camera 2 ROI. Sending frame to YOLO.")
                        
                        # Trigger YOLO queue
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        
                        # Send RAW FULL FRAME to YOLO (not cropped, to give YOLO maximum context)
                        self.frame_queue.put_nowait(frame_dos)
                        
                        # Reset State Machine
                        self.state = 0
                        self.last_state_change = current_time
                    
                    # Timeout guard
                    elif (current_time - self.last_state_change) > self.sequence_timeout:
                        self.logger.warning("Sequence Timeout: Person never reached C2. State -> 0")
                        self.state = 0

                # 4. Debug Mode UI
                if self.debug_mode:
                    display_c1 = frame_uno.copy()
                    display_c2 = frame_dos.copy()

                    # Draw ROIs
                    cv2.rectangle(display_c1, (x1_1, y1_1), (x2_1, y2_1), (0, 255, 0) if c1_movement else (0, 0, 255), 2)
                    cv2.rectangle(display_c2, (x1_2, y1_2), (x2_2, y2_2), (0, 255, 0) if c2_movement else (0, 0, 255), 2)

                    # Add text
                    cv2.putText(display_c1, f"State: {self.state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                    cv2.putText(display_c2, "Target: Camera 2 ROI", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

                    # Resize to configured dimensions before displaying to avoid
                    # full-screen windows when the camera stream resolution is large.
                    display_c1 = cv2.resize(display_c1, (self.debug_win_w, self.debug_win_h))
                    display_c2 = cv2.resize(display_c2, (self.debug_win_w, self.debug_win_h))

                    cv2.imshow("Camera 1 Debug", display_c1)
                    cv2.imshow("Camera 2 Debug", display_c2)
                    cv2.waitKey(1)

                self.report_health()
                time.sleep(0.03)

            except queue.Full:
                self.logger.warning("Frame queue is full, dropping this cycle's frames.")
                self.report_error()
            except Exception as e:
                self.logger.error(f"Unexpected error capturing frames: {e}")
                self.report_error()
                time.sleep(1)
        
        # Shutdown
        if self.debug_mode:
            cv2.destroyAllWindows()
        self.camera_uno.release()
        self.camera_dos.release()