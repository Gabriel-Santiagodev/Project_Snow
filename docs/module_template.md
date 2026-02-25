# 🛠️ Service Development Guide (Project Snow)

Welcome to the development team. Our architecture is based on **Concurrent Microservices** (parallel threads).

To ensure system stability, prevent memory leaks, and enable automatic error recovery (via the Watchdog), **all new modules must strictly adhere to this template.**

---

## 📋 1. Mandatory Rules

1.  **No `print()` statements:** The use of `print()` is strictly prohibited. Always use `self.logger.info()`, `.warning()`, or `.error()` for observability.
2.  **No Hardcoding (Magic Numbers):** Do not write GPIO pins, file paths, resolutions, or AI thresholds directly in the code. All external configuration parameters must be placed in `config/settings.yaml` and accessed via `self.config`. *(Note: Internal counters or purely logical variables should remain in your script).*
3.  **Lifecycle Control:** Never use a standard `while True:` loop. Always use `while not self._stop_event.is_set():` to allow the system to shut down gracefully without creating zombie threads.
4.  **Health & Error Reporting:**
    -   Call `self.report_health()` at the end of every successful loop iteration to clear error flags.
    -   Call `self.report_error()` when you detect a hardware or logical failure (e.g., a disconnected camera or empty frame). Accumulating 3 consecutive errors will trigger an automatic thread restart.
5.  **Shared State Memory (Crucial):** You must respect mutability rules when communicating with other threads via `self.shared_state`:
    -   **Mutable objects (Queues, Lists):** NEVER use `set_volatile()`. Obtain the reference once using `get_volatile()` in your `__init__` and use native methods (like `.put()` or `.get()`).
    -   **Immutable objects (Booleans, Integers, Strings):** Use `get_volatile()` to read and `set_volatile()` to overwrite the value.

---

## 📝 2. Base Templates (Boilerplates)

Depending on whether your task requires interacting with mutable or immutable objects, choose the appropriate template, copy it into a new file inside `src/services/`, and replace the core logic.

### Template A: Mutable Objects (Producer/Consumer Pattern via Queues)

*Ideal for: Services that need to pass heavy data sequentially without blocking each other, such as the Camera Service (Producer putting frames into the queue) and the AI Service (Consumer extracting frames from the queue).*

```python
import time
import queue
from src.core.base_service import BaseService

class MutableServiceTemplate(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        
        # 1. Read parameters from settings.yaml
        # e.g., self.threshold = self.config['software']['ai_model']['confidence_threshold']
        
        # 2. Connect to Mutable Objects in the Shared State ONLY ONCE
        self.frame_queue = self.shared_state.get_volatile("camera_frame_queue")

    def _main_loop(self):
        self.logger.info("Initializing mutable service...")
        
        while not self._stop_event.is_set():
            try:
                # ==========================================
                # SERVICE LOGIC GOES HERE (e.g., Consumer)
                # ==========================================
                
                # Try to extract data. If empty for 1 sec, jumps to queue.Empty
                data = self.frame_queue.get(timeout=1.0)
                
                # Simulation: If data is corrupted or hardware disconnected
                if data is None:
                    self.logger.warning("Hardware returned empty data. Possible disconnection.")
                    self.report_error() # <--- Increments the consecutive error counter
                    time.sleep(1)
                    continue # Skip the rest of the loop
                
                # If execution was successful:
                self.report_health() # <--- Resets error counter to 0
                
                # PREVENTION: Sleep to avoid 100% CPU usage (~30 FPS)
                time.sleep(0.03) 
                
            except queue.Empty:
                # The queue is empty, this is not an error, just keep waiting
                pass
            except Exception as e:
                self.logger.error(f"Unexpected error processing data: {e}")
                self.report_error()
```

### Template B: Immutable Objects (Simple Reactive Service)

*Ideal for: Services that only need to read or update lightweight state flags without sequential data processing. Examples include an Audio Service waiting for a boolean flag to play a sound, or a Sensor Service constantly updating an integer value.*

```python
import time
from src.core.base_service import BaseService

class ImmutableServiceTemplate(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        
        # 1. Read parameters from settings.yaml
        # e.g., self.audio_path = self.config['hardware']['audio']['alert_file']

    def _main_loop(self):
        self.logger.info("Initializing immutable service...")
        
        while not self._stop_event.is_set():
            try:
                # ==========================================
                # SERVICE LOGIC GOES HERE (e.g., Audio Alert)
                # ==========================================
                
                # 1. Read an immutable data point (boolean)
                person_detected = self.shared_state.get_volatile("person_detected")
                
                if person_detected:
                    self.logger.info("Alert! Playing sound...")
                    
                    # Playback simulation
                    # if not play_sound(): 
                    #     self.report_error() # Increments error counter (e.g., speaker disconnected)
                    #     continue
                    
                    # 2. Update the immutable object to prevent infinite looping
                    self.shared_state.set_volatile("person_detected", False)
                
                # If execution was successful:
                self.report_health()
                
                # PREVENTION: Sleep to avoid 100% CPU usage (Checks the Shared State 10 times per second)
                time.sleep(0.1) 
                
            except Exception as e:
                self.logger.error(f"Unexpected error in the immutable service: {e}")
                self.report_error()
                time.sleep(1)
```

## 🧰 3. Available API & Injected Tools

By inheriting from `BaseService`, your class automatically receives several injected dependencies accessible via `self.`. You do not need to import these manually.

### A. Configuration (`self.config`)

Your bridge to the `config/settings.yaml` file.

* **Usage:** Before creating a new hardware variable, file path, or algorithmic threshold, check if it exists in the YAML file. If your service requires a new external parameter, add it to `settings.yaml` first, and then read it here.
* *Example:* `volume = self.config['hardware']['audio']['volume']`

### B. The Logger (`self.logger`)

Do not use `print()`. The logger automatically formats and writes information to the disk, allowing us to debug the system in real-time.

* `self.logger.debug("Threshold value is 0.85")`
* `self.logger.info("AI Model loaded successfully")`
* `self.logger.warning("Camera latency detected")`
* `self.logger.error("Failed to initialize audio driver")`

### C. The Shared State (`self.shared_state`)

The only authorized mechanism for inter-thread communication.

**⚠️ Strict Mutability Constraints (RAM):**

* **Mutable Objects (Queues, Lists, Dicts):** Obtain their reference ONLY ONCE in the `__init__` using `.get_volatile()` and never put it inside of the loop. Inside your loop, use their native methods (e.g., `.put()`, `.get()`). **NEVER use `set_volatile` on a Queue**, as it will destroy the memory reference and break concurrency.
* **Immutable Objects (Booleans, Strings, Integers):** For these, you must use `.get_volatile("key")` to read them in every loop iteration, and `.set_volatile("key", new_value)` to overwrite them.

**Persistent Data (Metrics & Resilience on SSD):**
Unlike volatile memory (RAM), these methods write directly to the physical storage. In our project, we use these functions specifically to gather data for analysis and our scientific paper. To prevent SSD wear-and-tear, use them **strictly for specific, low-frequency events**.

* `self.shared_state.set_metric("total_people_assisted", value)`: Use to update a counter exactly once when a person is successfully detected.
* `self.shared_state.set_resilience("reboot_error_count", value)`: Use to update the reboot error counter, tracking the total number of times the Raspberry Pi has been rebooted.

---

## 🔌 4. Service Registration

Creating your `.py` file does not automatically execute it. You must register your new service into the system's pipeline.

1.  Open the file `config/services_list.json`.
2.  Add the strict path of your class to the `"services"` array following this format: `src.services.module_name.ClassName`.

*Example structure:*

```json
{
    "_comment": "Services List - Version 1.0",
    "services": [
        "src.services.camera_service.CameraService",
        "src.services.yolo_service.YoloService",
        "src.services.audio_service.AudioService",
        "src.services.your_new_module.YourNewClass"
    ]
}