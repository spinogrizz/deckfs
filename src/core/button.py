"""Stream Deck button implementation."""

import os
import threading
from typing import Optional
from .processes import ProcessManager
from ..utils.file_utils import find_any_file
from ..utils.image_utils import load_and_prepare_image
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
        """Internal method to locate image.* file for display on device."""
        return find_any_file(self.working_dir, "image")
    
    def get_image_bytes(self, deck) -> Optional[bytes]:
        """Get prepared image bytes for this button or None if error/no image.
        
        Args:
            deck: Stream Deck device instance for image preparation
            
        Returns:
            Optional[bytes]: Prepared image bytes or None if error
        """
        if self.has_error:
            # Error state - caller should show error image
            return None
            
        image_path = self._find_image_file()
        if not image_path:
            # No image file found
            self.set_error(f"No image file found in {self.working_dir}", notify=False)
            return None
            
        try:
            image_bytes = load_and_prepare_image(deck, image_path)
            if image_bytes:
                # Clear any previous image loading errors
                if self.error_message.startswith("Failed to load image") or self.error_message.startswith("Error loading image"):
                    self.clear_error(notify=False)
                return image_bytes
            else:
                # Image loading failed
                self.set_error(f"Failed to load image: {image_path}", notify=False)
                return None
                
        except Exception as e:
            self.set_error(f"Error loading image: {e}", notify=False)
            return None
    
    def file_changed(self, filename: str) -> bool:
        """Called by devices.py when any file in button directory changes.
        
        Button decides what to do based on the filename.
        
        Args:
            filename: Name of the changed file
            
        Returns:
            bool: True if this file change was handled, False if ignored
        """
        if filename.startswith("image."):
            # Image file changed - devices.py will handle updating display
            return True
        elif filename.startswith("background."):
            logger.debug(f"Background script changed in {self.working_dir}")
            self.process_manager.stop_script("background")
            success = self.process_manager.start_script("background", "background")
            if success:
                # Clear any previous error state when background script restarts successfully
                self.clear_error()
            else:
                self.set_error("Failed to restart background script")
            return True
        elif filename.startswith("update."):
            logger.debug(f"Update script changed in {self.working_dir}")
            # Update script is optional - not finding it is not an error
            self.process_manager.start_script("update", "update")
            return True
        elif filename.startswith("action."):
            logger.debug(f"Action script changed in {self.working_dir}")
            # Action scripts don't need restart - they run on button press
            return True
        
        return False
                
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