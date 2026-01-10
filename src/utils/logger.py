#imports-------
import logging 
import queue 
import logging.handlers 
import os 
import logging.config
from typing import Any

import yaml
#--------------

def load_config() -> dict[str, Any]:
    """
    Load logging configuration from a YAML file.

    This function finds and reads the logging configuration stored in 'config/log_config.yaml'
    and returns it as a dictionary suitable for use with 'logging.config.dictConfig'.

    Returns
    -------
    dict[str, Any]
        A dictionary containing the logging configuration
        parameters loaded from the YAML file.

    Raises
    -------
    FileNotFoundError
        If the configuration file does not exist or was not found.
    yaml.YAMLError
        If the YAML file contains invalid syntax.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))
    config_path = os.path.join(project_root, 'config', 'log_config.yaml')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Config file not found at: {config_path}')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_logging() -> logging.handlers.QueueListener:
    """
    Configure and initialize the logging system with a queue-based handler.

    This function ensures the 'logs/' directory exists, loads the logging
    configuration from the YAML file, and sets up a thread-safe logging
    system using 'QueueHandler' and 'QueueListener'. The listener forwards
    log records from the queue to the original handlers defined in the
    configuration.

    Returns
    -------
    logging.handlers.QueueListener
        The QueueListener instance that runs in a background thread.
        Returning it allows the caller to later stop the listener
        gracefully and ensure all log records are flushed.

    Notes
    -------
    - The root logger's handlers are replaced with a 'QueueHandler'
    - Logging is processed asynchronously to avoid blocking in
    multi-threaded or high-throughput applications
    - Call 'listener.stop()' when shutting down the application
    to ensure all log records are flushed.
    """


    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))
    logs_path = os.path.join(project_root, 'logs')
    os.makedirs(logs_path, exist_ok = True) # Ensure logs directory exists
    
    config = load_config()
    logging.config.dictConfig(config)

    log_queue = queue.Queue()
    root = logging.getLogger()

    # Replace root handlers with a QueueHandler
    original_handlers = list(root.handlers)
    root.handlers.clear()
    queue_handler = logging.handlers.QueueHandler(log_queue)
    root.addHandler(queue_handler)

    # Listener forwards logs from queue to original handlers
    listener = logging.handlers.QueueListener(log_queue, *original_handlers, respect_handler_level=True)
    listener.start()
    return listener

