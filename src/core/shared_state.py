# ==============================================================================
# PROJECT SNOW - SHARED STATE
# ==============================================================================
# Version: 2.0
# Last Updated: February 3, 2026
# Author: Roberto Carlos Jimenez Rodriguez
# Purpose: Managing of Volatile and Persistent information
# ==============================================================================

import threading
import json
import logging
from pathlib import Path
import queue 

logger = logging.getLogger(__name__)

class SharedState:
    """
    This file is the storage place for all the variables in this project

    Here are managed two kinds of information:
    - Volatile information. Information that is not necessary to keep, such as the last detection 
    - Persistent information. Information we must keep every reboot, such as 'maintenance_mode' = True
    """

    def __init__(self, json_path="config/system_state.json"):

        # Lock to prevent errors
        self._lock = threading.Lock()

        # JSON path
        self._json_path = Path(json_path)

       # Start with persistent and volatile data empty
        self._persistent_data = {}

        self._volatile_data = {}

        # Load from disk at startup
        self._load_from_disk()

        # Initialize volatile keys with defaults
        self._initialize_volatile_data()
    
    def _get_default_persistent_state(self):
        """ This function returns the base values for the persistent data of the system """
        return {
            "system_info": {
                "first_install_date": "2026-01-11T00:00:00Z",
                "last_boot_timestamp": None,
                "total_uptime_hours": 0
            },
            "resilience" : {
                "maintenance_mode_active": False,
                "reboot_error_count": 0
            },
            "persistence_settings": {
                "eco_mode_active": False
            },
            "scientific_metrics": {
                "total_people_assisted": 0,
                "total_system_restarts": 0
            },
            "metadata": {
                "version": "2.0",
                "lastUpdated": "2026-02-03T00:00:00Z",
                "author": "Ruben Santiago Aguilar and Roberto Carlos Jimenez Rodriguez"
            }
        }

    def _initialize_volatile_data(self):
        """ This function gives default values to the volatile data. """
        self._volatile_data = {
            "voltage": 0.0,
            "cpu_temp": 0.0,
            "camera_frame_queue": queue.Queue(),
            "person_detected": False 
        }

    def _load_from_disk(self):
        """
        This function does 3 things:
        - Opens and reads the JSON file
        - If the file doesn't exist or is corrupted, use defaults
        - Copy values into self._persistent_data
        """

        # Try to open the JSON file
        try:
            with open(self._json_path, 'r') as f:
                data = json.load(f)
                self._persistent_data = data
                logger.info("Loaded state from the disk")

        # In case it doesn't exist, default values are used
        except FileNotFoundError:
            logger.info("No saved state found, using defaults")
            self._persistent_data = self._get_default_persistent_state()

        # In case it is corrupted, default values are used
        except json.JSONDecodeError:
            logger.error("Corrupted state file, using defaults")
            self._persistent_data = self._get_default_persistent_state()