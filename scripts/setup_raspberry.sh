#!/bin/bash
# ==============================================================================
# PROJECT SNOW - RASPBERRY PI SETUP SCRIPT
# ==============================================================================
# Purpose: Installs system-level dependencies required for pygame, OpenCV, 
#          and luma.oled to compile and run successfully on a fresh Raspberry Pi.
# ==============================================================================

echo "Installing Project Snow System Dependencies..."

# 1. Update package list
sudo apt-get update

# 2. Install dependencies for Pygame and OpenCV
sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
                        libsm6 libxext6 libxrender-dev libgl1-mesa-glx

# 3. Install dependencies for luma.oled and psutil
sudo apt-get install -y python3-dev python3-pip build-essential libfreetype6-dev \
                        libjpeg-dev libopenjp2-7 libtiff5

# 4. Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 5. Install Python requirements
echo "Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup completed successfully."
