# Project Snow: System Architecture Specification

## 1. System Overview & Architectural Principles

Project Snow is an autonomous, event-driven edge-computing node designed to execute continuous real-time Computer Vision (CV) workloads in off-grid environments. Because the system relies entirely on solar power and operates on resource-constrained hardware (e.g., Raspberry Pi), traditional sequential execution models are insufficient. 

To guarantee deterministic inference and prevent thermal throttling or battery depletion, the software architecture is built upon the following core engineering principles:

* **Concurrent Modular Monolith:** The system operates as a single application, but its internal processes (Video Capture, ML Inference, Audio Actuation) are strictly decoupled into independent parallel threads (Microservices).
* **Event-Driven Edge Computing:** To minimize CPU cycles, the system avoids continuous polling. Services remain in low-power states until triggered by specific asynchronous events (e.g., a frame entering a queue or a boolean flag changing state). All data processing occurs locally, eliminating cloud latency and ensuring 100% offline availability.
* **Centralized Thread-Safe State:** Direct thread-to-thread communication is strictly prohibited to prevent race conditions and memory leaks. All inter-service data exchange is routed through a central, lock-protected memory bank (`SharedState`).
* **Fault Isolation:** The crash of a single hardware peripheral or software module must not cause a kernel panic or halt the entire node. The architecture includes a dedicated orchestrator (`ServiceManager`) that monitors thread health and executes isolated restarts.

> **Note for Collaborators:** Understanding this macroscopic topology is mandatory before creating new modules. For specific coding standards and boilerplate templates, refer to the `module_template.md` development guide.

---

## 2. Initialization Pipeline & Hardware Safety Lockout

The system's boot sequence (`main.py`) is designed to validate the environment and protect the hardware from infinite crash loops before initializing any heavy computational workloads. The initialization follows a strict three-phase pipeline:

### Phase 2.1: Asynchronous Observability Initialization
Before any logic is executed, the non-blocking logging system is initialized. This ensures that every subsequent boot step, including catastrophic failures, is queued in RAM and safely flushed to the SSD without delaying the main execution thread.

### Phase 2.2: Configuration Parsing
The system loads the unified `settings.yaml` file. This YAML file acts as the single source of truth for all external variables (GPIO pin mappings, AI confidence thresholds, camera indices). Hardcoding these values within individual Python scripts is strictly forbidden.

### Phase 2.3: Hardware Safety Lockout (Maintenance Mode)
This is a critical resilience mechanism. Before starting the ML and Camera threads, the main execution sequence reads the persistent operational history from `config/system_state.json`. If the system detects chronic instability (`reboot_error_count >= 3`), it initiates a strict hardware lockout sequence:

* **Hardware Actuation & State Mutation:** The system immediately initializes the defined GPIO pins, turning on the `emergency_light` (LED) to visually signal a fault. Concurrently, it updates the in-memory state, setting `maintenance_mode_active` to `True`, and dispatches a `CRITICAL` freeze warning to the asynchronous logger.
* **The Zombie Loop (Execution Halt):** To prevent battery drain and potential hardware damage from continuous reboot loops, the system deliberately traps itself in an infinite idle loop (`while True`). This halts the boot sequence entirely, preventing the instantiation of the `ServiceManager` and any resource-heavy microservices.
* **Physical Intervention & Recovery:** The system polls the physical `reset_button` state every 0.1 seconds to avoid CPU overload. It will remain locked indefinitely until a technician physically presses the button. Upon detection, the system initiates a recovery protocol: it flushes the error counters (`reboot_error_count = 0`), sets the maintenance flag to `False`, overwrites the persistent `system_state.json` with the clean state, turns off the emergency LED, and safely breaks the loop to resume the normal boot sequence.
## 3. Service Orchestration & Thread Lifecycle

The core operational engine of Project Snow is the `ServiceManager`. Instead of a monolithic script that sequentially executes tasks, the orchestrator acts as a supervisor for multiple decoupled microservices running as parallel threads.

### 3.1. Dynamic Service Instantiation (Reflection)
To ensure the system is highly modular and adaptable to different hardware peripherals without modifying the core orchestrator, services are loaded dynamically.
* The `ServiceManager` reads the `config/services_list.json` file.
* Utilizing Python's `importlib` (Reflection), it parses the string paths (e.g., `src.services.camera_service.CameraService`) and instantiates the classes at runtime.
* During instantiation, Dependency Injection is utilized: the orchestrator passes the single global instance of `SharedState` and the parsed `settings.yaml` configuration to every service.

### 3.2. Thread Encapsulation & Safety Net (`BaseService`)
Every dynamically loaded module must inherit from the `BaseService` abstract class, which extends `threading.Thread`. This inheritance strictly enforces the lifecycle of the microservice:
* **The `run()` Wrapper:** The actual business logic (`_main_loop()`) is encapsulated within a rigorous `try-except` block inside the parent's `run()` method. If a specific service encounters an unhandled exception (e.g., a division by zero or an unexpected driver failure), the exception is caught and logged at the thread level. This prevents the error from propagating to the main OS process, ensuring the rest of the node continues operating.
* **Graceful Shutdown:** Threads are never forcefully terminated (killed). The orchestrator uses `threading.Event()` (`_stop_event`) to signal threads to finish their current loop iteration, release hardware resources, and exit gracefully.

---

## 4. Concurrency Model & State Management (`SharedState`)

In a multithreaded architecture, allowing parallel threads to directly modify global variables simultaneously leads to data corruption, race conditions, and system crashes. Project Snow strictly prohibits direct inter-service communication. Instead, all data exchange occurs through the `SharedState` module.

### 4.1. Thread-Safety & Mutex Locks
The `SharedState` acts as a centralized memory bank protected by Mutual Exclusion Locks (`threading.Lock()`). Whenever a thread attempts to read or write data, it must acquire the lock, ensuring atomic operations. Once the transaction is complete, the lock is released for other threads.

### 4.2. Volatile Memory & Inter-Thread Communication (RAM)
Data that requires high-speed access and does not need to survive a system reboot is stored in volatile memory (`_volatile_data`). This is where the core inter-service communication patterns are implemented:
* **Producer/Consumer Pattern (Heavy Data):** For continuous data streams, such as passing video frames from the Camera Service to the ML Inference Service, the system utilizes `queue.Queue()`. The queue handles its own internal locking, allowing the producer to append frames without blocking the consumer that is actively analyzing the oldest frame.
* **Reactive Polling (Lightweight Events):** For asynchronous event triggers (e.g., notifying the Audio Service that a target was detected), the system uses immutable primitives like boolean flags (e.g., `person_detected`). Services poll these flags at controlled intervals (`time.sleep()`) to avoid CPU monopolization.

### 4.3. Persistent Storage & Wear Leveling (SSD/SD)
Data that must survive power cycles or hardware reboots is stored in persistent memory (`_persistent_data`), which is physically written to the storage drive via `system_state.json`.
* **Wear-and-Tear Prevention:** Because SD cards and basic SSDs have limited write cycles, the system restricts persistent writes strictly to low-frequency events.
* **Usage Scope:** Persistent storage is exclusively utilized for resilience metrics (e.g., updating the `reboot_error_count` prior to a Hard Reboot) and scientific data gathering (e.g., incrementing `total_people_assisted` for research validation). High-frequency data (like bounding box coordinates or temperature readings) is never written to disk.

## 5. Fault Tolerance & Tiered Recovery System

In an edge-computing environment operating without human supervision, software anomalies (e.g., memory leaks, corrupted frames, or I/O driver timeouts) are inevitable. Project Snow implements a strict Watchdog routine within the `ServiceManager` (`check_health()`) that polls the status of all active threads and applies a tiered recovery strategy.

### 5.1. Health Polling & Tier 1 Recovery (Soft Restart)
Each service maintains a `consecutive_errors` counter. If a thread encounters a logical error (e.g., an empty camera frame) or completely crashes (`not thread.is_alive()`), the Watchdog detects this state.
* **Thread Reallocation (Soft Restart):** Instead of halting the system, the orchestrator isolates the failing service, signals a graceful stop, and executes a `join()` to clear its memory footprint. It then dynamically instantiates a fresh thread of the same class to take its place. This ensures that a localized failure (e.g., the audio driver hanging) does not interrupt the main Machine Learning inference loop.

### 5.2. Tier 2 Recovery (OS-Level Hard Reboot)
If a specific service repeatedly fails and exceeds the `max_thread_restarts` threshold (defined in `settings.yaml`), the orchestrator assumes a critical system-level or hardware-level lockup has occurred. 
* The system saves the current error state to persistent memory (incrementing the `reboot_error_count`).
* It triggers an OS-level reboot command (`sudo reboot`) to forcefully cycle the hardware and clear the RAM.

---

## 6. Asynchronous Observability & Telemetry (Logging)

Continuous telemetry is essential for debugging off-grid nodes. However, writing log entries to persistent storage (SD Card/SSD) involves extremely slow I/O operations. In a synchronous architecture, logging a single warning during the video capture loop could block the thread for milliseconds, causing frame drops and ruining the deterministic nature of the AI inference.

To bypass this hardware limitation, Project Snow implements a fully asynchronous, non-blocking logging architecture:

### 6.1. RAM Buffer (QueueHandler)
When any microservice emits a log message (e.g., `self.logger.info()`), the message is not written to the disk. Instead, it is instantly pushed into a thread-safe volatile memory buffer (`queue.Queue`) handled by a `QueueHandler`. This operation takes mere microseconds, allowing the high-performance threads (like Camera and YOLOv8) to continue executing without interruption.

### 6.2. Background Telemetry Worker (QueueListener)
A dedicated background thread (`QueueListener`) runs independently of the `ServiceManager`. Its sole responsibility is to dequeue messages from the RAM buffer and write them to the persistent storage (`logs/app.log`) at the speed of the disk, completely isolating the I/O latency from the core application logic.

### 6.3. Storage Wear-Leveling
To prevent the telemetry data from exhausting the limited capacity of the edge node's storage, the system utilizes a `RotatingFileHandler`. Once the log file reaches a strict size limit (e.g., 1 MB), the system automatically archives it and starts a new file, maintaining a strict maximum of historical backups. This guarantees that the system will never crash due to a `Disk Full` exception.