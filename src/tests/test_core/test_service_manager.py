import pytest
import time
from unittest.mock import MagicMock, patch
from src.core.service_manager import ServiceManager
from src.core.base_service import BaseService

class WatchdogDummyService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)
        self.name = "WatchdogDummyService"
    
    def _main_loop(self):
        while not self._stop_event.is_set():
            time.sleep(0.01)

@pytest.fixture
def manager(mock_config, mocker):
    """Provides a fresh ServiceManager instance with mocked SharedState."""
    mock_shared_state = MagicMock()
    mock_shared_state.get_resilience.return_value = 0
    mock_shared_state.get_metric.return_value = 0
    
    mocker.patch('src.core.service_manager.SharedState', return_value=mock_shared_state)
    return ServiceManager(mock_config)

def test_load_services_list(manager, mocker):
    """Test loading services from config json."""
    mock_open = mocker.mock_open(read_data='{"services": ["src.dummy.DummyService"]}')
    mocker.patch('builtins.open', mock_open)
    
    services = manager._load_services_list()
    assert services == ["src.dummy.DummyService"]

def test_start_all_services(manager, mocker):
    """Test dynamic importing and starting of services."""
    mocker.patch.object(manager, '_load_services_list', return_value=["dummy_module.WatchdogDummyService"])
    
    # Mock importlib to return our WatchdogDummyService class
    mock_module = MagicMock()
    mock_module.WatchdogDummyService = WatchdogDummyService
    mocker.patch('importlib.import_module', return_value=mock_module)
    
    manager.start_all_services()
    
    assert len(manager.services) == 1
    assert manager.services[0].name == "WatchdogDummyService"
    assert "WatchdogDummyService" in manager.restart_counts
    
    manager.stop_all()

@patch('os.system') # Prevent actual reboot during test
def test_watchdog_healthy(mock_os, manager):
    """Test watchdog with a healthy service."""
    service = WatchdogDummyService(manager.shared_state, manager.config)
    service.start()
    manager.services.append(service)
    manager.restart_counts[service.name] = 0
    
    manager.check_health()
    
    assert manager.restart_counts[service.name] == 0
    assert service in manager.services
    mock_os.assert_not_called()
    
    manager.stop_all()

@patch('os.system')
def test_watchdog_soft_restart(mock_os, manager):
    """Test watchdog soft restarts a sick service."""
    service = WatchdogDummyService(manager.shared_state, manager.config)
    service.start()
    manager.services.append(service)
    manager.restart_counts[service.name] = 0
    
    # Make the service sick
    service.consecutive_errors = 3
    
    # Watchdog should restart it (max restarts is 3 in mock_config)
    manager.check_health()
    
    assert manager.restart_counts[service.name] == 1
    # Original service is removed, new one is added
    assert service not in manager.services
    assert len(manager.services) == 1
    new_service = manager.services[0]
    
    assert new_service.is_alive()
    mock_os.assert_not_called()
    
    manager.stop_all()

@patch('os.system')
def test_watchdog_hard_reboot(mock_os, manager):
    """Test watchdog triggers a hard reboot if restarts hit max limit."""
    service = WatchdogDummyService(manager.shared_state, manager.config)
    service.start()
    manager.services.append(service)
    # Exceed max restarts (limit is 3)
    manager.restart_counts[service.name] = 4
    
    # Make the service sick
    service.consecutive_errors = 3
    
    manager.check_health()
    
    # Wait for the stop_all to signal
    time.sleep(0.1)
    
    # OS system should have been called to reboot
    mock_os.assert_called_once_with("sudo reboot")
    
    # Shared state counter should increment
    manager.shared_state.set_resilience.assert_called_with("reboot_error_count", 1)
    manager.shared_state.set_metric.assert_called_with("total_system_restarts", 1)
    
    manager.stop_all()