import threading
import logging
import time
import json
import importlib
import os
# Asegúrate que el import coincida con el nombre del archivo de tu compañero (shared_state.py)
from src.core.shared_satate import SharedState #Corregir esto

class ServiceManager:
    """
    El Gran Orquestador.
    Responsable de nacer, vigilar, matar y revivir a todos los servicios del robot.
    """

    def __init__(self, config):
        """
        Inicializa el Manager con la configuración global.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config 
        
        # Aquí nace el shared_state, es la unica instancia en todo el programa
        # Se pasará por referencia a todos los servicios hijos.
        # CORRECCIÓN: self.shared_state (no share_state)
        self.shared_state = SharedState()
        
        self.services = []
        self.restart_counts = {} # Diccionario para llevar el conteo de reinicios por servicio
    
    def _load_services_list(self):
        """
        Lee el JSON que define qué servicios activar.
        Retorna una lista vacía [] si falla para evitar crashes.
        """
        try:
            with open("config/services_list.json", 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.critical(f"FATAL: services_list.json could not be read: {e}")
            return [] 
    
    def start_all_services(self):
        """
        Carga dinámica (Inyección de Dependencias).
        Instancia los servicios y les entrega la Config y el SharedState.
        """
        self.logger.info("Initializing all services...")

        service_class_paths = self._load_services_list()

        for class_path in service_class_paths:
            try:
                # Ejemplo: "src.services.camera_service.CameraService"
                # rsplit separa desde la derecha (el último punto)
                module_name, class_name = class_path.rsplit(".", 1)
                
                module = importlib.import_module(module_name) # Importamos el archivo
                service_class = getattr(module, class_name)   # Obtenemos la Clase
                
                # INYECCIÓN DE DEPENDENCIAS:
                # Aquí es donde config y shared_state entran en acción.
                service = service_class(self.shared_state, self.config)
                
                service.start() # Llama a run(), que llama a _main_loop() en un hilo paralelo
                
                self.services.append(service) # Lo agregamos a la nómina
                self.restart_counts[service.name] = 0 # Iniciamos su historial limpio
                
                self.logger.info(f"SERVICE INITIALIZED: {service.name}")
            except Exception as e:
                self.logger.critical(f"SERVICE INITIALIZING ERROR {class_path}: {e}", exc_info=True)
    
    def check_health(self):
        """
        WATCHDOG (Perro Guardián).
        Implementa la lógica de recuperación en 3 capas.
        """
        # Leemos configuración o usamos 3 por defecto
        max_thread_restarts = self.config.get('system', {}).get('max_thread_restarts', 3)

        for service in self.services:
            # --- CAPA 1: Diagnóstico ---
            is_dead = not service.is_alive()
            is_sick = service.consecutive_errors >= 3

            # Solo entramos aquí si hay problemas. Si está sano, el bucle continúa.
            if is_dead or is_sick:
                reason = "DEAD" if is_dead else f"SICK ({service.consecutive_errors} errors)"
                self.logger.warning(f"WATCHDOG: The service {service.name} is {reason}.")
                
                # Aumentamos su historial de fallos
                self.restart_counts[service.name] += 1
                current_restarts = self.restart_counts[service.name]

                # --- CAPA 2 y 3: Decisión de Tratamiento ---
                if current_restarts > max_thread_restarts:
                    # CASO GRAVE: La aspirina no funcionó. Reinicio total.
                    self.logger.critical(f"{service.name} has failed {current_restarts} times. STARTING SYSTEM REBOOT.")
                    
                    # Guardamos el error en el Disco Duro (JSON)
                    # CORRECCIÓN: get_resilience (spelling)
                    current_system_reboots = self.shared_state.get_resilience("reboot_error_count") or 0
                    self.shared_state.set_resilience("reboot_error_count", current_system_reboots + 1)
                    
                    self._perform_system_reboot()
                    return # Salimos del método, ya no importa nada más
                else:
                    # CASO LEVE: Reinicio suave del hilo
                    self.logger.info(f"Applying soft restart ({current_restarts}/{max_thread_restarts})...")
                    self._restart_service(service)

    def _restart_service(self, old_service):
        """
        Mata un hilo viejo y crea uno nuevo idéntico.
        """
        # 1. Asegurar muerte del anterior
        if old_service.is_alive():
            old_service.stop()
            old_service.join(timeout=2.0)

        # 2. Sacarlo de la lista
        if old_service in self.services:
            self.services.remove(old_service)

        # 3. Resurrección (Reflection)
        # type(old_service) obtiene la clase (ej: CameraService) automáticamente
        new_service = type(old_service)(self.shared_state, self.config)
        new_service.start() 

        # 4. Actualizar lista
        self.services.append(new_service)
        # NOTA: No reiniciamos self.restart_counts a 0 aquí, 
        # porque queremos recordar que ya falló una vez.
        self.logger.info(f"Service {new_service.name} rebooted successfully.")

    def _perform_system_reboot(self):
        """
        Reinicia la Raspberry Pi.
        """
        self.logger.critical("INITIALIZING EMERGENCY SYSTEM REBOOT!!!")
        self.stop_all() 
        time.sleep(1)
        # Comando Linux
        os.system("sudo reboot")
    
    def stop_all(self):
        """
        Detiene todos los servicios limpiamente.
        """
        self.logger.info("Stopping all services...")

        # Paso 1: Señal de alto
        for service in self.services:
            service.stop()
        
        # Paso 2: Esperar a que cierren
        for service in self.services:
            service.join()
    
        self.logger.info("All services have been stopped.")
