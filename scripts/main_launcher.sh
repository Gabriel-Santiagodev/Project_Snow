#!/bin/bash

# ==============================================================================
# PROJECT SNOW - BASH FILE / MAIN LAUNCHER
# ==============================================================================
# Version: 1.0
# Last Updated: January 11, 2026
# Author: Roberto Carlos Jimenez Rodriguez
# Purpose: Tell to the Raspberry Pi how to start working
# ==============================================================================

echo "Starting Project Snow"

# Obtain the directory where this file is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" 

# Get the project root
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")" 

# Go to the project directory
cd "$PROJECT_ROOT" || exit 1

# Check if the venv exist
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual Environment not found"
    exit 1
fi

# Virtual Environment Check
echo "Checking Virtual Environment..."
PYTHON_BIN="venv/bin/python3"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "ERROR: Virtual Environment python binary not found at $PYTHON_BIN"
    exit 1
fi

# Hailo paths. 
export HAILO_PATH="/usr/lib/hailo" # TODO: Verify this path on the physical Raspberry Pi
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$HAILO_PATH
echo "Hailo environment configured"

# Force OpenCV to use the X11 (xcb) backend instead of searching for Wayland,
# which is not available inside the virtual environment's Qt plugins directory.
export QT_QPA_PLATFORM=xcb

# Force RTSP transport over TCP instead of UDP to improve stream stability and
# reduce reference-frame loss that triggers HEVC/H.265 decoder RPS errors.
export OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"

# Waiting 5 seconds to initialize the hardware (cameras, sensors, etc.)
echo "Waiting 5 seconds to initialize the hardware"
sleep 5

# Run python using the virtual environment explicitly
echo "Launching main.py..."
exec $PYTHON_BIN -m src.core.main