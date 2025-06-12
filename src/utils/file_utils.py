"""File utility functions."""

import os
from typing import List, Optional


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