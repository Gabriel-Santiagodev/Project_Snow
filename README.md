# Project Snow: Autonomous Edge Computing Node

![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%205-lightgrey)
![Accelerator](https://img.shields.io/badge/AI%20Accelerator-Hailo--8-red)
![License](https://img.shields.io/badge/license-Proprietary-red.svg)

## 1. Project Overview

Project Snow is a 100% off-grid, autonomous edge-computing node designed to execute continuous, real-time Computer Vision (CV) workloads in disconnected environments. By leveraging solar power generation, concurrent Python multithreading, and dedicated neural processing hardware, the architecture eliminates reliance on external cloud servers, ensuring zero-latency deterministic inference and high availability without network dependencies.

## 2. Current MVP (Proof of Concept)

The initial Proof of Concept (PoC) is deployed as an assistive navigation system. Utilizing the Ultralytics YOLOv8 architecture accelerated via Hailo-8, the node identifies visually impaired individuals. Upon positive detection, an asynchronous event triggers directional audio actuation to provide spatial guidance towards specific infrastructure, demonstrating the system's capacity for real-time physical interaction without blocking the primary computer vision pipeline.

## 3. Developer Onboarding

To maintain architectural integrity and prevent concurrency-related memory leaks, all contributors must complete the following onboarding sequence before submitting a Pull Request:

1. **Review this document** to understand system requirements and deployment procedures.
2. **Read the Architecture Specification (`docs/architecture.md`)** to comprehend the event-driven monolithic topology, the `SharedState` memory bank, and the tiered fault-tolerance mechanisms.
3. **Study the Service Development Guide (`docs/module_template.md`)** for mandatory coding standards, inter-thread communication rules, and boilerplate templates.

## 4. System Requirements

### 4.1. Hardware Infrastructure
* **Compute Node:** Raspberry Pi 5 (16GB RAM).
* **AI Accelerator:** Hailo-8 M.2 AI Acceleration Module.
* **Vision Sensors:** HiLook Network Cameras (IP66 Weatherproof).
* **Actuators:** HF Audio Marine Flush-Mount Outdoor Speakers.
* **Power Subsystem:** Standardized photovoltaic array with charge controller and battery bank.

### 4.2. Software Dependencies
* **Operating System:** Raspberry Pi OS 64-bit (Debian Bookworm).
* **Language:** Python 3.11.x *(Note: Python 3.14+ is currently unsupported to ensure ABI compatibility with Hailo drivers and Ultralytics pre-compiled binaries).*
* **Core Packages (`requirements.txt`):**
  ```text
  opencv-python>=4.8.0
  ultralytics>=8.0.0
  pygame>=2.5.0
  psutil>=5.9.0
  PyYAML>=6.0
  numpy>=1.24.0
  Pillow>=10.0.0
  gpiozero>=1.6.2
  colorlog>=6.7.0
  ```

## 5. Installation & Quickstart

**1. Clone the repository:**
```bash
git clone https://github.com/Gabriel-Santiagodev/Project_Snow.git
cd Project_Snow
```

**2. Provision the Virtual Environment:**
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**3. System Initialization:**
Ensure all hardware peripherals (Hailo-8, Cameras via USB/CSI, GPIO pins) are physically connected. Launch the orchestration sequence:
```bash
bash scripts/main_launcher.sh
```
*(Alternatively, execute the Python entry point directly: `python3 src/core/main.py`)*

## 6. The Team

Project Snow is developed by engineering students from the **Universidad Politécnica de Santa Rosa Jáuregui**, committed to delivering industrial-grade edge computing architectures.

* **Ruben Gabriel Aguilar Santiago** - Lead Engineer / Computational Robotics Engineering
* **Roberto Carlos Jimenez Rodriguez** - Architecture Lead / ITIID Engineering
* **Joshua Suarez Tinajero** - Infrastructure Lead / Computational Robotics Engineering
* **Alvaro Huezzo Patiño** - General Co-Lead / Computational Robotics Engineering
* **Collaborators (ITIID Engineering):** Fernando, Valeria, Abraham, Yerik.

---
**License & Copyright**

Copyright (c) 2026 Project Snow Team. All Rights Reserved.

This software and associated documentation files are proprietary and confidential. Unauthorized copying, distribution, or modification is strictly prohibited.