# ==============================================================================
# PROJECT SNOW - MAIN ENTRY POINT
# ==============================================================================
# Version: 1.2
# Last Updated: January 2026
# Author: Ruben Gabriel Aguilar Santiago
# Purpose: System initialization, Gatekeeper Logic, and Keep-Alive Loop
# ==============================================================================

import time
import logging
import yaml
import os
import sys
import json
from typing import Any
from gpiozero import LED, Button
from src.utils.logger import setup_logging
from src.core.service_manager import ServiceManager

def load_config() -> dict[str, Any]:
    """
    Load system configuration from the YAML file.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))
    config_path = os.path.join(project_root, 'config', 'settings.yaml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Settings file not found at: {config_path}')
        
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def check_maintenance_mode(config: dict, logger: logging.Logger) -> None:
    """
    The Gatekeeper: Enforces Maintenance Mode.
    If 'reboot_error_count' >= 3, locks the system until physical reset.
    """
    try:
        with open("config/system_state.json", 'r') as f:
            system_state = json.load(f)
    except Exception as e:
        logger.error(f"Could not read system state, skipping maintenance check: {e}")
        return
    
    # Access using the correct key 'resilience'
    reboot_error_count = system_state.get("resilience", {}).get("reboot_error_count", 0)

    if reboot_error_count >= 3:
        # Hardware Setup
        pin_led = config['hardware']['pins']['emergency_light']
        pin_button = config['hardware']['pins']['reset_button']
        
        emergency_light = LED(pin_led)
        reset_button = Button(pin_button)
        
        emergency_light.on()
        
        # Update state in memory
        system_state['resilience']['maintenance_mode_active'] = True
        
        # Log CRITICAL state (Corrected casing and spelling)
        logger.critical(f"SYSTEM FROZEN: Maintenance Mode Active (Errors: {reboot_error_count})")
        logger.critical("Waiting for physical reset button interaction...")

        # Zombie Loop
        while True:
            if reset_button.is_pressed:
                logger.info("Reset button detected. Initializing system recovery...")
                
                # Reset counters and flags
                system_state['resilience']['reboot_error_count'] = 0
                system_state['resilience']['maintenance_mode_active'] = False
                
                # Save clean state to disk
                with open("config/system_state.json", 'w') as f:
                    json.dump(system_state, f, indent=4)
                
                emergency_light.off()
                logger.info("System unlocked. Proceeding to normal startup.")
                break
            
            time.sleep(0.1)
        return

def main():
    # 1. Start the Black Box (Logging System)
    listener = setup_logging()
    
    logger = logging.getLogger("Main")
    logger.info("Project Snow System Initializing...")

    # 2. Load the Manual (Configuration)
    try:
        config = load_config()
        logger.info("Configuration loaded successfully.")
    except Exception as e:
        logger.critical(f"FATAL: Failed to load settings.yaml: {e}")
        sys.exit(1)

    # 2.5. THE GATEKEEPER CHECK
    check_maintenance_mode(config, logger)

    # 3. Hire the Manager & 4. Start Engines
    try:
        service_manager = ServiceManager(config)
        service_manager.start_all_services()
        
        logger.info("System is Online. Entering Keep-Alive Loop.")
        
        # 5. Keep-Alive Loop
        while True:
            service_manager.check_health()
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n")
        logger.warning("User interruption detected. Shutting down system...")
        
        if 'service_manager' in locals():
            service_manager.stop_all()
            
        logger.info("System Shutdown Complete.")
        listener.stop()
        sys.exit(0)
        
    except Exception as e:
        logger.critical(f"UNEXPECTED SYSTEM CRASH: {e}", exc_info=True)
        
        if 'service_manager' in locals():
            service_manager.stop_all()
            
        listener.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
