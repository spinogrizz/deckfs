"""File event handler for monitoring image changes."""

import os
import threading
from watchdog.events import FileSystemEventHandler

from ..utils.config import CONFIG_DIR


class ImageChangeHandler(FileSystemEventHandler):
    """Image file change handler."""
    
    def __init__(self, device_manager, script_manager=None):
        """Initialize handler.
        
        Args:
            device_manager: Stream Deck device manager
            script_manager: Script manager for background/update scripts
        """
        self.device_manager = device_manager
        self.script_manager = script_manager
        
    def process_image_change(self, event_path, event_type):
        """Process potential image change.
        
        Args:
            event_path: Event file path
            event_type: Event type
        """
        if os.path.isdir(event_path):
            return
            
        filename = os.path.basename(event_path)
        dirname = os.path.dirname(event_path)
        
        # Track changes to image.* files (including symlinks)
        if not filename.startswith("image"):
            print(f"[SKIP] File {filename} doesn't start with 'image'")
            return
            
        # Calculate button index from folder name
        rel_path = os.path.relpath(dirname, CONFIG_DIR)
        folder = rel_path if rel_path != '.' else os.path.basename(dirname)
        
        # Extract first two digits from folder name (e.g., "01_light" -> "01")
        try:
            if len(folder) >= 2 and folder[:2].isdigit():
                key_index = int(folder[:2]) - 1
            else:
                raise ValueError("Folder name doesn't start with two digits")
        except ValueError:
            print(f"[ERROR] Cannot determine button number from folder: {folder}")
            return
            
        print(f"[UPDATE] Detected {event_type} for {filename} in folder {folder}")
        
        # Add small delay for proper symlink handling
        threading.Timer(0.1, self.device_manager.update_key_image, args=[key_index]).start()
        
    def process_script_change(self, event_path, event_type):
        """Process script file change.
        
        Args:
            event_path: Event file path
            event_type: Event type
        """
        # Ignore 'opened' and 'closed' events to prevent loops from script execution.
        # These events are fired when scripts are executed, but don't signify a change.
        if event_type not in ['modified', 'created', 'moved', 'deleted']:
            return
            
        if not self.script_manager or os.path.isdir(event_path):
            return
            
        filename = os.path.basename(event_path)
        dirname = os.path.dirname(event_path)
        
        # Check if it's a background or update script
        script_type = None
        if filename.startswith("background."):
            script_type = "background"
        elif filename.startswith("update."):
            script_type = "update"
        else:
            return
            
        # Calculate button directory from folder name
        rel_path = os.path.relpath(dirname, CONFIG_DIR)
        folder = rel_path if rel_path != '.' else os.path.basename(dirname)
        
        # Extract button directory name (e.g., "01_toggle_mute")
        try:
            if len(folder) >= 2 and folder[:2].isdigit():
                button_dir = folder
            else:
                raise ValueError("Folder name doesn't start with two digits")
        except ValueError:
            print(f"[ERROR] Cannot determine button directory from folder: {folder}")
            return
            
        print(f"[SCRIPT UPDATE] Detected {event_type} for {script_type} script in folder {button_dir}")
        
        # Handle script change with small delay
        threading.Timer(0.1, self.script_manager.handle_script_change, args=[button_dir, script_type]).start()

    def on_any_event(self, event):
        """Handle any file system events.
        
        Args:
            event: File system event
        """
        # Ignore directory events
        if event.is_directory:
            return

        dest_info = f" -> {event.dest_path}" if hasattr(event, 'dest_path') else ""
        print(f"[FS EVENT] {event.event_type}: {event.src_path}{dest_info} (is_dir: {event.is_directory})")
        
        # Check all events that might affect image.* files
        if hasattr(event, 'dest_path'):
            # Moved event can rename temp file to image.png
            print(f"[MOVED CHECK] Checking dest_path: {event.dest_path}")
            self.process_image_change(event.dest_path, event.event_type)
        
        self.process_image_change(event.src_path, event.event_type)
        self.process_script_change(event.src_path, event.event_type)