import time
import queue
import cv2
import numpy as np

from src.core.base_service import BaseService


class cameras_service(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        
        self.cameras_config = self.config["hardware"]["cameras"]

        self.resolution_camera_uno = self.cameras_config["camera1"]["resolution"]
        self.camera_uno = cv2.VideoCapture(self.cameras_config["camera1"]["src"])

        self.resolution_camera_dos = self.cameras_config["camera2"]["resolution"]
        self.camera_dos = cv2.VideoCapture(self.cameras_config["camera2"]["src"])

        self.frame_queue = self.shared_state.get_volatile("camera_frame_queue")
        
        self.previous_frame_uno = None
        self.previous_frame_dos = None
        self.previous_zone_a1 = None
        self.previous_zone_a2 = None
        self.previous_zone_b1 = None
        self.previous_zone_b2 = None
        #self.movement_threshold = self.config["software"]["camera_service"]["movement_threshold"]
        self.movement_threshold = self.config.get("software", {}).get("camera_service", {}).get("movement_threshold", 5.0)


    
    
    def _main_loop(self):
        self.logger.info("Initializing camera service")
        while not self._stop_event.is_set():
            try:
                #la logica de camaras de schos :D
                ret_uno, frame_uno = self.camera_uno.read()
                ret_dos, frame_dos = self.camera_dos.read()

                camera_uno_ok = ret_uno and frame_uno is not None
                camera_dos_ok = ret_dos and frame_dos is not None

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

                camera_uno_frozen = False
                camera_dos_frozen = False

                gray_uno = cv2.cvtColor(frame_uno, cv2.COLOR_BGR2GRAY)

                if self.previous_frame_uno is not None:
                    diff_uno = cv2.absdiff(gray_uno, self.previous_frame_uno)
                    if np.mean(diff_uno) < self.movement_threshold:
                        self.logger.warning("Freeze frame from Camera 1 detected.")
                        self.report_error()
                        camera_uno_frozen = True
                self.previous_frame_uno = gray_uno

                gray_dos = cv2.cvtColor(frame_dos, cv2.COLOR_BGR2GRAY)

                if self.previous_frame_dos is not None:
                    diff_dos = cv2.absdiff(gray_dos, self.previous_frame_dos)
                    if np.mean(diff_dos) < self.movement_threshold:
                        self.logger.warning("Freeze frame from Camera 2 detected.")
                        self.report_error()
                        camera_dos_frozen = True
                self.previous_frame_dos = gray_dos

                if camera_uno_frozen and camera_dos_frozen:
                    time.sleep(1)
                    continue

                if not camera_uno_frozen:
                    zonea1_data = self.cameras_config["camera1"]["zones"]["zone_a1"]
                    x_min_a1, y_min_a1, x_max_a1, y_max_a1 = zonea1_data["coords"]

                    cropped_a1 = frame_uno[y_min_a1:y_max_a1, x_min_a1:x_max_a1]

                    gray_cropped_a1 = cv2.cvtColor(cropped_a1, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_a1 is not None:
                        diff_a1 = cv2.absdiff(gray_cropped_a1, self.previous_zone_a1)

                        if np.mean(diff_a1) > self.movement_threshold:

                            if self.frame_queue.full():
                                try:
                                    self.frame_queue.get_nowait()
                                except queue.Empty:
                                    pass

                            self.frame_queue.put_nowait({
                                "camera_id":"camera1",
                                "zone":"zone_a1",
                                "timestamp": time.time(),
                                "frame": cropped_a1,
                            })

                    self.previous_zone_a1 = gray_cropped_a1

                    zonea2_data = self.cameras_config["camera1"]["zones"]["zone_a2"]
                    x_min_a2, y_min_a2, x_max_a2, y_max_a2 = zonea2_data["coords"]

                    cropped_a2 = frame_uno[y_min_a2:y_max_a2, x_min_a2:x_max_a2]

                    gray_cropped_a2 = cv2.cvtColor(cropped_a2, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_a2 is not None:
                        diff_a2 = cv2.absdiff(gray_cropped_a2, self.previous_zone_a2)

                        if np.mean(diff_a2) > self.movement_threshold:
                            self.logger.info("Movement in Camera 1 zone a2")
                    
                    self.previous_zone_a2 = gray_cropped_a2

                    

                if not camera_dos_frozen:
                    zoneb1_data =  self.cameras_config["camera2"]["zones"]["zone_b1"]
                    x_min_b1, y_min_b1, x_max_b1, y_max_b1 = zoneb1_data["coords"]

                    cropped_b1 = frame_dos[y_min_b1:y_max_b1, x_min_b1:x_max_b1]

                    gray_cropped_b1 = cv2.cvtColor(cropped_b1, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_b1 is not None:
                        diff_b1 = cv2.absdiff(gray_cropped_b1, self.previous_zone_b1)

                        if np.mean(diff_b1) > self.movement_threshold:
                            self.logger.info("Movement detected in Camera 2 zone b1")
                    
                    self.previous_zone_b1 = gray_cropped_b1

                    zoneb2_data =  self.cameras_config["camera2"]["zones"]["zone_b2"]
                    x_min_b2, y_min_b2, x_max_b2, y_max_b2 = zoneb2_data["coords"]

                    cropped_b2 = frame_dos[y_min_b2:y_max_b2, x_min_b2:x_max_b2]

                    gray_cropped_b2 = cv2.cvtColor(cropped_b2, cv2.COLOR_BGR2GRAY)

                    if self.previous_zone_b2 is not None:
                        diff_b2 = cv2.absdiff(gray_cropped_b2, self.previous_zone_b2)

                        if np.mean(diff_b2) > self.movement_threshold:
                            self.logger.info("Movement detected in Camera 2 zone b2")

                    self.previous_zone_b2 = gray_cropped_b2
                    
                    

                
                self.report_health()
                time.sleep(0.03)

            except queue.Full:
                self.logger.warning("Frame queue is full, dropping this cycle's frames.")
                self.report_error()
            except Exception as e:
                self.logger.error(f"Unexpected error capturing frames: {e}")
                self.report_error()
                time.sleep(1)