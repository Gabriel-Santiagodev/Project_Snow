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

# Virtual Environment
echo "Activating Virtual Environment"
source venv/bin/activate

# Hailo paths. 
export HAILO_PATH="/usr/lib/hailo" # TODO: Verify this path on the physical Raspberry Pi
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$HAILO_PATH
echo "Hailo environment configured"

# Waiting 5 seconds to initialize the hardware (cameras, sensors, etc.)
echo "Waiting 5 seconds to initialize the hardware"
sleep 5

# Run python. NOTE: Once we create main.py, CHECK if this path is right
python3 src/core/main.py 