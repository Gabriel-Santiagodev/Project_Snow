---
name: project_background
description: Deep context, history, and overarching goals of Project Snow (Off-Grid Edge AI for the visually impaired).
---

# Project Snow: Background and General Context

## What is Project Snow?
Project Snow is a 100% off-grid, autonomous edge computing node powered by Artificial Intelligence and computer vision. Physically, it resembles a 3-meter metal light pole equipped with solar panels, a lower cabinet containing the processing unit, and cameras. 

## The Problem and the Mission
The project was born out of a real-world mobility barrier at the Universidad Politécnica de Santa Rosa Jáuregui (UPSRJ), an inclusive university with blind and deaf students. Specifically, "Building 3" has poor infrastructure, making it inaccessible for blind students. The goal is to install this node at a strategic point on the way to Building 3. When a blind person walks past the pole, the AI detects them and provides audio instructions on how to reach the building safely.

## Key Differentiators
1. **Edge Computing:** Unlike traditional security cameras that send video to a cloud server, Snow processes everything locally inside the cabinet using a Raspberry Pi. No internet, Wi-Fi, or external networks are required. This ensures zero latency and absolute privacy.
2. **100% Off-Grid:** The system runs entirely on solar energy (panel, charge controller, battery). It does not plug into the university's electrical grid, making it autonomous and sustainable.
3. **Modular and Scalable:** While the current Proof of Concept (PoC) helps visually impaired students, the underlying architecture is a "Modular Adaptive System." The same pole and hardware can be deployed in agriculture (detecting pests) or industrial security (detecting missing helmets) simply by swapping the AI model and the actuator response.

## Hardware Overview
- **Compute:** Raspberry Pi 5 (16GB RAM) running Raspberry Pi OS.
- **AI Processing:** Hailo-8L M.2 HAT+ (13 TOPS) for real-time inference without thermal throttling.
- **Storage:** M.2 NVMe SSD 500GB PCIe 4.0 for fast booting and log persistence.
- **Sensors:** HiLook IP Cameras connected via a TP-Link PoE switch.
- **Actuators:** Directional marine speakers (final deployment) or OLED/LEDs (for exhibitions).
