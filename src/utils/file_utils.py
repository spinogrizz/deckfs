"""File utility functions."""

import os
from typing import List, Optional, Dict
from . import logger


def find_file(directory: str, prefix: str, extensions: List[str]) -> Optional[str]:
    """Find file by prefix and supported extensions.
    
    Args:
        directory: Directory to search in
        prefix: File prefix to look for
        extensions: List of supported extensions (without dots)
        
    Returns:
        Optional[str]: Full path to found file or None
    """
    if not os.path.isdir(directory):
        return None
        
    for ext in extensions:
        file_path = os.path.join(directory, f"{prefix}.{ext}")
        if os.path.isfile(file_path):
            return file_path
    return None


def find_any_file(directory: str, prefix: str) -> Optional[str]:
    """Find file by prefix (any extension).
    
    Args:
        directory: Directory to search in
        prefix: File prefix to look for
        
    Returns:
        Optional[str]: Full path to found file or None
    """
    if not os.path.isdir(directory):
        return None
        
    for filename in os.listdir(directory):
        if filename.startswith(f"{prefix}."):
            full_path = os.path.join(directory, filename)
            if os.path.isfile(full_path) or os.path.islink(full_path):
                return full_path
    return None


def extract_button_id_from_path(file_path: str, config_dir: str, max_buttons: int) -> int:
    """Extract button ID from file or directory path.
    
    Args:
        file_path: File or directory path
        config_dir: Configuration directory path
        max_buttons: Maximum number of buttons on device
        
    Returns:
        int: Button ID (1-based) or 0 if not found
    """
    try:
        if os.path.isfile(file_path) or '.' in os.path.basename(file_path):
            dir_path = os.path.dirname(file_path)
        else:
            dir_path = file_path
            
        rel_path = os.path.relpath(dir_path, config_dir)
        dir_name = rel_path.split(os.sep)[0]  # Get first part of relative path
        
        if len(dir_name) >= 2 and dir_name[:2].isdigit():
            button_id = int(dir_name[:2])
            if 1 <= button_id <= max_buttons:
                return button_id
    except Exception as e:
        logger.error(f"Error extracting button ID from {file_path}: {e}")
        
    return 0


def find_button_directories(config_dir: str, max_buttons: int) -> Dict[int, str]:
    """Find all button directories.
    
    Args:
        config_dir: Configuration directory path
        max_buttons: Maximum number of buttons on device
    
    Returns:
        Dict[int, str]: Mapping of button ID to directory name
    """
    button_dirs = {}
    
    if not os.path.isdir(config_dir):
        return button_dirs
        
    for item in os.listdir(config_dir):
        item_path = os.path.join(config_dir, item)
        if os.path.isdir(item_path) and len(item) >= 2 and item[:2].isdigit():
            button_id = int(item[:2])
            if 1 <= button_id <= max_buttons:
                button_dirs[button_id] = item
                
    return button_dirs


def find_button_working_dir(config_dir: str, button_id: int) -> Optional[str]:
    """Find working directory for button.
    
    Args:
        config_dir: Configuration directory path
        button_id: Button ID (1-based)
        
    Returns:
        Optional[str]: Full path to button working directory or None
    """
    if not os.path.isdir(config_dir):
        return None
        
    button_prefix = f"{button_id:02d}"
    
    for item in os.listdir(config_dir):
        if item.startswith(button_prefix) and os.path.isdir(os.path.join(config_dir, item)):
            return os.path.join(config_dir, item)
            
    return None