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
                    for zone_name, zone_data in self.cameras_config["camera1"]["zones"].items():
                        x_min, y_min, x_max, y_max = zone_data["coords"]
                        cropped = frame_uno[y_min:y_max, x_min:x_max]

                        self.frame_queue.put_nowait({
                            "camera_id":"camera1",
                            "zone": zone_name,
                            "timestamp": time.time(),
                            "frame": cropped,
                        })

                if not camera_dos_frozen:
                    for zone_name, zone_data in self.cameras_config["camera2"]["zones"].items():
                        x_min, y_min, x_max, y_max = zone_data["coords"]
                        cropped = frame_dos[y_min:y_max, x_min:x_max]

                        self.frame_queue.put_nowait({
                            "camera_id": "camera2",
                            "zone": zone_name,
                            "timestamp": time.time(),
                            "frame": cropped
                        })
                
                self.report_health()
                time.sleep(0.03)

            except queue.Full:
                self.logger.warning("Frame queue is full, dropping this cycle's frames.")
                self.report_error()
            except Exception as e:
                self.logger.error(f"Unexpected error capturing frames: {e}")
                self.report_error()
                time.sleep(1)