"""Configuration parameters."""

import os

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