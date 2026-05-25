"""
Configuration and State Persistence Module.

Handles loading configuration from YAML files and persisting state to JSON.
"""

import json
import logging
import os
import yaml


# ===========================================
# Directory and File Paths
# ===========================================
# Use %LOCALAPPDATA% for Windows (standard location for per-user app data)
# Falls back to user home directory on other platforms
APP_NAME = "APEXScheduler"
if os.name == 'nt':  # Windows
    APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), APP_NAME)
else:  # Linux/Mac
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), f'.{APP_NAME.lower()}')

os.makedirs(APP_DATA_DIR, exist_ok=True)

# Get the directory where the main script is located (parent of modules)
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Log files
LOG_FILE_APPDATA = os.path.join(APP_DATA_DIR, "pmm_server.log")
LOG_FILE_LOCAL = os.path.join(SCRIPT_DIR, "pmm_server.log")
STATE_FILE = os.path.join(APP_DATA_DIR, "server_state.json")


# ===========================================
# Logging Setup
# ===========================================
def setup_logging(level=logging.INFO):
    """
    Configure logging for the PMM Server application.
    Logs to console and two files (AppData and current directory).
    
    Args:
        level: Logging level (default: INFO)
    
    Returns:
        Logger instance
    """
    log_format = '%(asctime)s | %(levelname)-7s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Create logger
    log = logging.getLogger('pmm')
    log.setLevel(level)
    
    # Prevent duplicate handlers
    if log.handlers:
        return log
    
    formatter = logging.Formatter(log_format, date_format)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
    
    # File handler - AppData (persistent)
    appdata_handler = logging.FileHandler(LOG_FILE_APPDATA, encoding='utf-8')
    appdata_handler.setLevel(level)
    appdata_handler.setFormatter(formatter)
    log.addHandler(appdata_handler)
    
    # File handler - Local directory (convenient)
    local_handler = logging.FileHandler(LOG_FILE_LOCAL, encoding='utf-8')
    local_handler.setLevel(level)
    local_handler.setFormatter(formatter)
    log.addHandler(local_handler)
    
    return log


# Create logger instance
logger = setup_logging()
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.yaml")


# ===========================================
# Configuration Loading
# ===========================================
def load_config_file(config_path=None):
    """
    Load configuration from YAML file.
    
    Args:
        config_path (str): Path to the config YAML file. Defaults to config.yaml in script dir.
    
    Returns:
        dict: Configuration dictionary, or empty dict if file not found.
    """
    if config_path is None:
        config_path = CONFIG_FILE
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                logger.info(f"Loaded config from {config_path}")
                return config
    except Exception as e:
        logger.warning(f"Could not load config file: {e}")
    return {}


def get_config(config, section, key, default=None):
    """
    Get a nested value from the config dictionary with a default fallback.
    
    Args:
        config (dict): The configuration dictionary.
        section (str): The top-level section name.
        key (str): The key within the section.
        default: Default value if not found.
    
    Returns:
        The config value or default.
    """
    return config.get(section, {}).get(key, default)


# ===========================================
# State Persistence
# ===========================================
def load_persistent_state():
    """
    Load persistent state from the state file.
    
    Returns:
        dict: State dictionary, or empty dict if not found.
    """
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                logger.debug(f"Loaded state from {STATE_FILE}")
                return state
    except Exception as e:
        logger.warning(f"Could not load state file: {e}")
    return {}


def save_persistent_state(state_data):
    """
    Save state to the state file.
    
    Args:
        state_data (dict): State dictionary to save.
    """
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state_data, f, indent=2)
        logger.debug(f"Saved state to {STATE_FILE}")
    except Exception as e:
        logger.warning(f"Could not save state file: {e}")


# ===========================================
# Singleton Config Instance
# ===========================================
# Load config once when module is imported
config = load_config_file()
