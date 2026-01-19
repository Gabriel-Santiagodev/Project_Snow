# ==============================================================================
# PROJECT SNOW - LOGGER UTILS
# ==============================================================================
# Version: 1.1
# Last Updated: January 2026
# Author: Ruben Gabriel Aguilar Santiago
# Purpose: Non-blocking logging system using QueueHandler
# ==============================================================================

import logging
import queue
import logging.handlers
import os
import logging.config
from typing import Any
import yaml

def load_config() -> dict[str, Any]:
    """
    Load logging configuration from the YAML file.
    
    Returns
    -------
    dict
        Dictionary configuration compatible with logging.config.dictConfig
    """
    # Dynamic path resolution (Works from any directory)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))
    config_path = os.path.join(project_root, 'config', 'log_config.yaml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Log config file not found at: {config_path}')
        
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_logging() -> logging.handlers.QueueListener:
    """
    Initialize the Non-Blocking Logging System.

    Why QueueListener?
    Writing to a file (SD Card) is slow. If we log directly from the 
    Camera Thread, we might drop frames while waiting for the disk.
    
    Solution:
    1. Threads write to a fast RAM Queue (QueueHandler).
    2. A background thread (QueueListener) picks up logs and writes to disk.
    
    Returns
    -------
    QueueListener
        The background listener thread (must be stopped on exit).
    """
    
    # 1. Ensure logs directory exists
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '../../'))
    logs_path = os.path.join(project_root, 'logs')
    os.makedirs(logs_path, exist_ok=True)
    
    # 2. Load basic config (Formatters, Levels)
    config = load_config()
    logging.config.dictConfig(config)

    # 3. Create the buffer Queue
    log_queue = queue.Queue()
    root = logging.getLogger()

    # 4. Save original handlers (File & Console) and clear root
    original_handlers = list(root.handlers)
    root.handlers.clear()

    # 5. Connect root to Queue (Fast write)
    queue_handler = logging.handlers.QueueHandler(log_queue)
    root.addHandler(queue_handler)

    # 6. Start the background worker (Slow write)
    # This worker moves logs from Queue -> File/Console
    listener = logging.handlers.QueueListener(
        log_queue, 
        *original_handlers, 
        respect_handler_level=True
    )
    listener.start()
    
    return listener
