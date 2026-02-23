# ==============================================================================
# PROJECT SNOW - SERVICE MANAGER
# ==============================================================================
# Version: 1.0
# Last Updated: January 2026
# Author: Ruben Gabriel Aguilar Santiago
# Purpose: Orchestrator for all robotic micro-services (Start, Monitor, Heal)
# ==============================================================================

import logging
import time
import json
import importlib
import os
from src.core.shared_state import SharedState

class ServiceManager:
    """
    The Grand Orchestrator of the System.
    
    This class implements the 'Manager' design pattern. It is responsible for:
    1. Loading services dynamically from a JSON configuration.
    2. Injecting dependencies (Config & SharedState) into those services.
    3. Monitoring thread health (Watchdog).
    4. Executing recovery protocols (Soft Restart vs Hard Reboot).

    Parameters
    ----------
    config : dict
        The global configuration dictionary loaded from 'settings.yaml'.

    Attributes
    ----------
    shared_state : SharedState
        The single source of truth for thread-safe data exchange.
    services : list
        A list of active service objects (Threads).
    restart_counts : dict
        A scorecard tracking how many times each service has been restarted.
    """

    def __init__(self, config):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config 
        
        # Initialize the Central Nervous System (Shared State)
        # This is the ONLY instance in the entire program.
        self.shared_state = SharedState()
        
        self.services = []
        
        # Tracks service stability history
        # Format: {'CameraService': 0, 'AudioService': 2}
        self.restart_counts = {} 
    
    def _load_services_list(self):
        """
        Read the list of active services from JSON.
        
        Returns
        -------
        list
            A list of strings representing class paths (e.g., "src.hardware.camera...").
            Returns an empty list [] on failure to prevent system crash.
        """
        try:
            with open("config/services_list.json", 'r') as f:
                data = json.load(f)
                return data.get("services", [])
        except Exception as e:
            self.logger.critical(f"FATAL: services_list.json could not be read: {e}")
            return [] 
    
    def start_all_services(self):
        """
        Initialize and start all services defined in the configuration.

        This method uses Python Reflection to dynamically import and instantiate
        classes based on string names. This allows adding new hardware without
        modifying the Manager's code.

        Notes
        -----
        Dependency Injection happens here: We pass 'self.shared_state' and 
        'self.config' to every new service.
        """
        self.logger.info("Initializing all services...")

        service_class_paths = self._load_services_list()

        for class_path in service_class_paths:
            try:
                # Example: "src.hardware.camera_service.CameraService"
                # rsplit splits from the right to separate Module from Class
                module_name, class_name = class_path.rsplit(".", 1)
                
                # Dynamic Import (Reflection)
                module = importlib.import_module(module_name)
                service_class = getattr(module, class_name)
                
                # Instantiation & Injection
                service = service_class(self.shared_state, self.config)
                
                # Start the Thread (calls run() -> _main_loop())
                service.start()
                
                # Add to payroll
                self.services.append(service)
                self.restart_counts[service.name] = 0
                
                self.logger.info(f"SERVICE INITIALIZED: {service.name}")
            except Exception as e:
                # If one service fails, we log it but continue starting others
                self.logger.critical(f"SERVICE INITIALIZING ERROR {class_path}: {e}", exc_info=True)
    
    def check_health(self):
        """
        Main Watchdog Routine (The Doctor).
        
        This method checks if any service is 'Dead' (crashed) or 'Sick' (logical errors).
        It implements a Tiered Recovery Strategy:
        - Tier 1: Soft Restart (Restart only the thread).
        - Tier 2: Hard Reboot (Restart the entire Raspberry Pi).

        Notes
        -----
        This should be called periodically from the main loop (e.g., every 5s).
        """
        # Read limit from config or default to 3
        max_thread_restarts = self.config.get('system', {}).get('max_thread_restarts', 3)

        for service in self.services:
            # --- TIER 1: Diagnosis ---
            is_dead = not service.is_alive()
            is_sick = service.consecutive_errors >= 3

            # Only intervene if there is a problem
            if is_dead or is_sick:
                reason = "DEAD" if is_dead else f"SICK ({service.consecutive_errors} errors)"
                self.logger.warning(f"WATCHDOG: The service {service.name} is {reason}.")
                
                # Increment historical restart count
                self.restart_counts[service.name] += 1
                current_restarts = self.restart_counts[service.name]

                # --- TIER 2: Treatment Decision ---
                if current_restarts > max_thread_restarts:
                    # CASE CRITICAL: 'Aspirin' didn't work. System is unstable.
                    self.logger.critical(f"{service.name} has failed {current_restarts} times. STARTING SYSTEM REBOOT.")
                    
                    # Persist the error count to disk (JSON) so we remember after reboot
                    try:
                        current_system_reboots = self.shared_state.get_resilience("reboot_error_count") or 0
                        self.shared_state.set_resilience("reboot_error_count", current_system_reboots + 1)
                        total_restarts = self.shared_state.get_metric("total_system_restarts") or 0
                        self.shared_state.set_metric("total_system_restarts", total_restarts + 1)
                    except:
                        pass        
                    self._perform_system_reboot()
                    return # Exit immediately to allow reboot
                else:
                    # CASE MILD: Apply 'Aspirin' (Restart the thread)
                    self.logger.info(f"Applying soft restart ({current_restarts}/{max_thread_restarts})...")
                    self._restart_service(service)

    def _restart_service(self, old_service):
        """
        Soft Restart: Replaces a broken thread with a fresh one.
        
        Parameters
        ----------
        old_service : BaseService
            The instance of the service that has failed or is sick.
        """
        # 1. Euthanasia: Ensure the old thread is stopped
        if old_service.is_alive():
            old_service.stop()
            old_service.join(timeout=2.0)

        # 2. Cleanup: Remove from active list
        if old_service in self.services:
            self.services.remove(old_service)

        # 3. Resurrection: Create new instance using the same class
        # type(old_service) gives us the class (e.g. CameraService) without importing it
        new_service = type(old_service)(self.shared_state, self.config)
        new_service.start() 

        # 4. Re-hiring: Add to active list
        self.services.append(new_service)
        
        # Note: We do NOT reset self.restart_counts here. We want to remember the failure.
        self.logger.info(f"Service {new_service.name} rebooted successfully.")

    def _perform_system_reboot(self):
        """
        Hard Reboot: Triggers a hardware restart via OS command.
        Used as a last resort when threads cannot recover.
        """
        self.logger.critical("INITIALIZING EMERGENCY SYSTEM REBOOT!!!")
        self.stop_all() 
        time.sleep(1)
        # Linux Command to restart
        os.system("sudo reboot")
    
    def stop_all(self):
        """
        Graceful Shutdown Protocol.
        Signals all threads to stop and waits for them to close files/connections.
        """
        self.logger.info("Stopping all services...")

        # Step 1: Raise the Stop Flag
        for service in self.services:
            service.stop()
        
        # Step 2: Wait for closure (Join)
        for service in self.services:
            service.join()
    
        self.logger.info("All services have been stopped.")
