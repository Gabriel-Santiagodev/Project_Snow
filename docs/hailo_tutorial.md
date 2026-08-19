---
name: setup_hailo
description: Installation guide for Raspberry Pi OS, Hailo-8L, and initial hardware configuration.
---

# Initial Setup for Hailo-8L and Raspberry Pi

## 1. Operating System
Although Arch Linux can be lightweight, for the Machine Learning environment of the Raspberry Pi 5 and the Hailo-8L drivers (along with precompiled Ultralytics YOLOv8 software), the officially supported distribution is **Raspberry Pi OS 64-bit (Debian Bookworm)**.
- Using Arch Linux will cause severe compatibility issues with hardware dependencies like `gpiozero` and Hailo PCIe drivers.
- **Decision:** It is highly recommended to **format the M.2 SSD** and install a fresh "Raspberry Pi OS (64-bit) Bookworm" using the Raspberry Pi Imager.

## 2. Hailo-8L Installation (Tutorial Based)
Once running Raspberry Pi OS on the SSD, execute the following:

1. **Update the system:**
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo reboot
   ```
2. **Enable PCIe Gen 3 (Acceleration):**
   - Run `sudo raspi-config`
   - Go to `Advanced Options` -> `PCIe Speed`.
   - Select `Yes` to enable the PCIe Gen 3 link.
   - Reboot.
3. **Install Hailo software:**
   ```bash
   sudo apt install hailo-all
   sudo reboot
   ```
4. **Clone Hailo examples (For testing):**
   ```bash
   git clone https://github.com/hailo-ai/hailo-rpi5-examples.git
   cd hailo-rpi5-examples
   source setup_env.sh
   pip install -r requirements.txt
   ```
5. **Test inference:**
   Run the basic pipeline using a USB camera (or the official camera by changing `video-source` to `/dev/video0`):
   ```bash
   python basic_pipelines/detection.py --labels-json resources/yolov8m-labels.json
   ```

## 3. Physical Connections and Network
- **IP Cameras & PoE:** The TP-Link TL-SF1005P switch is *Plug and Play*. Connect the cameras to the PoE ports and the Uplink port to the Raspberry Pi. No specific code configuration is needed for the switch; just configure the static IPs of the cameras in `settings.yaml` as RTSP streams.
- **Remote Access (Headless):** Enable VNC or SSH from `sudo raspi-config` under `Interface Options` to operate the Pi without a monitor.
