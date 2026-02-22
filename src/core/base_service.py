# ==============================================================================
# PROJECT SNOW - BASE SERVICE
# ==============================================================================
# Version: 1.0
# Last Updated: January 2026
# Author: Ruben Gabriel Aguilar Santiago
# Purpose: Template for all threaded services (Camera, Audio, etc.)
# ==============================================================================

import threading
import logging
from abc import ABC, abstractmethod

class BaseService(ABC, threading.Thread):
    """
    Abstract base class for threaded services.

    This class provides a standardized template for creating services
    that run in their own thread. It handles the lifecycle (start/stop),
    error catching, and health reporting for the Watchdog.

    Parameters
    ----------
    shared_state : SharedState
        The central thread-safe data store for inter-service communication.
    config : dict
        Configuration dictionary containing service-specific parameters.
    """

    def __init__(self, shared_state, config):
        # Initialize the parent Thread class (Crucial for parallelism)
        super().__init__()
        
        # Dependency Injection: Receive tools from the Manager
        self.shared_state = shared_state
        self.config = config
        
        # Thread Control: Safe flag to stop execution without killing the process
        self._stop_event = threading.Event()
        
        # Observability: Dedicated logger for this specific service
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Health Monitoring: Counters for the Watchdog Logic
        self.consecutive_errors = 0
        self.name = self.__class__.__name__

    def report_error(self):
        """
        Signals that the service encountered a logical error.
        
        Usage: Call this inside _main_loop when something goes wrong (e.g., empty frame).
        Effect: Increases the 'sickness' level for the Watchdog.
        """
        self.consecutive_errors += 1

    def report_health(self):
        """
        Signals that the service is working correctly.
        Usage: Call this at the end of a successful loop iteration.
        Effect: Resets the 'sickness' level to 0 (Healthy).
        """
        
        self.consecutive_errors = 0

    def stop(self):
        """
        Thread-safe method to stop the service.
        
        This does NOT kill the thread immediately. It sets a flag that 
        the _main_loop must check to exit gracefully.
        """
        self.logger.info("Stopping service signal received...")
        self._stop_event.set()

    def run(self):
        """
        The Main Entry Point for the Thread.
        
        WARNING: Do not override this method in child classes.
        This wrapper provides the 'Safety Net' (try-except) to prevent
        a single service crash from bringing down the entire robot.
        """
        self.logger.info("Initializing service thread...")

        try:
            # Execute the child's specific logic
            self._main_loop()
        except Exception as e:
            # CATCH-ALL: If the child code crashes, we catch it here.
            # This allows the Manager to see the thread is dead and revive it.
            self.logger.critical(f"UNHANDLED CRASH in {self.name}: {e}", exc_info=True)
        finally:
            self.logger.info("Service thread finished.")

    @abstractmethod
    def _main_loop(self):
        """
        Abstract method where the specific business logic lives.

        Rules for Implementation:
        1. Must use a loop: `while not self._stop_event.is_set():`
        2. Must call `self.report_error()` on failure.
        3. Must call self.report_health() on success.
        """
        pass