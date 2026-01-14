# ==============================================================================
# PROJECT SNOW - SHARED STATE
# ==============================================================================
# Version: 1.0
# Last Updated: January 11, 2026
# Author: Roberto Carlos Jimenez Rodriguez
# Purpose: Managing of Volatie and Persistant information
# ==============================================================================

import threading
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SharedState:
    """
    This file is the storage place for all the variables in this project

    Here are managed two kinds of information:
    - Volatile information. Information that is not neccesary to keep, such as the last detection 
    - Persistant information. Information we must keep every reboot, such as 'maintenance_mode' = True
    """

    def __init__(self, json_path="config/system.state.json"):

        # Lock to prevent errors
        self._lock = threading.Lock()

        # Persistent keys
        self._PERSISTENT_KEYS = {
            "maintenance_mode",
            "reboot_error_count",
            "eco_mode_active",
            "last_error_timestamp"
        }

        # Volatile information (RAM)
        self._data = {}

        # JSON path
        self._json_path = Path(json_path)

        # Load from disk at startup
        self._load_from_disk()

        # Initialize volatile keys with defaults
        self._initialize_volatile_data()
    
    def _initialize_volatile_data(self):
        """ This function gives default values to the volatile data. """
        self._data.update({
            "detections": None,
            "voltage": 0.0,
            "cpu_temp": 0.0,
            "last_frame": None
        })

    def _load_from_disk(self):
        """
        This function does 3 things:
        - Opens and reads the JSON file
        - If the file doesn't exist or is corrupted, use defaults
        - Copy values into self._data
        """

        # Try to open the JSON file
        try:
            with open(self._json_path, 'r') as f:
                data = json.load(f)
                self._data.update(data)
                logger.info("Loaded state from the disk")

        # In case it doesn't exist, default values are used
        except FileNotFoundError:
            logger.info("No saved state found, using defaults")
            self._data.update({
                "maintenance_mode": False,
                "reboot_error_count": 0,
                "eco_mode_active": False,
                "last_error_timestamp": None
            })

        # In case it is corrupted, default values are used
        except json.JSONDecodeError:
            logger.error("Corrupted state file, using defaults")
            self._data.update({
                "maintenance_mode": False,
                "reboot_error_count": 0,
                "eco_mode_active": False,
                "last_error_timestamp": None
            })

            
    def get(self, key):
        """ Get a value from RAM. """
        with self._lock:
            return self._data.get(key)
        
    def set(self, key, value):
        """ Set a value in RAM only """
        with self._lock:
            self._data[key] = value
    
    def _save_to_disk(self):
        """ Save persistent data to JSON file. """
        # Extract only persistent keys
        self.persistent_data = {
            key: self._data[key] 
            for key in self._PERSISTENT_KEYS 
            if key in self._data
        }

        # Write to file
        with open(self._json_path, 'w') as f:
            json.dump(self.persistent_data, f, indent=2)

    def set_persistent(self, key, value):
        """ Set a value in RAM and save to disk. """
        with self._lock:
            self._data[key] = value
            self._save_to_disk()