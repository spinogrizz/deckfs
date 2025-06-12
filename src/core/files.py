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
        # Ignore directory events
        if event.is_directory:
            return
            
        # Generate debounce key based on file path and button directory
        file_path = getattr(event, 'dest_path', event.src_path)
        
        # Skip if no valid file path
        if not file_path:
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
            if filename.startswith("image."):
                return f"{button_dir}:image"
            elif filename.startswith("background."):
                return f"{button_dir}:background"
            elif filename.startswith("update."):
                return f"{button_dir}:update"
            elif filename.startswith("action."):
                return f"{button_dir}:action"
                
            return None
            
        except Exception as e:
            print(f"Error generating debounce key for {file_path}: {e}")
            return None