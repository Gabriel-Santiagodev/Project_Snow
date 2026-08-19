---
name: hardware_recovery
description: Hardware specifications and tiered recovery (Watchdog) logic for Project Snow.
---

# Hardware Target and Fault Tolerance

## Hardware Specifications
- **Host:** Raspberry Pi 5 (16GB RAM) booting from SSD M.2 500GB Kingston NV2 (PCIe 4.0).
- **AI Accelerator:** Hailo-8L connected via PCIe M.2 HAT+ (13 TOPS capability).
- **Power:** Pure battery/Power supply simulating an Off-Grid setup (100% solar).
- **Cameras:** HiLook IP connected via Ethernet to a TP-Link PoE Switch (TL-SF1005P). The switch is Plug-and-Play; it requires no code configuration, only the correct RTSP IP for the cameras.
- **Actuators (Innovafest Expo):** 2.42 OLED Display (IIC) and LED Lights.
- **Actuators (Final Production):** Marine Speakers via USB DAC.

## Tiered Recovery and Safety Logic
The system must be able to self-heal in a remote environment.

1. **Watchdog (`ServiceManager`):** Monitors the health of all services every N seconds by checking their thread error counters.
2. **Tier 1 (Soft Restart):** If an individual thread fails (e.g., `oledservice` throws an error or dies), ONLY that thread is restarted. The Machine Learning inference (YOLOv8) and the rest of the system are NOT stopped.
3. **Tier 2 (Hard Reboot):** If a service reaches the maximum allowed restarts (`max_thread_restarts`), a hardware lockup is assumed. The system executes `sudo reboot` to force an OS reboot, saving the error count to disk (`reboot_error_count`) beforehand.
4. **Zombie Loop (Hardware Safety Lockout):** If multiple consecutive crashes occur or the `reboot_error_count` is >= 3 at startup, the software enters maintenance mode. It gets trapped in a low-power `while True` loop, turns on a red emergency LED, and waits for a human to physically press the Reset button. **This protects the battery from infinite reboot loops.**
