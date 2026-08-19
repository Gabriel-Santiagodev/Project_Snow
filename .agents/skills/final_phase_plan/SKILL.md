---
name: final_phase_plan
description: Specific plan, logic, and block breakdown for the Final Development Phase (Innovafest).
---

# Final Phase Development Plan

This document outlines the exact goals and logic for the final development sprint of Project Snow, targeting the `innovafest` branch. We are preparing the system for an exhibition on August 21.

## The Two Main Blocks

### Block 1: Architecture Preparation
The goal is to prepare and refine the software architecture using the existing codebase as a foundation. No massive reworks.
Currently, the YOLO service is ready, but the Audio service cannot be used at the exhibition due to noise rules. We need new services to replace it.

1. **Camera Logic for Exhibition (`camerasservice`):**
   - For the 24/7 installation, we use complex tracking. But for the exhibition, we simplify:
   - We have two cameras facing different directions. 
   - Logic: Camera 1 acts as "Button 1". Camera 2 acts as "Button 2". 
   - Sequence: Person appears in Camera 1 -> Person disappears from Camera 1 -> Person appears in Camera 2. When this sequence is fulfilled, a frame is sent to the queue for AI processing. This simulates a person walking past the pole with a cane.
2. **New Service: `lightservice`**
   - Reads the `person_detected` boolean flag from the `SharedState`.
   - If `True`, it turns on an LED connected to the Raspberry Pi GPIO for 5 seconds.
   - After 5 seconds, it turns the LED off and sets `person_detected` back to `False`.
3. **New Service: `oledservice`**
   - Controls a 2.42 OLED IIC display.
   - Default state: Displays "SNOW".
   - Reads the `person_detected` flag. If `True`, the display changes to "PERSONA DETECTADA".
   - Resets the flag to `False` and returns to displaying "SNOW".
4. **General Evaluation and QA:**
   - Ensure all services (new and old) are compatible and do not cause race conditions.
   - Fix any `requirements.txt` issues.
   - Create tests using `pytest` inside `tests/test_services/test_[service_name].py`. We must test edge cases (what happens if it runs 24/7, if flags get stuck, if cameras disconnect) and verify log outputs and watchdog recovery.
5. **Merge Strategy:**
   - All these services will be developed in their own branches and merged into `innovafest`.

### Block 2: Raspberry Pi Integration
Once Block 1 is merged, the software must be deployed to the physical hardware.
- Transfer the `innovafest` branch code to the Raspberry Pi.
- Ensure `scripts/main_launcher.sh` executes automatically on boot.
- Install Python, dependencies, and Hailo-8L drivers.
- Run tests on the Raspberry Pi itself.
- Verify the Watchdog logic by intentionally crashing services to ensure the Tier 1 (Soft Restart), Tier 2 (Hard Reboot), and Zombie Loop recovery mechanisms function correctly.
- The ultimate goal: Flip the power switch, and the system boots, runs, and detects completely autonomously without a monitor or keyboard.
