"""Stream Deck button implementation."""

import os
import threading
from typing import Optional
from .processes import ProcessManager
from ..utils.file_utils import find_any_file


class Button:
    """Encapsulates a single Stream Deck button logic."""
    
    def __init__(self, working_dir: str):
        """Initialize button.
        
        Args:
            working_dir: Working directory for this button
        """
        self.working_dir = working_dir
        
        # Process manager for this button
        self.process_manager = ProcessManager(working_dir)
        
        # Monitor thread for background processes
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False
        
    def load_config(self) -> bool:
        """Load button configuration.
        
        Returns:
            bool: True if configuration loaded successfully
        """
        if not os.path.isdir(self.working_dir):
            return False
            
        self.process_manager.start_script("update", "update")
        
        return True
        
    def reload(self):
        """Reload button configuration."""
        self.stop()
        
        self.process_manager = ProcessManager(self.working_dir)
            
        self.load_config()
        self.start()
        
    def start(self):
        """Start button (background processes)."""
        if self.running:
            return
            
        self.running = True
        
        # Start background script if exists (only if not already running)
        if not self.process_manager.is_running("background"):
            self.process_manager.start_script("background", "background")
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor_background, daemon=True)
        self.monitor_thread.start()
        
    def stop(self):
        """Stop button (background processes)."""
        if not self.running:
            return
            
        self.running = False
        
        self.process_manager.cleanup()
            
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        
    def handle_press(self):
        """Handle button press."""
        self.process_manager.start_script("action", "action")
        
        
    def _find_image_file(self) -> Optional[str]:
        """Find image file for button.
        
        Returns:
            Optional[str]: Path to image file or None
        """
        return find_any_file(self.working_dir, "image")
    
    def handle_script_change(self, script_type: str):
        """Handle script file change.
        
        Args:
            script_type: Type of script that changed (background, update, action)
        """
        if script_type == "background":
            self.process_manager.stop_script("background")
            self.process_manager.start_script("background", "background")
        elif script_type == "update":
            self.process_manager.start_script("update", "update")
                
    def _monitor_background(self):
        """Monitor background process for crashes."""
        while self.running:
            if self.process_manager.is_running("background"):
                exit_code = self.process_manager.get_exit_code("background")
                if exit_code is not None:
                    self.process_manager.restart_script("background", "background")
                    
            # Use threading.Event().wait() instead of time.sleep() for better thread responsiveness
            # Allows clean shutdown when self.running becomes False
            threading.Event().wait(1)  # Check every second