import threading
import logging
from abc import ABC, abstractmethod

class BaseService(ABC, threading.Thread):
    """
    Abstract base class for threaded services.

    This class provides a standardized template for creating services
    that run in their own thread. Subclasses must implement the `_main_loop`
    method, which defines the core logic of the service.

    Parameters
    ----------
    shared_state : Any
        A shared object or dictionary used to exchange state between services.
    config : Any
        Configuration file containing service-specific parameters.

    Attributes
    ----------
    shared_state : Any
        Reference to the shared state object.
    config : Any
        Reference to the configuration object.
    _stop_event : threading.Event
        Event used to signal the thread to stop execution.
    logger : logging.Logger
        Logger instance scoped to the service class.
    consecutive_errors : int
        Counter tracking consecutive errors for health monitoring.
    """

    def __init__(self, shared_state, config):
        super().__init__()
        self.shared_state = shared_state
        self.config = config
        self._stop_event = threading.Event()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.consecutive_errors = 0

    def report_error(self):
        """
        Increment the consecutive error counter.

        This method should be called whenever the service encounters
        an error during execution. It allows monitoring systems to
        detect repeated failures.
        """
        self.consecutive_errors += 1

    def report_health(self):
        """
        Reset the consecutive error counter.

        This method should be called when the service successfully
        completes an operation, indicating that it is healthy again.
        """
        self.consecutive_errors = 0

    def stop(self):
        """
        Signal the service to stop execution.

        This method sets the internal stop event, which can be checked
        inside the `_main_loop` implementation to gracefully terminate
        the service.
        """
        self.logger.info("Stopping service...")
        self._stop_event.set()

    def run(self):
        """
        Start the service thread and execute its main loop.

        This method is automatically invoked when calling `start()`
        on the thread. It initializes the service, runs the main loop,
        and ensures proper logging of errors and shutdown.
        """
        self.logger.info("Initializing service...")

        try:
            self._main_loop()
        except Exception as e:
            self.logger.critical(f"Unhandled error: {e}", exc_info=True)
        finally:
            self.logger.info("Service finished.")

    @abstractmethod
    def _main_loop(self):
        """
        Abstract method defining the service's main loop.

        Subclasses must implement this method with the core logic
        of the service. The loop should periodically check
        `self._stop_event.is_set()` to determine whether to exit
        gracefully.
        """
        pass
