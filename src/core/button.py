import os
import time
import threading
from typing import Optional
from PIL import Image
from .processes import ProcessManager
from ..utils.file_utils import find_any_file
from ..utils import logger


class Button:
    """Encapsulates a single Stream Deck button logic."""
    
    def __init__(self, working_dir: str, request_redraw):
        """Initialize button.
        
        Args:
            working_dir: Working directory for this button
            request_redraw: Callback to request image redraw
        """
        self.working_dir = working_dir
        self.request_redraw = request_redraw
        
        # Error state tracking
        self.failed = False
        
        # Background script crash protection
        self.background_crash_timestamps = []
        self.restart_limits = 5
        self.restart_window = 300  # 5 minutes
        
        # Process manager for this button with unified callback
        self.process_manager = ProcessManager(
            working_dir,
            on_script_completed=self._on_script_completed
        )
        
        self.running = False
        
    def load_config(self) -> bool:
        """Called by Coordinator after button creation to run update script.
        
        Returns:
            bool: True if configuration loaded successfully
        """
        if not os.path.isdir(self.working_dir):
            self.set_failed(True)
            return False
            
        # Clear any previous errors
        self.set_failed(False)
        
        # Update script is optional - not finding it is not an error
        self.process_manager.start_script_sync("update")
        
        return True
        
    def reload(self):
        """Called when button files change to recreate ProcessManager and restart scripts."""
        self.stop()
        
        self.process_manager = ProcessManager(
            self.working_dir,
            on_script_completed=self._on_script_completed
        )
            
        self.load_config()
        self.start()
        
    def start(self):
        """Called after device connection to start background script and monitoring."""
        if self.running:
            return
            
        self.running = True
        
        # Start background script if exists (only if not already running)
        if not self.process_manager.is_running("background"):
            self.process_manager.start_script_async("background")
        
        # Start process monitoring
        self.process_manager.start_monitoring()
        
    def stop(self):
        """Called during shutdown or disconnection to cleanup all processes and threads."""
        if not self.running:
            return
            
        self.running = False
        
        self.process_manager.cleanup()
        
    def handle_press(self):
        """Called by Coordinator when physical button is pressed to execute action script."""
        # Action script is optional - not finding it is not an error
        # Process manager will automatically monitor action completion
        self.process_manager.start_script_async("action")
        
    def set_failed(self, failed: bool):
        self.failed = failed
        self.request_redraw()   

    def _find_image_file(self) -> Optional[str]:
        """Internal method to locate image.* file for display on device."""
        return find_any_file(self.working_dir, "image")
    
    def get_image(self) -> Optional[Image.Image]:
        """Get PIL Image for this button or None if error/no image.
        
        Returns:
            Optional[Image.Image]: PIL Image or None if error/no image
        """
        if self.failed:
            return None
            
        image_path = self._find_image_file()
        if not image_path:
            return None
            
        try:
            # Resolve symlinks for dynamic image switching
            resolved_path = os.path.realpath(image_path)
            if not os.path.exists(resolved_path):
                logger.error(f"Image symlink target not found: {resolved_path}")
                return None
                
            image = Image.open(resolved_path)
            logger.debug(f"Image loaded: {resolved_path}")
            return image
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None
    
    def file_changed(self, filename: str) -> bool:
        """Called by coordinator when any file in button directory changes.
        
        Button decides what to do based on the filename.
        
        Args:
            filename: Name of the changed file
            
        Returns:
            bool: True if this file change was handled, False if ignored
        """
        if filename.startswith("image."):
            return True
        
        elif filename.startswith("background."):
            logger.debug(f"Background script changed in {self.working_dir}")
            self.process_manager.stop_script("background")
            success = self.process_manager.start_script_async("background")
            self.set_failed(not success)
            return True
        
        elif filename.startswith("update."):
            logger.debug(f"Update script changed in {self.working_dir}")
            self.process_manager.start_script_sync("update")
            return True
        
        elif filename.startswith("action."):
            logger.debug(f"Action script changed in {self.working_dir}")
            return True
        
        return False
                
    def _on_script_completed(self, script_name: str, exit_code: int):
        """Called by ProcessManager when any script completes.
        
        Args:
            script_name: Name of script that completed (action, background, update)
            exit_code: Exit code of the script
        """
        if script_name == "background":
            # Background script crashed, try to restart it with crash protection
            logger.debug(f"Background script exited with code {exit_code}, checking restart limits...")
            
            current_time = time.time()
            
            # Sliding window crash protection
            self.background_crash_timestamps = [
                ts for ts in self.background_crash_timestamps
                if current_time - ts < self.restart_window
            ]
            
            self.background_crash_timestamps.append(current_time)
            
            if len(self.background_crash_timestamps) > self.restart_limits:
                logger.warn("Background script crashed too many times. Giving up.")
                self.set_failed(True)
            else:
                # Clear any previous error state immediately - we're going to try restart
                self.set_failed(False)
                    
                # Wait a bit before restart to avoid rapid restart loops
                def restart_after_delay():
                    success = self.process_manager.start_script_async("background")
                    if not success:
                        self.set_failed(True)
                
                threading.Timer(2.0, restart_after_delay).start()

        elif script_name == "action":
            # Action script completed
            if exit_code != 0:
                # Action failed, show error temporarily
                self.set_failed(True)
                
                # Clear error after 2 seconds to restore normal display
                def clear_action_error():
                    self.set_failed(False)
                    
                threading.Timer(2.0, clear_action_error).start()
        # Update scripts are handled synchronously, no callback needed
    
