from src.core.base_service import BaseService
import time
import random

class SensorsService(BaseService):
    def __init__(self, shared_state, config):
        super().__init__(shared_state, config)

    def _main_loop(self):
        self.logger.info("Sensor Service Initialized (Simulated Hardware Mode).")
        
        # Initial plausible values
        voltage = 12.5
        cpu_temp = 45.0
        
        while not self._stop_event.is_set():
            # Add random noise to simulate fluctuating reads
            voltage += random.uniform(-0.1, 0.1)
            voltage = max(10.0, min(voltage, 14.4)) # Clamp between 10V and 14.4V
            
            cpu_temp += random.uniform(-1.0, 1.0)
            cpu_temp = max(30.0, min(cpu_temp, 85.0)) # Clamp between 30C and 85C
            
            self.shared_state.set_volatile("voltage", round(voltage, 2))
            self.shared_state.set_volatile("cpu_temp", round(cpu_temp, 2))
            
            # Occasionally log values to show it's working
            if random.random() < 0.2: # 20% chance per second
                temp = self.shared_state.get_volatile("cpu_temp")
                volt = self.shared_state.get_volatile("voltage")
                self.logger.info(f"Hardware Status -> Voltage: {volt}V | CPU Temp: {temp}C")
            
            self.report_health()
            
            # Read sensors once every second
            time.sleep(1)
