import logging
import time
import os
import sys
import pytest

# Configure project root path to allow imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, PROJECT_ROOT)

from src.utils.logger import setup_logging

# Configuration Constants
MESSAGE_COUNT = 1000
PERFORMANCE_THRESHOLD_SEC = 0.1

@pytest.fixture
def async_logger():
    """
    Pytest Fixture: Initializes the non-blocking logger before the test,
    and guarantees the listener stops gracefully after the test.
    """
    listener = setup_logging(PROJECT_ROOT)
    
    if not listener:
        pytest.fail("Failed to initialize logging listener.")
        
    logger = logging.getLogger("TestLogger")
    
    yield logger  # Provide the logger to the test function
    
    # --- TEARDOWN ---
    # This runs automatically after the test finishes or if it fails
    listener.stop()

def test_logger_non_blocking_performance(async_logger):
    """
    Performance Test: Ensures the QueueHandler prevents I/O blocking.
    Queuing 1,000 messages must take less than the performance threshold.
    """
    start_time = time.time()
    
    for i in range(MESSAGE_COUNT):
        # These calls should be instantaneous if the QueueHandler is working
        async_logger.debug(f"Stress test message sequence: {i}")
        
    duration = time.time() - start_time
    
    # Pytest native assertion (Replaces the manual IF/ELSE prints)
    assert duration < PERFORMANCE_THRESHOLD_SEC, (
        f"SYSTEM SLOWDOWN DETECTED: Logger blocking main thread. "
        f"Took {duration:.4f}s (Threshold: {PERFORMANCE_THRESHOLD_SEC}s)"
    )

def test_logger_levels(async_logger):
    """
    Functionality Test: Ensures the logger methods don't crash the system.
    """
    try:
        async_logger.debug("Debug check: Queueing debug message.")
        async_logger.info("Info check: Queueing info message.")
        async_logger.warning("Warning check: Queueing warning message.")
    except Exception as e:
        pytest.fail(f"Logger raised an unexpected exception: {e}")