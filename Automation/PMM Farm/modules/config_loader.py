"""
Configuration and State Persistence Module.

Handles loading configuration from YAML files and persisting state to JSON.
"""

import json
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
STATE_FILE = os.path.join(APP_DATA_DIR, "server_state.json")

# Get the directory where the main script is located (parent of modules)
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
                print(f"📂 Loaded config from {config_path}")
                return config
    except Exception as e:
        print(f"⚠️ Could not load config file: {e}")
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
                print(f"📂 Loaded state from {STATE_FILE}")
                return state
    except Exception as e:
        print(f"⚠️ Could not load state file: {e}")
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
        print(f"💾 Saved state to {STATE_FILE}")
    except Exception as e:
        print(f"⚠️ Could not save state file: {e}")


# ===========================================
# Singleton Config Instance
# ===========================================
# Load config once when module is imported
config = load_config_file()
