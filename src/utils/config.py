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
        