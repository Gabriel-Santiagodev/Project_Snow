import time
import os
import sys
import logging
from unittest.mock import patch
import json
import threading

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../'))
sys.path.insert(0, project_root)

from src.core.service_manager import ServiceManager
from src.core.shared_state import SharedState
from src.core.base_service import BaseService

# Setup basic logging for the test
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("TestCounters")

class MockCrashingService(BaseService):
    """
    A service that intentionally crashes by reporting errors.
    """
    def _main_loop(self):
        while not self._stop_event.is_set():
            logger.info("MockCrashingService simulating an error...")
            self.report_error()
            time.sleep(1) # Wait a bit before next error

def test_counters():
    # Load original config
    import yaml
    config_path = os.path.join(project_root, 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Overwrite max thread restarts for a faster test
    config['system'] = {'max_thread_restarts': 2}
    
    # Clean up old system_state.json for a clean test
    state_file = os.path.join(project_root, 'config', 'system_state.json')
    if os.path.exists(state_file):
        os.remove(state_file)
        
    manager = ServiceManager(config)
    
    # Replace the list of services to only run our MockCrashingService
    # We must provide the correct module path
    # To do this cleanly, we can add this very module to sys.modules or use a neat trick
    # Since ServiceManager uses importlib, we will create a dummy file for it to import
    
    dummy_service_path = os.path.join(project_root, 'src', 'tests', 'dummy_crashing_service.py')
    with open(dummy_service_path, 'w') as f:
        f.write('''from src.core.base_service import BaseService
import time
import logging

class DummyCrashingService(BaseService):
    def _main_loop(self):
        while not self._stop_event.is_set():
            self.logger.info("DummyCrashingService simulating an error...")
            self.report_error()
            time.sleep(0.5)
''')
    
    # Patch _load_services_list to return our dummy service
    with patch.object(manager, '_load_services_list', return_value=['src.tests.dummy_crashing_service.DummyCrashingService']):
        # Also patch os.system so we don't actually reboot the real machine!
        with patch('os.system') as mock_os_system:
            logger.info("Starting all services (which is just our DummyCrashingService)...")
            manager.start_all_services()
            
            # Watchdog loop simulation
            # The service needs 3 consecutive errors to be "sick".
            # It generates 1 error every 0.5 sec.
            # Max thread restarts = 2.
            # So after ~1.5s, watchdog should restart it.
            # After 3 restarts (0, 1, 2 = 3 deaths?), watchdog should reboot system.
            
            for i in range(15):
                logger.info(f"--- Watchdog Check Iteration {i+1} ---")
                manager.check_health()
                
                # Check General Counter (reboot_error_count) manually
                reboot_count = manager.shared_state.get_resilience("reboot_error_count") or 0
                logger.info(f"Current General Counter (reboot_error_count): {reboot_count}")
                
                # If OS system was called, it means a reboot was triggered
                if mock_os_system.called:
                    logger.info("SYSTEM REBOOT WAS TRIGGERED BY WATCHDOG!")
                    break
                    
                time.sleep(1)
                
            # Verify the counters
            
            # Service Manager counter (restarts)
            # Service name corresponds to the class name = 'DummyCrashingService'
            restart_count = manager.restart_counts.get("DummyCrashingService", 0)
            logger.info(f"Service Manager Restart Counter: {restart_count}")
            assert restart_count > 0, "Service manager counter did not increment!"
            
            # General counter (reboot_error_count)
            reboot_error_count = manager.shared_state.get_resilience("reboot_error_count")
            logger.info(f"General Counter (persist): {reboot_error_count}")
            assert reboot_error_count == 1, "General counter did not increment to 1!"
            
            manager.stop_all()
            logger.info("TEST PASSED: Local, Service Manager, and General counters are working.")

    # Cleanup the dummy file
    if os.path.exists(dummy_service_path):
        os.remove(dummy_service_path)
    
    # Cleanup config state
    if os.path.exists(state_file):
        os.remove(state_file)

if __name__ == "__main__":
    test_counters()
