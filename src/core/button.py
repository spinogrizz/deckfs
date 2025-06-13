"""Stream Deck button implementation."""

import os
import threading
from typing import Optional
from .processes import ProcessManager
from ..utils.file_utils import find_any_file
from ..utils import logger


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
        
        # Error state tracking
        self.has_error = False
        self.error_message = ""
        
        # Callback for error state changes
        self.on_error_changed = None
        
    def load_config(self) -> bool:
        """Called by StreamDeckManager after button creation to run update script.
        
        Returns:
            bool: True if configuration loaded successfully
        """
        if not os.path.isdir(self.working_dir):
            self.set_error(f"Button directory not found: {self.working_dir}")
            return False
            
        # Clear any previous errors
        self.clear_error()
        
        # Update script is optional - not finding it is not an error
        self.process_manager.start_script("update", "update")
        
        return True
        
    def reload(self):
        """Called when button files change to recreate ProcessManager and restart scripts."""
        self.stop()
        
        self.process_manager = ProcessManager(self.working_dir)
            
        self.load_config()
        self.start()
        
    def start(self):
        """Called after device connection to start background script and monitoring thread."""
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
        """Called during shutdown or disconnection to cleanup all processes and threads."""
        if not self.running:
            return
            
        self.running = False
        
        self.process_manager.cleanup()
            
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        
    def handle_press(self):
        """Called by StreamDeckManager when physical button is pressed to execute action script."""
        # Action script is optional - not finding it is not an error
        success = self.process_manager.start_script("action", "action")
        if success:
            # Start monitoring action script in background thread
            threading.Thread(target=self._monitor_action, daemon=True).start()
        
        
    def _find_image_file(self) -> Optional[str]:
        """Called by StreamDeckManager to locate image.* file for display on device."""
        return find_any_file(self.working_dir, "image")
    
    def handle_script_change(self, script_type: str):
        """Called by FileWatcher when script files are modified to restart affected scripts.
        
        Args:
            script_type: Type of script that changed (background, update, action)
        """
        if script_type == "background":
            self.process_manager.stop_script("background")
            success = self.process_manager.start_script("background", "background")
            if success:
                # Clear any previous error state when background script restarts successfully
                self.clear_error()
            else:
                self.set_error(f"Failed to restart {script_type} script")
        elif script_type == "update":
            # Update script is optional - not finding it is not an error
            self.process_manager.start_script("update", "update")
                
    def _monitor_background(self):
        """Background thread that checks every second for crashed background scripts.
        
        Automatically restarts crashed scripts with crash protection limits.
        """
        
        while self.running:
            # Check for exit code first (this also removes terminated processes)
            exit_code = self.process_manager.get_exit_code("background")
            if exit_code is not None:
                success = self.process_manager.restart_script("background", "background")
                if not success:
                    self.set_error("Background script crashed and failed to restart")
                    
            # Use threading.Event().wait() instead of time.sleep() for better thread responsiveness
            # Allows clean shutdown when self.running becomes False
            threading.Event().wait(1)  # Check every second
            
    
    def _monitor_action(self):
        """Monitor action script for errors and show temporary error on failure."""
        
        # Wait for action process and get its exit code
        exit_code = self.process_manager.wait_for_action_completion()
        
        if exit_code is not None and exit_code != 0:
            # Action failed, show error temporarily
            self.set_error(f"Action script failed with exit code {exit_code}")
            
            # Clear error after 2 seconds to restore normal display
            def clear_action_error():
                threading.Event().wait(2)
                self.clear_error()
                
            threading.Thread(target=clear_action_error, daemon=True).start()
    
    def set_error(self, message: str, notify: bool = True):
        """Set button error state.
        
        Args:
            message: Error message
            notify: Whether to notify callback about state change
        """
        was_error = self.has_error
        self.has_error = True
        self.error_message = message
        
        # Notify about error state change
        if not was_error and notify and self.on_error_changed:
            self.on_error_changed()
        
    def clear_error(self, notify: bool = True):
        """Clear button error state.
        
        Args:
            notify: Whether to notify callback about state change
        """
        was_error = self.has_error
        self.has_error = False
        self.error_message = ""
        
        # Notify about error state change
        if was_error and notify and self.on_error_changed:
            self.on_error_changed()