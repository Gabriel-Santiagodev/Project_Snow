# ==============================================================================
# PROJECT SNOW - MAIN ENTRY POINT
# ==============================================================================
# Version: 1.5 (single source of truth fix)
# Last Updated: March 2026
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
from src.core.shared_state import SharedState

try:
    from gpiozero import LED, Button
except ImportError:
    LED = None
    Button = None
    
from src.utils.logger import setup_logging
from src.core.service_manager import ServiceManager

def load_config(project_root: str) -> dict[str, Any]:
    """
    Load system configuration from the YAML file using absolute paths.
    """
    config_path = os.path.join(project_root, 'config', 'settings.yaml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Settings file not found at: {config_path}')
        
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def check_maintenance_mode(config: dict, logger: logging.Logger, shared_state: SharedState) -> None:
    """
    The Gatekeeper: Enforces Maintenance Mode.
    If 'reboot_error_count' >= 3, locks the system until physical reset.
    """
    
    # Access using the correct key 'resilience'
    reboot_error_count = shared_state.get_resilience("reboot_error_count") or 0

    if reboot_error_count >= 3:
        # Hardware Setup
        pin_led = config['hardware']['pins']['emergency_light']
        pin_button = config['hardware']['pins']['reset_button']
        
        if LED and Button:
            emergency_light = LED(pin_led)
            reset_button = Button(pin_button)
            emergency_light.on()
        else:
            emergency_light = None
            reset_button = None
            logger.warning("gpiozero not installed. Running in laptop simulated mode.")
        
        # Update state in memory
        shared_state.set_resilience("maintenance_mode_active", True)
        
        # Log CRITICAL state
        logger.critical(f"SYSTEM FROZEN: Maintenance Mode Active (Errors: {reboot_error_count})")
        logger.critical("Waiting for physical reset button interaction...")

        # Zombie Loop
        while True:
            # Check button press if available, else use a keyboard fallback prompt
            is_pressed = False
            if reset_button is not None:
                is_pressed = reset_button.is_pressed
            else:
                # Laptop simulated flow
                val = input("SIMULATED HARDWARE: Press ENTER to simulate reset button... ")
                is_pressed = True

            if is_pressed:
                logger.info("Reset button detected. Initializing system recovery...")
                
                # Reset counters and flags
                shared_state.set_resilience("reboot_error_count", 0)
                shared_state.set_resilience("maintenance_mode_active", False)
                
                if emergency_light is not None:
                    emergency_light.off()
                logger.info("System unlocked. Proceeding to normal startup.")
                break
            
            time.sleep(0.1)
        return

def main():
    # 0. Global Path Resolution
    # This prevents pathing errors no matter where the user executes the script from
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))
    state_path = os.path.join(project_root, "config", "system_state.json")

    shared_state = SharedState(state_path)

    # 1. Start the Black Box (Logging System)
    listener = setup_logging(project_root)
    
    logger = logging.getLogger("Main")
    logger.info("Project Snow System Initializing...")

    # 2. Load the Manual (Configuration)
    try:
        config = load_config(project_root)
        logger.info("Configuration from settings.yaml loaded successfully.")
    except Exception as e:
        logger.critical(f"FATAL: Failed to load settings.yaml: {e}")
        listener.stop()
        sys.exit(1)

    # 2.5. THE GATEKEEPER CHECK
    check_maintenance_mode(config, logger,shared_state)

    # 3. Hire the Manager & 4. Start Engines
    try:
        service_manager = ServiceManager(config, shared_state, project_root)
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