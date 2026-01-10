import logging
import time
import os
import sys

# Configure project root path to allow imports from 'src' when running from 'src/tests'
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(PROJECT_ROOT)

from src.utils.logger import setup_logging

# Configuration Constants
MESSAGE_COUNT = 1000
PERFORMANCE_THRESHOLD_SEC = 0.1

def run_stress_test(logger: logging.Logger, count: int) -> float:
    """
    Execute a high-volume logging loop to measure execution time.

    Parameters
    ----------
    logger : logging.Logger
        The logger instance used to dispatch messages.
    count : int
        The number of log records to generate.

    Returns
    -------
    float
        The total time elapsed in seconds during the logging loop.
    """
    print(f"\n--- Starting Stress Test ({count} messages) ---")
    
    start_time = time.time()
    
    for i in range(count):
        # These calls should be instantaneous if the QueueHandler is working
        logger.debug(f"Stress test message sequence: {i}")
        
    end_time = time.time()
    return end_time - start_time

def main() -> None:
    """
    Execute the logger verification suite.

    This script validates the logging architecture by performing:
    1. Handler Verification: Ensures the system initializes correctly.
    2. Level Filtering: Emits logs at different levels for manual verification.
    3. Performance Analysis: Measures main-thread blocking time to confirm
    asynchronous behavior (QueueHandler efficacy).
    """
    print("--- Logger Integration Test Initialized ---")

    # 1. System Initialization
    listener = setup_logging()
    
    if not listener:
        print("[ERROR] Failed to initialize logging listener.")
        return

    try:
        logger = logging.getLogger("TestLogger")

        # 2. Level Filtering Test
        # Expected: DEBUG in file only, INFO/WARNING in both console and file.
        logger.debug("Debug check: Should appear in app.log ONLY.")
        logger.info("Info check: Should appear in console AND app.log.")
        logger.warning("Warning check: Should appear in console AND app.log.")

        # 3. Performance Stress Test
        duration = run_stress_test(logger, MESSAGE_COUNT)
        
        print(f"--- Test Completed ---")
        print(f"Time elapsed: {duration:.4f} seconds")

        if duration < PERFORMANCE_THRESHOLD_SEC:
            print(f"✅ [PASS] System is NON-BLOCKING (Duration < {PERFORMANCE_THRESHOLD_SEC}s).")
            print("   Log records were successfully queued in memory.")
        else:
            print(f"⚠️ [FAIL] System appears SLOW (Duration >= {PERFORMANCE_THRESHOLD_SEC}s).")
            print("   Main thread execution was significantly delayed.")

    finally:
        # 4. Graceful Shutdown
        # Ensures logs are flushed to disk even if an error occurs above.
        print("\nStopping listener and flushing queue...")
        listener.stop()
        print("Test sequence finished. Please verify 'logs/app.log'.")

if __name__ == "__main__":
    main()