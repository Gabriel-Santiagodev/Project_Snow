# ==============================================================================
# PROJECT SNOW - SHARED STATE
# ==============================================================================
# Version: 2.2 
# Last Updated: February 8, 2026
# Author: Roberto Carlos Jimenez Rodriguez 
# Purpose: Thread-safe Management of Volatile and Persistent information
# ==============================================================================

import threading
import json
import logging
import queue 
from pathlib import Path
from typing import Any, Dict, Optional 

logger = logging.getLogger(__name__)

class SharedState:
    """
    Centralized Memory Bank for Project Snow.
    Manages thread-safe access to Volatile (RAM) and Persistent (SSD) data.
    """

    def __init__(self, json_path: str = "config/system_state.json"):
        self._lock = threading.Lock()
        self._json_path = Path(json_path)
        
        self._persistent_data: Dict[str, Any] = {}
        self._volatile_data: Dict[str, Any] = {}

        self._load_from_disk()
        self._initialize_volatile_data()
    
    def _get_default_persistent_state(self) -> Dict[str, Any]:
        """ Returns the factory-default state structure. """
        return {
            "system_info": {
                "first_install_date": "2026-01-11T00:00:00Z",
                "last_boot_timestamp": None,
                "total_uptime_hours": 0
            },
            "resilience": {
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
                "lastUpdated": "2026-02-08T00:00:00Z",
                "author": "Project Snow Team"
            }
        }

    def _initialize_volatile_data(self):
        """ Sets up RAM-only variables (Not saved to disk). """
        self._volatile_data = {
            "voltage": 0.0,
            "cpu_temp": 0.0,
            "camera_frame_queue": queue.Queue(),
            "person_detected": False 
        }

    def _load_from_disk(self):
        """ Loads JSON state. Falls back to defaults on failure. """
        try:
            if not self._json_path.exists():
                raise FileNotFoundError
            
            with open(self._json_path, 'r') as f:
                data = json.load(f)
                self._persistent_data = data
                logger.info("State loaded successfully from disk.")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"State load failed ({e}). Using factory defaults.")
            self._persistent_data = self._get_default_persistent_state()
            self._save_to_disk() 

    def _save_to_disk(self) -> None:
        """ Atomic-like save of persistent data to JSON. """
        try:
            with open(self._json_path, "w") as f:
                json.dump(self._persistent_data, f, indent=4)
        except Exception as e:
            logger.error(f"CRITICAL: Failed to save state to disk: {e}")   

    def get_resilience(self, key: str) -> Any:
        with self._lock:
            return self._persistent_data.get("resilience", {}).get(key)
    
    def set_resilience(self, key: str, value: Any) -> None:
        with self._lock:
            if "resilience" not in self._persistent_data:
                self._persistent_data["resilience"] = {}
            self._persistent_data["resilience"][key] = value
            self._save_to_disk()

    def get_metric(self, key: str) -> Any:
        with self._lock:
            return self._persistent_data.get("scientific_metrics", {}).get(key)
        
    def set_metric(self, key: str, value: Any) -> None:
        with self._lock:
            if "scientific_metrics" not in self._persistent_data:
                self._persistent_data["scientific_metrics"] = {}
            self._persistent_data["scientific_metrics"][key] = value
            self._save_to_disk()
    
    def get_volatile(self, key: str) -> Any:
        with self._lock:    
            return self._volatile_data.get(key)
    
    def set_volatile(self, key: str, value: Any) -> None:
        with self._lock:
            self._volatile_data[key] = value