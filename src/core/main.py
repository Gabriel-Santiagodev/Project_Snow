# ==============================================================================
# PROJECT SNOW - MAIN ENTRY POINT
# ==============================================================================
# Version: 1.0
# Last Updated: January 2026
# Author: Ruben Gabriel Aguilar Santiago
# Purpose: System initialization and Keep-Alive Loop
# ==============================================================================

import time
import logging
import yaml
import os
import sys
from typing import Any
from src.utils.logger import setup_logging
from src.core.service_manager import ServiceManager

def load_config() -> dict[str, Any]:
    """
    Load system configuration from the YAML file.
    
    Returns
    -------
    dict
        Dictionary containing global settings from 'settings.yaml'.
    """
    # Dynamic path resolution (Works from any directory)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))
    config_path = os.path.join(project_root, 'config', 'settings.yaml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Settings file not found at: {config_path}')
        
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    # 1. Start the Black Box (Logging System)
    # We capture the listener to stop it gracefully later.
    listener = setup_logging()
    
    # Create a local logger for startup messages
    logger = logging.getLogger("Main")
    logger.info("Project Snow System Initializing...")

    # 2. Load the Manual (Configuration)
    try:
        config = load_config()
        logger.info("Configuration loaded successfully.")
    except Exception as e:
        # If we can't read settings, we can't function. Abort.
        logger.critical(f"FATAL: Failed to load settings.yaml: {e}")
        sys.exit(1)

    # 3. Hire the Manager & 4. Start Engines
    try:
        service_manager = ServiceManager(config)
        service_manager.start_all_services()
        
        logger.info("System is Online. Entering Keep-Alive Loop.")
        
        # 5. Keep-Alive Loop (The Pulse)
        while True:
            service_manager.check_health()
            time.sleep(5) # Breathe every 5 seconds
            
    except KeyboardInterrupt:
        # 6. Graceful Shutdown (Ctrl+C)
        print("\n") # Newline for clean output
        logger.warning("User interruption detected. Shutting down system...")
        
        service_manager.stop_all()
        logger.info("System Shutdown Complete.")
        
        # Stop the logging listener last so we capture the shutdown logs
        listener.stop()
        sys.exit(0)
        
    except Exception as e:
        # Safety net for unexpected crashes in the main loop
        logger.critical(f"UNEXPECTED SYSTEM CRASH: {e}", exc_info=True)
        if 'service_manager' in locals():
            service_manager.stop_all()
        listener.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
