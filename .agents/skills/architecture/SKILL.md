---
name: architecture
description: Core concurrency architecture, SharedState rules, and ServiceManager for Project Snow.
---

# Concurrent Architecture and State Management

## Core Concepts
- Project Snow operates under an **"Event-Based Concurrent Modular Monolith"** model.
- **Edge Processing:** Everything runs locally. Nothing goes to the cloud, and no Wi-Fi is required.
- **Zero Blocking:** Video capture (Producer), ML inference (Consumer), and physical actuation (Asynchronous) run in separate threads inheriting from `BaseService`.

## Inter-thread Communication Rules
1. **Centralized Memory (`SharedState`):** NEVER declare loose global variables. Every flag (e.g., `person_detected`) or shared data must live in the single instance of `SharedState`. NO THREAD may communicate directly with another thread.
2. **Mutex Locks:** Whenever a service reads or writes to the `SharedState`, the `SharedState` class uses mutual exclusion locks (`threading.Lock()`) to prevent race conditions.
3. **Mutable Objects (Queues/Lists):** 
   - Must be obtained ONLY ONCE in the `__init__` using `get_volatile()`.
   - NEVER use `set_volatile()` on a Queue, as it destroys the memory reference. Use native methods like `.put()` or `.get()`.
4. **Immutable Objects (Bools, Ints):**
   - Use `get_volatile()` to read the value in every cycle.
   - Use `set_volatile()` to update the value in memory.
5. **Disk Writing (SSD Protection):** 
   - Fast calculations operate in volatile RAM.
   - Logs and persistent data must not be written directly from the main thread; they must be sent to a RAM buffer for a `QueueListener` (Log) or a specific resilience method to write asynchronously to the NVMe SSD (Wear Leveling). Do not burn out the SSD!
6. **Pipeline Integration:** Every new service is registered in `config/services_list.json` with its full module path (Reflection).
