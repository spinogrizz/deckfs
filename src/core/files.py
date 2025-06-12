"""File watcher with event debouncing."""

import os
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..utils.event_bus import EventBus


class FileWatcher(FileSystemEventHandler):
    """File system watcher with debouncing."""
    
    def __init__(self, event_bus: EventBus, config_dir: str):
        """Initialize file watcher.
        
        Args:
            event_bus: Event bus for emitting events
            config_dir: Directory to watch
        """
        self.event_bus = event_bus
        self.config_dir = config_dir
        self.observer: Observer = None
        self.file_types = ["image", "background", "update", "action"]
        
    def start_watching(self):
        """Start watching file system."""
        if self.observer:
            return
            
        self.observer = Observer()
        self.observer.schedule(self, path=self.config_dir, recursive=True)
        self.observer.start()
        print(f"File watcher started for: {self.config_dir}")
        
    def stop_watching(self):
        """Stop watching file system."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            print("File watcher stopped")
            
    def on_any_event(self, event):
        """Handle any file system event.
        
        Args:
            event: File system event
        """
        # Handle directory events (button folder changes)
        if event.is_directory:
            self._handle_directory_event(event)
            return
            
        # Handle file events
        file_path = getattr(event, 'dest_path', None) or event.src_path
        
        # Skip if no valid file path
        if not file_path:
            return
            
        # Skip opened/closed events that don't indicate actual file changes
        # to prevent infinite loops when daemon reads files
        if event.event_type in ['opened', 'closed_no_write']:
            return
            
        debounce_key = self._get_debounce_key(file_path)
        
        if debounce_key:
            # Emit debounced event
            self.event_bus.emit(
                "FILE_CHANGED",
                {
                    "path": file_path,
                    "event_type": event.event_type,
                    "src_path": event.src_path
                },
                debounce_key=debounce_key
            )
            
    def _handle_directory_event(self, event):
        """Handle directory events (button folder changes).
        
        Args:
            event: Directory event
        """
        # Skip 'modified' events for directories - these are usually caused by file changes inside
        if event.event_type == 'modified':
            return
            
        # Check if this is a button directory event at root level
        src_path = event.src_path
        dest_path = getattr(event, 'dest_path', None)
        
        # Check if directory is directly in config_dir (button folder)
        if self._is_button_directory_event(src_path) or (dest_path and self._is_button_directory_event(dest_path)):
            print(f"[BUTTON DIR EVENT] {event.event_type}: {src_path}" + (f" -> {dest_path}" if dest_path else ""))
            
            # Emit button directory change event with longer debouncing for directories
            debounce_key = "button_directories"
            
            # Use longer debounce for directory events to prevent reload loops
            self.event_bus.debounce_interval = 1.0  # Increase temporarily
            self.event_bus.emit(
                "BUTTON_DIRECTORIES_CHANGED",
                {
                    "event_type": event.event_type,
                    "src_path": src_path,
                    "dest_path": dest_path
                },
                debounce_key=debounce_key
            )
            # Reset back to normal
            self.event_bus.debounce_interval = 0.5
            
    def _is_button_directory_event(self, dir_path: str) -> bool:
        """Check if directory event is for a button directory.
        
        Args:
            dir_path: Directory path
            
        Returns:
            bool: True if this is a button directory
        """
        try:
            # Get relative path from config directory
            rel_path = os.path.relpath(dir_path, self.config_dir)
            
            # Check if it's a direct child (button directory)
            if os.sep in rel_path:
                return False  # Not a direct child
                
            # Check if directory name starts with digits (button pattern)
            return len(rel_path) >= 2 and rel_path[:2].isdigit()
            
        except Exception:
            return False
            
    def _get_debounce_key(self, file_path: str) -> str:
        """Generate debounce key for file path.
        
        Args:
            file_path: Path to file
            
        Returns:
            str: Debounce key
        """
        try:
            # Check if file_path is valid
            if not file_path or not file_path.strip():
                return None
                
            # Get relative path from config directory
            rel_path = os.path.relpath(file_path, self.config_dir)
            path_parts = rel_path.split(os.sep)
            
            if len(path_parts) < 2:
                return None
                
            # Extract button directory (first part)
            button_dir = path_parts[0]
            filename = path_parts[1]
            
            # Only process button directories (start with digits)
            if not (len(button_dir) >= 2 and button_dir[:2].isdigit()):
                return None
                
            # Create debounce key based on button and file type
            for file_type in self.file_types:
                if filename.startswith(f"{file_type}."):
                    return f"{button_dir}:{file_type}"
                    
            return None
            
        except Exception as e:
            print(f"Error generating debounce key for {file_path}: {e}")
            return None