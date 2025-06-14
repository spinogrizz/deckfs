"""Configuration parameters and manager."""

import os
import yaml
from typing import Dict, Any, Optional
from . import logger

# Main configuration directory
CONFIG_DIR = os.path.expanduser("~/.local/streamdeck")

# Supported image formats
SUPPORTED_IMAGE_FORMATS = ['.png', '.jpg', '.jpeg']

# Supported script types
SUPPORTED_SCRIPTS = {
    'sh': ['bash'],
    'py': ['python3'],
    'js': ['node']
}

# Default device settings
DEFAULT_BRIGHTNESS = 50
DEFAULT_DEBOUNCE_INTERVAL = 0.1

# Default configuration values
DEFAULT_CONFIG = {
    'brightness': DEFAULT_BRIGHTNESS,
    'debounce_interval': DEFAULT_DEBOUNCE_INTERVAL
}


class ConfigManager:
    """Manages YAML configuration file loading and default values."""
    
    def __init__(self, config_dir: str = CONFIG_DIR):
        """Initialize config manager.
        
        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, 'config.yaml')
        self._config_cache: Optional[Dict[str, Any]] = None
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file or return defaults.
        
        Returns:
            Dict[str, Any]: Configuration dictionary with defaults applied
        """
        if self._config_cache is not None:
            return self._config_cache
            
        config = DEFAULT_CONFIG.copy()
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    user_config = yaml.safe_load(f) or {}
                    
                # Update only defined settings, keep defaults for others
                for key, value in user_config.items():
                    if key in DEFAULT_CONFIG:
                        config[key] = value
                        
                logger.info(f"Configuration loaded from {self.config_path}")
                        
            except Exception as e:
                logger.error(f"Error loading config file {self.config_path}: {e}")
                logger.info("Using default configuration")
        else:
            logger.warn("No config.yaml found, using default configuration")
            
        self._config_cache = config
        return config
        
    def get_brightness(self) -> int:
        """Get brightness setting.
        
        Returns:
            int: Brightness value (0-100)
        """
        config = self.load_config()
        brightness = config.get('brightness', DEFAULT_BRIGHTNESS)
        return max(0, min(100, int(brightness)))  # Clamp to 0-100
        
    def get_debounce_interval(self) -> float:
        """Get debounce interval setting.
        
        Returns:
            float: Debounce interval in seconds
        """
        config = self.load_config()
        interval = config.get('debounce_interval', DEFAULT_DEBOUNCE_INTERVAL)
        return max(0.01, float(interval))  # Minimum 0.01 seconds
        
    def reload_config(self, deck_device=None, debouncer=None):
        """Reload configuration from file and apply all settings."""
        logger.info("Configuration file changed, reloading...")
        
        # Clear cache to force reload
        self._config_cache = None
        
        # Apply all settings 
        self.apply_all_settings(deck_device, debouncer)
    
    
    def apply_all_settings(self, deck_device=None, debouncer=None):
        """Apply all current configuration settings to provided components."""
        if deck_device:
            try:
                brightness = self.get_brightness()
                deck_device.set_brightness(brightness)
            except Exception as e:
                logger.error(f"Error applying brightness: {e}")
        
        if debouncer:
            try:
                new_interval = self.get_debounce_interval()
                debouncer.debounce_interval = new_interval
            except Exception as e:
                logger.error(f"Error applying debounce interval: {e}")
    
    def load_env_vars(self) -> Dict[str, str]:
        """Load environment variables from env.local file.
        
        Returns:
            Dict[str, str]: Environment variables as key-value pairs
        """
        env_vars = {}
        env_file_path = os.path.join(self.config_dir, "env.local")
        
        if not os.path.exists(env_file_path):
            return env_vars
            
        try:
            with open(env_file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                        
                    # Parse KEY=VALUE pairs
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Skip if key is empty
                        if not key:
                            logger.debug(f"Invalid line in env.local:{line_num}: {line}")
                            continue
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                            
                        env_vars[key] = value
                    else:
                        logger.debug(f"Invalid line in env.local:{line_num}: {line}")
                        
        except Exception as e:
            logger.error(f"Error reading env.local file: {e}")
            
        return env_vars


# Global ConfigManager instance - module-level singleton
_config: Optional[ConfigManager] = None
_config_dir: Optional[str] = None


def get_config(config_dir: str = None) -> ConfigManager:
    """Get global config instance, creating it if necessary.
    
    Args:
        config_dir: Configuration directory path. If None, uses default CONFIG_DIR.
                   Only used when creating the instance for the first time.
    
    Returns:
        ConfigManager: Global ConfigManager instance
    """
    global _config, _config_dir
    
    # If config doesn't exist yet, create it
    if _config is None:
        if config_dir is None:
            config_dir = CONFIG_DIR
        _config_dir = config_dir
        _config = ConfigManager(config_dir)
    # If config exists but different config_dir requested, recreate
    elif config_dir is not None and config_dir != _config_dir:
        _config_dir = config_dir
        _config = ConfigManager(config_dir)
    
    return _config


def reset_config():
    """Reset global config instance. Used for testing."""
    global _config, _config_dir
    _config = None
    _config_dir = None


# Alias for cleaner access
config = get_config
        